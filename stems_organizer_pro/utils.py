"""
Stems Organizer PRO — Utilitários
Tooltip, retry decorator, FFmpeg check/download.
"""
import os
import sys
import shutil
import zipfile
import subprocess
import urllib.request
import time
import logging
from functools import wraps

import customtkinter as ctk
import tkinter as tk

logger = logging.getLogger(__name__)


# --- DECORATOR PARA RETRY AUTOMÁTICO ---
def retry_on_failure(max_retries=3, delay=1.0, backoff=2.0):
    """Decorator para retry automático em caso de falha"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Tentativa {attempt + 1} falhou: {e}. Tentando novamente em {current_delay}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff
            logger.error(f"Todas as {max_retries} tentativas falharam: {last_exception}")
            raise last_exception
        return wrapper
    return decorator


# --- VERIFICAÇÃO E INSTALAÇÃO DO FFMPEG ---
def check_ffmpeg():
    """Verifica se FFmpeg está instalado"""
    ffmpeg_dir = os.path.join(os.getenv('APPDATA', ''), 'StemsOrganizerPro', 'ffmpeg')
    if os.path.exists(ffmpeg_dir):
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def download_ffmpeg():
    """Baixa e instala FFmpeg automaticamente no Windows"""
    if sys.platform != 'win32':
        return False

    ffmpeg_dir = os.path.join(os.getenv('APPDATA', ''), 'StemsOrganizerPro', 'ffmpeg')
    ffmpeg_exe = os.path.join(ffmpeg_dir, 'ffmpeg.exe')

    if os.path.exists(ffmpeg_exe):
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
        return True

    try:
        logger.info("Baixando FFmpeg...")
        ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

        os.makedirs(ffmpeg_dir, exist_ok=True)
        zip_path = os.path.join(ffmpeg_dir, 'ffmpeg.zip')

        urllib.request.urlretrieve(ffmpeg_url, zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)

        for root, dirs, files in os.walk(ffmpeg_dir):
            for f in files:
                if f in ['ffmpeg.exe', 'ffprobe.exe']:
                    src = os.path.join(root, f)
                    dst = os.path.join(ffmpeg_dir, f)
                    if src != dst:
                        shutil.move(src, dst)

        os.remove(zip_path)
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
        logger.info("FFmpeg instalado com sucesso!")
        return True

    except Exception as e:
        logger.error(f"Erro ao instalar FFmpeg: {e}")
        return False


def init_ffmpeg():
    """Inicializa FFmpeg, tentando download se necessário"""
    available = check_ffmpeg()
    if not available:
        logger.info("FFmpeg não encontrado. Tentando instalar automaticamente...")
        available = download_ffmpeg()
    return available


# --- Classe Helper para Tooltips ---
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
        self.widget.bind("<Destroy>", self._on_widget_destroy)

    def _on_widget_destroy(self, event=None):
        """Limpa tooltip quando widget é destruído"""
        self.hide_tooltip(None)

    def show_tooltip(self, event):
        if self.tooltip_window or not self.text:
            return

        try:
            if not self.widget.winfo_exists():
                return
        except (tk.TclError, RuntimeError):
            return

        try:
            x, y, _, _ = self.widget.bbox("insert")
        except (tk.TclError, TypeError):
            x, y = 0, 0

        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25

        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.attributes('-topmost', True)

        label = ctk.CTkLabel(
            self.tooltip_window,
            text=self.text,
            fg_color="#3c3c3c",
            corner_radius=5,
            padx=8,
            pady=4,
            font=("", 12)
        )
        label.pack()

    def hide_tooltip(self, event):
        if self.tooltip_window:
            try:
                if self.tooltip_window.winfo_exists():
                    self.tooltip_window.destroy()
            except (tk.TclError, RuntimeError):
                pass
            self.tooltip_window = None
