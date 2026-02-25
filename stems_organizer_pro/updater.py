"""
Stems Organizer PRO — Auto Updater
Verificação, download e instalação de atualizações via GitHub Releases.
Estratégia .old para evitar conflitos de arquivo no Windows.
"""
import os
import sys
import json
import time
import threading
import subprocess
import urllib.request
import logging
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from .config import (
    CURRENT_VERSION, GITHUB_REPO, APP_DATA_PATH,
    COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM,
    COLOR_ACCENT_PURPLE, COLOR_ACCENT_CYAN
)
from .notifications import ToastNotification

logger = logging.getLogger(__name__)


class AutoUpdater:

    @staticmethod
    def parse_version(v):
        """Parse semver string para tupla comparável"""
        v = v.strip().lstrip('v')
        parts = []
        for p in v.split('.'):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    @staticmethod
    def cleanup_old_files():
        """Remove arquivos .old de atualizações anteriores"""
        try:
            app_dir = os.path.dirname(os.path.abspath(
                sys.executable if getattr(sys, 'frozen', False) else __file__
            ))
            for f in os.listdir(app_dir):
                if f.endswith('.old'):
                    try:
                        os.remove(os.path.join(app_dir, f))
                        logger.info(f"Limpeza: removido {f}")
                    except Exception:
                        pass
        except Exception:
            pass

    @staticmethod
    def check_for_updates():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            request = urllib.request.Request(url)
            request.add_header('User-Agent', f'StemsOrganizerPro/{CURRENT_VERSION}')
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                latest_version = data.get('tag_name', '').replace('v', '')
                if latest_version:
                    latest_tuple = AutoUpdater.parse_version(latest_version)
                    current_tuple = AutoUpdater.parse_version(CURRENT_VERSION)
                    if latest_tuple > current_tuple:
                        return data
        except Exception as e:
            logger.error(f"Erro ao checar atualizações: {e}")
        return None

    @staticmethod
    def download_and_install_update(release_data, parent_window):
        assets = release_data.get('assets', [])
        installer_url = None
        for asset in assets:
            if asset['name'].endswith('.exe') and 'setup' in asset['name'].lower():
                installer_url = asset['browser_download_url']
                break

        if not installer_url:
            ToastNotification(parent_window, "Instalador não encontrado na release.", "error")
            return

        # Overlay de download
        overlay = ctk.CTkFrame(parent_window, fg_color="#000000", corner_radius=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        center_frame = ctk.CTkFrame(
            overlay, fg_color=COLOR_CARD, corner_radius=16,
            border_width=1, border_color=COLOR_ACCENT_PURPLE
        )
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        icon_label = ctk.CTkLabel(center_frame, text="🔄", font=("", 40))
        icon_label.pack(pady=(30, 10))

        title_label = ctk.CTkLabel(
            center_frame, text="Baixando Atualização...",
            font=("", 18, "bold"), text_color=COLOR_TEXT
        )
        title_label.pack(pady=(0, 5))

        ctk.CTkLabel(
            center_frame,
            text=f"v{CURRENT_VERSION}  →  {release_data.get('tag_name', '?')}",
            font=("", 13), text_color=COLOR_ACCENT_CYAN
        ).pack(pady=(0, 15))

        progress = ctk.CTkProgressBar(
            center_frame, width=350, progress_color=COLOR_ACCENT_PURPLE
        )
        progress.pack(padx=40, pady=(0, 5))
        progress.set(0)

        pct_label = ctk.CTkLabel(
            center_frame, text="0%", font=("", 12), text_color=COLOR_TEXT_DIM
        )
        pct_label.pack(pady=(0, 20))

        def download_thread():
            temp_installer = os.path.join(APP_DATA_PATH, "StemsOrganizerPro_Updater.exe")
            try:
                def report_progress(block_num, block_size, total_size):
                    if total_size > 0:
                        percent = min(1.0, (block_num * block_size) / total_size)
                        parent_window.after(10, lambda p=percent: progress.set(p))
                        parent_window.after(10, lambda p=percent: pct_label.configure(text=f"{int(p*100)}%"))

                urllib.request.urlretrieve(installer_url, temp_installer, reporthook=report_progress)

                parent_window.after(10, lambda: title_label.configure(text="Atualização baixada!"))
                parent_window.after(10, lambda: icon_label.configure(text="✅"))
                parent_window.after(10, lambda: pct_label.configure(text="Iniciando instalador..."))
                time.sleep(1)

                # Estratégia .old
                if getattr(sys, 'frozen', False):
                    current_exe = sys.executable
                    old_exe = current_exe + '.old'
                    try:
                        if os.path.exists(old_exe):
                            os.remove(old_exe)
                        os.rename(current_exe, old_exe)
                        logger.info(f"Renomeado {current_exe} -> {old_exe}")
                    except Exception as e:
                        logger.warning(f"Não foi possível renomear exe: {e}")

                subprocess.Popen([temp_installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
                os._exit(0)
            except Exception as e:
                parent_window.after(0, lambda: overlay.destroy())
                
                def fallback_action():
                    error_msg = f"A atualização automática falhou.\nMotivo: {str(e)}\n\nO link de download manual da nova versão será aberto em seu navegador agora."
                    logger.error(f"Falha na atualização automática: {e}")
                    messagebox.showerror("Erro na Atualização Automática", error_msg)
                    release_url = release_data.get('html_url', f"https://github.com/{GITHUB_REPO}/releases/latest")
                    webbrowser.open(release_url)
                
                parent_window.after(100, fallback_action)

        threading.Thread(target=download_thread, daemon=True).start()
