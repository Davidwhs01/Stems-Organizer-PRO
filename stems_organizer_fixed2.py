"""
Stems Organizer PRO — Aplicação Principal
"""
import os
import re
import shutil
import sys
import threading
import json
import urllib.request
import subprocess
import hashlib
import winsound
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import google.generativeai as genai

# Optional dependencies
try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None
    CouldntDecodeError = Exception

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    create_client = None
    Client = None

from PIL import Image, ImageDraw, ImageFont
import io

# --- Importar módulos refatorados ---
from stems_organizer_pro.config import *
from stems_organizer_pro.utils import retry_on_failure, check_ffmpeg, download_ffmpeg, init_ffmpeg, Tooltip
from stems_organizer_pro.history import SessionHistory
from stems_organizer_pro.notifications import ToastNotification
from stems_organizer_pro.feedback import ExecutionFeedback
from stems_organizer_pro.updater import AutoUpdater

# --- Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

FFMPEG_AVAILABLE = init_ffmpeg()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Stems Organizer Pro by Prod. Aki")
        self.root.geometry("1200x850")
        self.root.minsize(1000, 650)

        ctk.set_appearance_mode("Dark")
        self.root.configure(fg_color=COLOR_BACKGROUND)

        # Inicializar todas as variáveis
        self.api_configured = False
        self.PARENT_FOLDER_MAP = {}
        self.LOCAL_CLASSIFICATION_RULES = {}
        self.planned_actions = []
        self.supabase = None
        self.master_prompt = ""
        self.folder_path_full = ""
        self.execution_feedback = None
        self.is_processing = False
        self.logo_image = None
        self.logo_label = None
        self.logo_image_pil = None
        self.logo_image_pil_full = None
        self.current_page = "home"
        self.sidebar_buttons = {}
        
        # Novas variáveis para melhorias
        self.cancel_requested = False
        self.ia_cache = {}
        self.undo_history = []
        self.processing_start_time = 0
        self.files_processed = 0
        self.total_files_to_process = 0

        # Limpeza de arquivos .old de atualizações anteriores
        AutoUpdater.cleanup_old_files()

        # Inicializar Supabase
        self.init_supabase()
        
        self.create_widgets()
        self.load_api_key()
        
        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.browse_folder())
        self.root.bind('<Control-Return>', lambda e: self.start_organization_thread() if not self.is_processing else None)
        self.root.bind('<Control-z>', lambda e: self.undo_last_action())
        self.root.bind('<Control-comma>', lambda e: self.open_settings_window())
        self.root.bind('<Escape>', lambda e: self.request_cancel() if self.is_processing else None)
        
        # Drag and drop (via tkdnd ou fallback)
        try:
            self.root.drop_target_register('DND_Files')
            self.root.dnd_bind('<<Drop>>', self._on_drop)
        except Exception:
            pass  # tkdnd não disponível, ignorar silenciosamente
        
        # Iniciar verificação de atualização em background
        self.root.after(2000, self.check_updates_async)
        
        # Toast de boas-vindas
        self.root.after(500, lambda: ToastNotification(self.root, f"Stems Organizer PRO v{CURRENT_VERSION}", "info", duration=2500))
        
        # FFmpeg status toast
        if FFMPEG_AVAILABLE:
            self.root.after(1500, lambda: ToastNotification(self.root, "FFmpeg detectado automaticamente", "success", duration=2000))
        else:
            self.root.after(1500, lambda: ToastNotification(self.root, "FFmpeg não encontrado. Algumas funções podem ser limitadas.", "warning", duration=4000))

    def _on_drop(self, event):
        """Handler para drag & drop de pastas"""
        path = event.data.strip('{}').strip('"')
        if os.path.isdir(path):
            self.folder_path_full = path
            self.folder_path_entry.configure(state="normal")
            self.folder_path_entry.delete(0, "end")
            self.folder_path_entry.insert(0, path)
            self.folder_path_entry.configure(state="readonly")
            self.start_button.configure(state="normal")
            wav_files = [f for f in os.listdir(path) if f.lower().endswith('.wav')]
            ToastNotification(self.root, f"Pasta carregada: {len(wav_files)} arquivos .wav", "info")
            self.navigate_to("organize")
        else:
            ToastNotification(self.root, "Arraste uma pasta, não um arquivo.", "warning")

    def check_updates_async(self):
        """Verifica por atualizações disponíveis sem travar a UI"""
        def update_task():
            release_data = AutoUpdater.check_for_updates()
            if release_data:
                version = release_data.get('tag_name', '')
                self.root.after(0, lambda: self.prompt_update(version, release_data))
        
        threading.Thread(target=update_task, daemon=True).start()

    def prompt_update(self, version, release_data):
        """Mostra toast de atualização disponível"""
        ToastNotification(
            self.root,
            f"Nova versão {version} disponível!",
            "update",
            duration=0,  # Não auto-dismiss
            action_text="Atualizar",
            action_callback=lambda: AutoUpdater.download_and_install_update(release_data, self.root)
        )

    def init_supabase(self):
        """Inicializa conexão com Supabase com tratamento de erro melhorado"""
        if not SUPABASE_AVAILABLE:
            logger.info("Supabase não disponível - funcionalidade de aprendizado desabilitada")
            self.supabase = None
            return
            
        try:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            # Teste simples da conexão
            test_response = self.supabase.table('rule_suggestions').select('id').limit(1).execute()
            logger.info("Supabase connection successful.")
        except Exception as e:
            logger.warning(f"Supabase connection failed - {e}")
            self.supabase = None

    def create_widgets(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ═══════════════════════ SIDEBAR ═══════════════════════
        sidebar = ctk.CTkFrame(self.root, fg_color=COLOR_SIDEBAR, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_propagate(False)

        # Logo + Brand
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=15, pady=(20, 5))
        self.load_logo(brand_frame)
        
        brand_label = ctk.CTkLabel(brand_frame, text="Stems Organizer", font=("", 16, "bold"), text_color=COLOR_TEXT)
        brand_label.pack(side="left")
        
        version_label = ctk.CTkLabel(sidebar, text=f"PRO v{CURRENT_VERSION}", font=("", 11), text_color=COLOR_TEXT_DIM)
        version_label.pack(anchor="w", padx=20, pady=(0, 20))

        # Separator
        sep = ctk.CTkFrame(sidebar, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", padx=15, pady=(0, 15))

        # Navigation buttons
        nav_items = [
            ("organize",  "📂  Organizar",    lambda: self.navigate_to("organize")),
            ("history",   "📊  Histórico",    lambda: self.navigate_to("history")),
            ("settings",  "⚙️  Configurações", lambda: self.open_settings_window()),
        ]

        for key, label, cmd in nav_items:
            btn = ctk.CTkButton(
                sidebar, text=label, font=("", 14), anchor="w",
                fg_color="transparent", hover_color=COLOR_SIDEBAR_ACTIVE,
                text_color=COLOR_TEXT, height=42, corner_radius=8,
                command=cmd
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.sidebar_buttons[key] = btn

        # Spacer
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Shortcuts hint at bottom
        shortcuts_frame = ctk.CTkFrame(sidebar, fg_color=COLOR_SURFACE, corner_radius=8)
        shortcuts_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(shortcuts_frame, text="⌨️ Atalhos", font=("", 11, "bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=10, pady=(8, 2))
        shortcuts_text = "Ctrl+O  Abrir pasta\nCtrl+⏎  Analisar\nCtrl+Z  Desfazer\nEsc     Cancelar"
        ctk.CTkLabel(shortcuts_frame, text=shortcuts_text, font=("Consolas", 10), text_color=COLOR_TEXT_DIM, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

        # Credits
        ctk.CTkLabel(sidebar, text="Made by Prod. Aki", text_color="#555555", font=("", 10)).pack(pady=(0, 15))

        # ═══════════════════════ MAIN AREA ═══════════════════════
        main_container = ctk.CTkFrame(self.root, fg_color=COLOR_BACKGROUND, corner_radius=0)
        main_container.grid(row=0, column=1, sticky="nsew")
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

        # Content area (pages go here)
        self.visual_organizer_frame = ctk.CTkFrame(main_container, fg_color=COLOR_BACKGROUND)
        self.visual_organizer_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=(15, 5))
        self.visual_organizer_frame.grid_columnconfigure(0, weight=1)
        self.visual_organizer_frame.grid_rowconfigure(0, weight=1)

        # ═══════════════════════ FOOTER (inside main) ═══════════════════════
        footer_frame = ctk.CTkFrame(main_container, fg_color=COLOR_FRAME, corner_radius=10)
        footer_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 15))
        footer_frame.grid_columnconfigure(0, weight=1)

        # Progress frame
        progress_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        progress_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        progress_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(progress_frame, text="Pronto para iniciar.", text_color=COLOR_TEXT, anchor="w", font=("", 12))
        self.status_label.grid(row=0, column=0, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(progress_frame, mode="determinate", progress_color=COLOR_ACCENT_PURPLE, height=6)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        # Controls frame
        self.controls_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        self.controls_frame.grid(row=0, column=1, rowspan=2, sticky="e", padx=15, pady=10)

        # Folder path entry (inline in controls)
        self.folder_path_entry = ctk.CTkEntry(
            self.controls_frame, placeholder_text="Nenhuma pasta selecionada...",
            state="readonly", width=280, height=32, font=("", 11),
            fg_color=COLOR_SURFACE, border_color=COLOR_BORDER
        )
        self.folder_path_entry.grid(row=0, column=0, padx=(0, 8))

        self.browse_button = ctk.CTkButton(
            self.controls_frame, text="📂 Abrir", width=80, height=32,
            fg_color=COLOR_ACCENT_CYAN, hover_color="#0891b2", text_color="#0d0d0e",
            font=("", 12, "bold"), command=self.browse_folder
        )
        self.browse_button.grid(row=0, column=1, padx=(0, 8))

        analysis_options = ["Análise Rápida (Padrão)", "Análise Profunda (Lenta)", "Nenhuma Análise (Mais Rápido)"]
        self.analysis_mode_combo = ctk.CTkComboBox(
            self.controls_frame, values=analysis_options, width=180, height=32,
            button_color=COLOR_ACCENT_PURPLE, border_color=COLOR_BORDER,
            dropdown_hover_color=COLOR_BUTTON_HOVER, state="readonly", font=("", 11)
        )
        self.analysis_mode_combo.set(analysis_options[0])
        self.analysis_mode_combo.grid(row=0, column=2, padx=(0, 8))

        self.start_button = ctk.CTkButton(
            self.controls_frame, text="⚡ Analisar", font=("", 13, "bold"), width=110, height=32,
            fg_color=COLOR_ACCENT_PURPLE, hover_color=COLOR_BUTTON_HOVER,
            command=self.start_organization_thread, state="disabled"
        )
        self.start_button.grid(row=0, column=3, padx=(0, 5))

        self.apply_button = ctk.CTkButton(
            self.controls_frame, text="✅ Aplicar", font=("", 13, "bold"), width=110, height=32,
            fg_color=COLOR_SUCCESS, hover_color="#059669", text_color="#ffffff",
            command=self.start_apply_thread
        )

        self.cancel_button = ctk.CTkButton(
            self.controls_frame, text="❌ Cancelar", font=("", 13, "bold"), width=110, height=32,
            fg_color=COLOR_ERROR, hover_color="#dc2626", command=self.request_cancel
        )

        self.undo_button = ctk.CTkButton(
            self.controls_frame, text="↩️ Desfazer", font=("", 12), width=100, height=32,
            fg_color=COLOR_WARNING, hover_color="#d97706", text_color="#0d0d0e",
            command=self.undo_last_action
        )

        # Inicializar no Organizar
        self.navigate_to("organize")

    def navigate_to(self, page):
        """Navega para uma página da sidebar com transição"""
        self.current_page = page
        
        # Atualizar visual dos botões da sidebar
        for key, btn in self.sidebar_buttons.items():
            if key == page:
                btn.configure(fg_color=COLOR_SIDEBAR_ACTIVE, text_color=COLOR_ACCENT_CYAN)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT)
        
        # Roteamento de páginas
        if page == "organize":
            if self.folder_path_full:
                self.show_folder_preview([f for f in os.listdir(self.folder_path_full) if f.lower().endswith('.wav')][:10])
            else:
                self.show_welcome_screen()
        elif page == "history":
            self.show_history_screen()

    def show_history_screen(self):
        """Mostra tela de histórico de sessões"""
        self.clear_frame(self.visual_organizer_frame)
        
        # Header
        header = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(header, text="📊 Histórico de Sessões", font=("", 24, "bold"), text_color=COLOR_TEXT).pack(side="left")
        
        sessions = SessionHistory.load()
        
        if not sessions:
            empty_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
            empty_frame.pack(expand=True)
            ctk.CTkLabel(empty_frame, text="📭", font=("", 48)).pack(pady=(30, 10))
            ctk.CTkLabel(empty_frame, text="Nenhuma sessão registrada ainda.", font=("", 16), text_color=COLOR_TEXT_DIM).pack()
            ctk.CTkLabel(empty_frame, text="As sessões serão salvas automaticamente após cada organização.", font=("", 13), text_color=COLOR_TEXT_DIM).pack(pady=5)
            return
        
        # Lista de sessões
        scroll = ctk.CTkScrollableFrame(self.visual_organizer_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        for session in reversed(sessions):
            card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
            card.pack(fill="x", pady=4)
            
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=15, pady=10)
            inner.grid_columnconfigure(1, weight=1)
            
            # Data
            ctk.CTkLabel(inner, text=f"📅 {session.get('date', '?')}", font=("", 13, "bold"), text_color=COLOR_ACCENT_CYAN).grid(row=0, column=0, sticky="w")
            
            # Pasta
            folder = session.get('folder', '?')
            folder_short = f"...{folder[-40:]}" if len(folder) > 40 else folder
            ctk.CTkLabel(inner, text=folder_short, font=("", 12), text_color=COLOR_TEXT_DIM).grid(row=0, column=1, sticky="w", padx=15)
            
            # Stats
            stats_text = f"📁 {session.get('files', 0)} arquivos  •  🏷️ {session.get('categories', 0)} categorias  •  ⏱️ {session.get('duration', 0)}s"
            ctk.CTkLabel(inner, text=stats_text, font=("", 11), text_color=COLOR_TEXT_DIM).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
            
            # Botão reabrir
            folder_path = session.get('folder', '')
            if os.path.isdir(folder_path):
                reopen_btn = ctk.CTkButton(
                    inner, text="📂 Reabrir", width=80, height=28, font=("", 11),
                    fg_color=COLOR_SURFACE, hover_color=COLOR_ACCENT_PURPLE,
                    command=lambda p=folder_path: self._reopen_folder(p)
                )
                reopen_btn.grid(row=0, column=2, rowspan=2, padx=(10, 0))

    def _reopen_folder(self, path):
        """Reabre uma pasta do histórico"""
        self.folder_path_full = path
        self.folder_path_entry.configure(state="normal")
        self.folder_path_entry.delete(0, "end")
        self.folder_path_entry.insert(0, path)
        self.folder_path_entry.configure(state="readonly")
        self.start_button.configure(state="normal")
        self.navigate_to("organize")
        ToastNotification(self.root, f"Pasta reaberta do histórico", "info")

    def load_logo(self, parent_frame):
        """Carrega logo de forma robusta com aspecto correto"""
        # Priorizar logo2.png (quadrada 128x128) sobre logo.png (retangular)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_candidates = [
            os.path.join(base_dir, "logo2.png"),
            os.path.join(APP_DATA_PATH, "logo2.png"),
            os.path.join(base_dir, "logo.png"),
        ]
        
        logo_size = 40
        
        try:
            original_image = None
            for logo_path in logo_candidates:
                if os.path.exists(logo_path):
                    original_image = Image.open(logo_path)
                    break
            
            if original_image is None:
                # Baixar logo se nenhuma existe localmente
                logger.debug("Baixando logo...")
                request = urllib.request.Request(LOGO_URL)
                request.add_header('User-Agent', f'StemsOrganizerPro/{CURRENT_VERSION}')
                with urllib.request.urlopen(request, timeout=10) as response:
                    image_data = response.read()
                    original_image = Image.open(io.BytesIO(image_data))
                    cache_path = os.path.join(APP_DATA_PATH, "logo2.png")
                    with open(cache_path, "wb") as f:
                        f.write(image_data)

            # Guardar imagem original para tela de boas-vindas
            self.logo_image_pil_full = original_image.copy()
            
            # Resize mantendo aspecto com thumbnail
            thumb = original_image.copy()
            thumb.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
            self.logo_image_pil = thumb

            # Criar widget de logo
            w, h = thumb.size
            self.logo_image = ctk.CTkImage(thumb, size=(w, h))
            self.logo_label = ctk.CTkLabel(parent_frame, image=self.logo_image, text="")
            self.logo_label.pack(side="left", padx=(0, 10))
                
        except Exception as e:
            logger.warning(f"Logo load failed - {e}")

    def show_welcome_screen(self):
        """Mostra tela de boas-vindas animada"""
        self.clear_frame(self.visual_organizer_frame)

        welcome_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        welcome_frame.pack(expand=True)

        # Logo grande com efeito pulsante
        logo_source = getattr(self, 'logo_image_pil_full', None) or self.logo_image_pil
        if logo_source:
            large_logo = logo_source.copy()
            large_logo.thumbnail((120, 120), Image.Resampling.LANCZOS)
            w, h = large_logo.size
            large_logo_ctk = ctk.CTkImage(large_logo, size=(w, h))
            logo_label = ctk.CTkLabel(welcome_frame, image=large_logo_ctk, text="")
            logo_label.pack(pady=(30, 15))
            # Efeito pulsante no logo
            self._pulse_widget(logo_label)

        # Título com animação de digitação
        title_text = "Stems Organizer Pro"
        welcome_title = ctk.CTkLabel(
            welcome_frame, text="", font=("", 32, "bold"), text_color=COLOR_ACCENT_CYAN
        )
        welcome_title.pack(pady=(0, 5))
        self._type_animation(welcome_title, title_text)

        # Linha de gradiente animada
        gradient_line = ctk.CTkFrame(welcome_frame, fg_color=COLOR_ACCENT_PURPLE, height=3, width=200, corner_radius=2)
        gradient_line.pack(pady=(0, 8))

        # Subtítulo
        subtitle = ctk.CTkLabel(
            welcome_frame, text="Organize seus stems de música automaticamente com IA",
            font=("", 15), text_color=COLOR_TEXT_DIM
        )
        subtitle.pack(pady=(0, 25))

        # Feature cards com fade-in escalonado
        cards_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        cards_frame.pack(padx=20, pady=10)

        features = [
            ("🤖", "IA Inteligente", "Classificação automática com Gemini"),
            ("⚡", "Super Rápido", "Processamento paralelo de stems"),
            ("🔊", "Análise de Áudio", "Detecção de silêncio com FFmpeg"),
            ("↩️", "Desfazer", "Reverta qualquer organização")
        ]

        for i, (icon, title, desc) in enumerate(features):
            card = ctk.CTkFrame(cards_frame, fg_color=COLOR_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER, width=180, height=130)
            card.grid(row=0, column=i, padx=8, pady=5)
            card.pack_propagate(False)

            ctk.CTkLabel(card, text=icon, font=("", 28)).pack(pady=(15, 5))
            ctk.CTkLabel(card, text=title, font=("", 13, "bold"), text_color=COLOR_TEXT).pack(pady=(0, 3))
            ctk.CTkLabel(card, text=desc, font=("", 10), text_color=COLOR_TEXT_DIM, wraplength=150).pack()

            # Fade-in escalonado
            card.grid_remove()
            self.root.after(400 + i * 200, lambda c=card: c.grid())

        # Instrução de ação
        action_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        action_frame.pack(pady=(25, 10))
        
        ctk.CTkLabel(
            action_frame, text="📂  Selecione uma pasta ou arraste para começar",
            font=("", 14), text_color=COLOR_TEXT_DIM
        ).pack()

    def _type_animation(self, label, full_text, index=0):
        """Animação de digitação para labels"""
        if index <= len(full_text):
            try:
                if label.winfo_exists():
                    label.configure(text=full_text[:index])
                    self.root.after(45, lambda: self._type_animation(label, full_text, index + 1))
            except:
                pass

    def _pulse_widget(self, widget, growing=True, count=0):
        """Efeito pulsante sutil num widget"""
        if count >= 6:  # 3 ciclos
            return
        try:
            if not widget.winfo_exists():
                return
            # Simular pulse alterando padding
            pad = 5 if growing else 0
            widget.configure(pady=pad)
            self.root.after(400, lambda: self._pulse_widget(widget, not growing, count + 1))
        except:
            pass

    def clear_frame(self, frame):
        """Destroi todos os widgets de um frame de forma segura"""
        try:
            if not frame.winfo_exists():
                return
        except:
            return
        
        for widget in frame.winfo_children():
            try:
                widget.destroy()
            except:
                pass
        
        try:
            self.root.update_idletasks()
        except:
            pass

    def play_lightning_effect(self, widget, flashes=3):
        """Efeito de flash no widget com verificações de segurança"""
        try:
            if not widget or not widget.winfo_exists():
                return
        except:
            return

        try:
            original_color = widget.cget("fg_color")
        except:
            return

        def flash(count):
            if count <= 0:
                try:
                    if widget.winfo_exists():
                        widget.configure(fg_color=original_color)
                except:
                    pass
                return

            try:
                if not widget.winfo_exists():
                    return
                current_color = COLOR_LIGHTNING if widget.cget("fg_color") == original_color else original_color
                widget.configure(fg_color=current_color)
                self.root.after(80, lambda: flash(count - 1))
            except:
                pass

        flash(flashes * 2)

    def update_status(self, message, progress):
        """Atualiza status e progresso de forma thread-safe"""
        def _update():
            try:
                if self.status_label.winfo_exists():
                    self.status_label.configure(text=message)
                if self.progress_bar.winfo_exists():
                    self.progress_bar.set(max(0.0, min(1.0, progress)))
            except:
                pass
        
        try:
            if self.root.winfo_exists():
                self.root.after(0, _update)
        except:
            pass

    def load_rules_from_sources(self):
        """Carrega regras com melhor tratamento de erro"""
        try:
            # Carregar regras base
            request = urllib.request.Request(RULES_URL)
            request.add_header('User-Agent', 'StemsOrganizerPro/1.0')

            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.PARENT_FOLDER_MAP = data.get("parent_folder_map", {})
                self.LOCAL_CLASSIFICATION_RULES = data.get("local_classification_rules", {})
                print(f"DEBUG: Loaded {len(self.LOCAL_CLASSIFICATION_RULES)} rule categories")

        except Exception as e:
            self.update_status(f"Erro ao baixar regras base: {e}", 0)
            print(f"DEBUG: Rules loading failed - {e}")
            # Regras de fallback mais completas
            self.PARENT_FOLDER_MAP = {
                "Drums": "Rhythm", "Bass": "Rhythm", "Perc": "Rhythm",
                "GTRs": "Harmony", "Piano": "Harmony", "Synth": "Harmony", "Pad": "Harmony",
                "Vocal": "Melody", "Orchestra": "Melody", "Fx": "Effects"
            }
            self.LOCAL_CLASSIFICATION_RULES = {
                "Drums": ["drum", "kick", "snare", "hat", "hihat", "cymbal", "tom", "perc"],
                "Bass": ["bass", "sub", "low", "808"],
                "GTRs": ["guitar", "gtr", "strum", "chord"],
                "Vocal": ["vocal", "voice", "lead", "harmony", "choir"],
                "Synth": ["synth", "lead", "pluck", "arp"],
                "Pad": ["pad", "string", "atmosphere"],
                "Orchestra": ["orchestra", "violin", "cello", "brass"],
                "Piano": ["piano", "keys", "electric"],
                "Fx": ["fx", "effect", "ambient", "riser", "sweep"],
                "Perc": ["perc", "shaker", "tambourine", "conga"]
            }

        # Tentar carregar regras aprendidas do Supabase
        if self.supabase:
            try:
                response = self.supabase.table('rule_suggestions')\
                    .select('keyword', 'category')\
                    .eq('is_approved', True)\
                    .execute()

                learned_rules = response.data if response.data else []
                print(f"DEBUG: Loaded {len(learned_rules)} learned rules from Supabase.")
                
                for rule in learned_rules:
                    keyword, category = rule['keyword'], rule['category']
                    if category in self.LOCAL_CLASSIFICATION_RULES:
                        if keyword not in self.LOCAL_CLASSIFICATION_RULES[category]:
                            self.LOCAL_CLASSIFICATION_RULES[category].append(keyword)
                    else:
                        self.LOCAL_CLASSIFICATION_RULES[category] = [keyword]
                        
            except Exception as e:
                print(f"DEBUG: Erro ao buscar regras do Supabase: {e}")

        return True

    def load_prompt_from_web(self):
        """Carrega prompt com fallback melhorado"""
        try:
            request = urllib.request.Request(PROMPT_URL)
            request.add_header('User-Agent', 'StemsOrganizerPro/1.0')

            with urllib.request.urlopen(request, timeout=15) as response:
                self.master_prompt = response.read().decode('utf-8')
                print("DEBUG: Master prompt loaded successfully")
                return True

        except Exception as e:
            print(f"DEBUG: Erro ao baixar prompt: {e}")
            # Prompt de fallback mais robusto
            self.master_prompt = """
Você é um especialista em classificação de stems musicais. Analise os nomes dos arquivos e classifique-os nas seguintes categorias:

CATEGORIAS VÁLIDAS:
- Drums: Elementos de bateria (kick, snare, hihat, cymbal, tom, etc.)
- Bass: Elementos de baixo frequência (bass, sub, 808, low, etc.) 
- GTRs: Guitarras e instrumentos de corda (guitar, gtr, strum, chord, etc.)
- Vocal: Elementos vocais (vocal, voice, lead, harmony, choir, etc.)
- Synth: Sintetizadores (synth, lead, pluck, arp, etc.)
- Pad: Pads e atmosferas (pad, string, atmosphere, etc.)
- Orchestra: Instrumentos orquestrais (orchestra, violin, cello, brass, etc.)
- Piano: Piano e teclados (piano, keys, electric, etc.)
- Fx: Efeitos sonoros (fx, effect, ambient, riser, sweep, etc.)
- Perc: Percussão (perc, shaker, tambourine, conga, etc.)
- Outros: Arquivos que não se encaixam em nenhuma categoria acima

ARQUIVOS PARA CLASSIFICAR:
{file_list}

INSTRUÇÕES:
1. Analise cada nome de arquivo cuidadosamente
2. Identifique palavras-chave que indiquem o tipo de instrumento/som
3. Classifique usando APENAS as categorias listadas acima
4. Retorne APENAS um JSON válido no formato: {{"nome_arquivo": "categoria"}}
5. Não adicione explicações ou texto extra

EXEMPLO DE RESPOSTA:
{{"kick_01.wav": "Drums", "bass_line.wav": "Bass", "guitar_chord.wav": "GTRs"}}

Categorias válidas: {valid_categories_list}
"""
            return True

    def load_api_key(self):
        """Carrega chave API com validação melhorada"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                    key = f.read().strip()
                    if key and len(key) > 20:
                        self.api_configured = True
                        print("DEBUG: API key loaded successfully")
                    else:
                        print("DEBUG: API key too short, marking as not configured")
            except Exception as e:
                print(f"DEBUG: Erro ao carregar API key: {e}")

    def save_api_key(self, key, popup):
        """Salva chave API com validação melhorada"""
        key = key.strip()
        if not key or len(key) < 20:
            messagebox.showerror("Erro", "Chave de API inválida. Deve ter pelo menos 20 caracteres.")
            return

        try:
            with open(CONFIG_FILE, "w", encoding='utf-8') as f:
                f.write(key)
            messagebox.showinfo("Sucesso", f"Chave de API salva com segurança em:\n{APP_DATA_PATH}")
            popup.destroy()
            self.api_configured = True
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar a chave:\n{e}")

    def browse_folder(self):
        """Seleciona pasta com validação melhorada"""
        folder_selected = filedialog.askdirectory(title="Selecione a pasta com arquivos .wav")
        if not folder_selected or not os.path.exists(folder_selected):
            return

        # Verificar se há arquivos .wav na pasta
        wav_files = []
        try:
            for root, dirs, files in os.walk(folder_selected):
                wav_files.extend([f for f in files if f.lower().endswith('.wav')])
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao acessar a pasta: {e}")
            return

        if not wav_files:
            messagebox.showwarning("Aviso", "Nenhum arquivo .wav encontrado na pasta selecionada.")
            return

        self.folder_path_entry.configure(state="normal")
        self.folder_path_entry.delete(0, ctk.END)
        display_path = f"...{os.path.basename(folder_selected)} ({len(wav_files)} arquivos)"
        self.folder_path_entry.insert(0, display_path)
        self.folder_path_entry.configure(state="readonly")
        self.folder_path_full = folder_selected
        self.start_button.configure(state="normal")

        # Mostrar prévia na tela principal
        self.show_folder_preview(wav_files[:10])

    def show_folder_preview(self, sample_files):
        """Mostra prévia dos arquivos na pasta selecionada"""
        self.clear_frame(self.visual_organizer_frame)

        preview_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        preview_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title = ctk.CTkLabel(
            preview_frame,
            text="🎵 Prévia dos arquivos encontrados",
            font=("", 20, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        title.pack(pady=(20, 15))

        files_frame = ctk.CTkScrollableFrame(preview_frame, fg_color=COLOR_BACKGROUND)
        files_frame.pack(fill="both", expand=True, padx=20)

        for file in sample_files:
            file_frame = ctk.CTkFrame(files_frame, fg_color=COLOR_FRAME)
            file_frame.pack(fill="x", padx=10, pady=5)

            file_icon = ctk.CTkLabel(file_frame, text="🎵", width=30)
            file_icon.pack(side="left", padx=10)

            # Truncar nomes de arquivos muito longos
            display_name = file if len(file) <= 60 else file[:57] + "..."
            file_label = ctk.CTkLabel(
                file_frame,
                text=display_name,
                anchor="w",
                font=("", 14)
            )
            file_label.pack(side="left", fill="x", expand=True, padx=10, pady=10)

        total_files = self.count_wav_files()
        if len(sample_files) < total_files:
            more_label = ctk.CTkLabel(
                preview_frame,
                text=f"... e mais {total_files - len(sample_files)} arquivos",
                font=("", 12),
                text_color="#888888"
            )
            more_label.pack(pady=10)

    def count_wav_files(self):
        """Conta total de arquivos .wav na pasta"""
        if not hasattr(self, 'folder_path_full') or not self.folder_path_full:
            return 0
        
        count = 0
        try:
            for root, dirs, files in os.walk(self.folder_path_full):
                count += len([f for f in files if f.lower().endswith('.wav')])
        except Exception:
            pass
        return count

    def start_organization_thread(self):
        """Inicia análise com validações melhoradas"""
        if not self.api_configured:
            self.open_settings_window()
            return

        if self.is_processing:
            messagebox.showwarning("Aviso", "Uma análise já está em andamento.")
            return

        if not self.folder_path_full or not os.path.exists(self.folder_path_full):
            messagebox.showwarning("Aviso", "Selecione uma pasta válida primeiro.")
            return

        self.is_processing = True
        self.cancel_requested = False  # Reset cancel flag
        self.planned_actions = []
        self.hide_apply_button()
        
        # Inicializar ETA
        self.processing_start_time = time.time()
        self.files_processed = 0
        self.total_files_to_process = self.count_wav_files()

        # Desabilitar controles e mostrar botão cancelar
        self.start_button.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.analysis_mode_combo.configure(state="disabled")
        self.show_cancel_button()

        # Inicializar feedback visual
        self.execution_feedback = ExecutionFeedback(self.visual_organizer_frame)

        threading.Thread(target=self.run_organization_logic, daemon=True).start()

    def hide_apply_button(self):
        """Esconde o botão aplicar"""
        try:
            self.apply_button.grid_remove()
        except:
            pass

    def show_apply_button(self):
        """Mostra o botão aplicar"""
        try:
            self.apply_button.grid(row=0, column=2, padx=(0, 0))
        except:
            pass

    def show_cancel_button(self):
        """Mostra o botão cancelar"""
        try:
            self.cancel_button.grid(row=0, column=3, padx=(10, 0))
        except:
            pass

    def hide_cancel_button(self):
        """Esconde o botão cancelar"""
        try:
            self.cancel_button.grid_remove()
        except:
            pass

    def request_cancel(self):
        """Solicita cancelamento do processamento"""
        if self.is_processing:
            self.cancel_requested = True
            self.update_status("⏹️ Cancelando... Aguarde a conclusão da operação atual.", 0)
            logger.info("Cancelamento solicitado pelo usuário")

    def show_undo_button(self):
        """Mostra o botão desfazer"""
        try:
            self.undo_button.grid(row=0, column=4, padx=(10, 0))
        except:
            pass

    def hide_undo_button(self):
        """Esconde o botão desfazer"""
        try:
            self.undo_button.grid_remove()
        except:
            pass

    def undo_last_action(self):
        """Desfaz a última organização aplicada"""
        if not self.undo_history:
            messagebox.showinfo("Info", "Nenhuma ação para desfazer.")
            return
        
        last_actions = self.undo_history.pop()
        
        if messagebox.askyesno("Confirmar Desfazer", 
                                f"Deseja desfazer {len(last_actions)} ações?"):
            success_count = 0
            error_count = 0
            
            for action in reversed(last_actions):
                try:
                    if action['type'] == 'move':
                        # Mover de volta para origem
                        if os.path.exists(action['destination']):
                            shutil.move(action['destination'], action['source'])
                            success_count += 1
                    elif action['type'] == 'rename':
                        # Renomear de volta
                        if os.path.exists(action['new_path']):
                            os.rename(action['new_path'], action['old_path'])
                            success_count += 1
                except Exception as e:
                    logger.error(f"Erro ao desfazer: {e}")
                    error_count += 1
            
            messagebox.showinfo("Desfazer Concluído", 
                               f"✅ {success_count} ações desfeitas\n❌ {error_count} erros")
            
            if not self.undo_history:
                self.hide_undo_button()

    def calculate_eta(self):
        """Calcula tempo estimado restante"""
        if self.files_processed == 0 or self.total_files_to_process == 0:
            return "Calculando..."
        
        elapsed = time.time() - self.processing_start_time
        rate = self.files_processed / elapsed if elapsed > 0 else 0
        remaining = self.total_files_to_process - self.files_processed
        
        if rate > 0:
            eta_seconds = remaining / rate
            if eta_seconds < 60:
                return f"~{int(eta_seconds)}s restantes"
            else:
                mins, secs = divmod(int(eta_seconds), 60)
                return f"~{mins}m {secs}s restantes"
        return "Calculando..."

    def get_cache_key(self, filename):
        """Gera chave de cache para um arquivo"""
        return hashlib.md5(filename.lower().encode()).hexdigest()

    def get_cached_result(self, filename):
        """Retorna resultado em cache se existir"""
        key = self.get_cache_key(filename)
        return self.ia_cache.get(key)

    def cache_result(self, filename, category):
        """Armazena resultado no cache"""
        key = self.get_cache_key(filename)
        self.ia_cache[key] = category

    def open_settings_window(self):
        """Janela de configurações premium"""
        settings_win = ctk.CTkToplevel(self.root)
        settings_win.title("⚙️ Configurações")
        settings_win.geometry("650x700")
        settings_win.transient(self.root)
        settings_win.grab_set()
        settings_win.configure(fg_color=COLOR_BACKGROUND)

        settings_win.update_idletasks()
        try:
            x = (settings_win.winfo_screenwidth() // 2) - (650 // 2)
            y = (settings_win.winfo_screenheight() // 2) - (700 // 2)
            settings_win.geometry(f"650x700+{x}+{y}")
        except:
            pass

        def on_closing():
            settings_win.grab_release()
            settings_win.destroy()
        settings_win.protocol("WM_DELETE_WINDOW", on_closing)

        # Header
        header = ctk.CTkFrame(settings_win, fg_color=COLOR_FRAME, corner_radius=0, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="⚙️  Configurações", font=("", 20, "bold"), text_color=COLOR_TEXT).pack(side="left", padx=20, pady=15)
        ctk.CTkLabel(header, text=f"v{CURRENT_VERSION}", font=("", 12), text_color=COLOR_TEXT_DIM).pack(side="right", padx=20)

        # Scrollable content
        content = ctk.CTkScrollableFrame(settings_win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # --- CARD 1: API Key ---
        api_card = ctk.CTkFrame(content, fg_color=COLOR_FRAME, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        api_card.pack(fill="x", pady=(0, 12))

        api_header = ctk.CTkFrame(api_card, fg_color="transparent")
        api_header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(api_header, text="🔑  Chave de API", font=("", 16, "bold"), text_color=COLOR_ACCENT_CYAN).pack(side="left")

        api_status = "✅ Configurada" if self.api_configured else "⚠️ Não configurada"
        status_color = COLOR_SUCCESS if self.api_configured else COLOR_WARNING
        ctk.CTkLabel(api_header, text=api_status, font=("", 11), text_color=status_color).pack(side="right")

        ctk.CTkLabel(api_card, text="Google Gemini AI — obtenha grátis em aistudio.google.com", font=("", 11), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=20, pady=(0, 10))

        key_frame = ctk.CTkFrame(api_card, fg_color=COLOR_BACKGROUND, corner_radius=8)
        key_frame.pack(fill="x", padx=20, pady=(0, 5))
        key_entry = ctk.CTkEntry(key_frame, placeholder_text="Cole sua chave API aqui...", show="•", font=("", 13), height=38, fg_color="transparent", border_width=0)
        key_entry.pack(fill="x", padx=10, pady=8)

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                    key_entry.insert(0, f.read().strip())
            except Exception:
                pass

        btn_frame = ctk.CTkFrame(api_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 15))
        ctk.CTkButton(btn_frame, text="🧪 Testar", font=("", 13, "bold"), width=120, height=34, fg_color=COLOR_ACCENT_PURPLE, hover_color=COLOR_BUTTON_HOVER, corner_radius=8, command=lambda: self.test_api_key(key_entry.get().strip())).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="💾 Salvar", font=("", 13, "bold"), width=120, height=34, fg_color=COLOR_ACCENT_CYAN, hover_color="#0097a7", text_color="#111111", corner_radius=8, command=lambda: self.save_api_key(key_entry.get().strip(), settings_win)).pack(side="left")

        # --- CARD 2: Atalhos ---
        sc_card = ctk.CTkFrame(content, fg_color=COLOR_FRAME, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        sc_card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(sc_card, text="⌨️  Atalhos de Teclado", font=("", 16, "bold"), text_color=COLOR_ACCENT_CYAN).pack(anchor="w", padx=20, pady=(15, 10))

        shortcuts = [("Ctrl + O", "Selecionar pasta"), ("Ctrl + Enter", "Iniciar análise"), ("Ctrl + Z", "Desfazer última ação"), ("Ctrl + ,", "Abrir configurações"), ("Esc", "Cancelar processamento")]
        sg = ctk.CTkFrame(sc_card, fg_color="transparent")
        sg.pack(fill="x", padx=20, pady=(0, 15))
        for key, desc in shortcuts:
            row = ctk.CTkFrame(sg, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=key, font=("Consolas", 11, "bold"), width=120, fg_color=COLOR_BACKGROUND, corner_radius=6, text_color=COLOR_ACCENT_PURPLE).pack(side="left", padx=(0, 12), ipady=3)
            ctk.CTkLabel(row, text=desc, font=("", 12), text_color=COLOR_TEXT, anchor="w").pack(side="left")

        # --- CARD 3: Categorias ---
        cat_card = ctk.CTkFrame(content, fg_color=COLOR_FRAME, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        cat_card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(cat_card, text="🎵  Categorias Suportadas", font=("", 16, "bold"), text_color=COLOR_ACCENT_CYAN).pack(anchor="w", padx=20, pady=(15, 10))

        categories = ["🥁 Drums", "🎸 Bass", "🎤 Vocal", "🎹 Piano", "🎛️ Synth", "🎼 Pad", "🎻 Orchestra", "🎧 Fx", "🪘 Perc", "🎺 Brass", "🎵 GTRs", "🔊 Sub", "🎶 Strings", "📦 Outros"]
        cg = ctk.CTkFrame(cat_card, fg_color="transparent")
        cg.pack(fill="x", padx=20, pady=(0, 15))
        for i, cat in enumerate(categories):
            ctk.CTkLabel(cg, text=cat, font=("", 11), width=130, fg_color=COLOR_BACKGROUND, corner_radius=6, text_color=COLOR_TEXT).grid(row=i // 4, column=i % 4, padx=4, pady=3, sticky="ew")
        cg.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # --- CARD 4: Sobre ---
        ab = ctk.CTkFrame(content, fg_color=COLOR_FRAME, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        ab.pack(fill="x", pady=(0, 12))
        ctk.CTkFrame(ab, fg_color=COLOR_ACCENT_PURPLE, height=3, corner_radius=2).pack(fill="x", padx=20, pady=(15, 10))

        logo_source = getattr(self, 'logo_image_pil_full', None) or self.logo_image_pil
        if logo_source:
            al = logo_source.copy()
            al.thumbnail((64, 64), Image.Resampling.LANCZOS)
            w, h = al.size
            alc = ctk.CTkImage(al, size=(w, h))
            ctk.CTkLabel(ab, image=alc, text="").pack(pady=(5, 8))

        ctk.CTkLabel(ab, text="Stems Organizer PRO", font=("", 20, "bold"), text_color=COLOR_ACCENT_CYAN).pack()
        ctk.CTkLabel(ab, text=f"v{CURRENT_VERSION} — Refactored Edition", font=("", 12), text_color=COLOR_TEXT_DIM).pack(pady=(2, 10))

        for ln in ["🎼  Desenvolvido por Prod. Aki", "🤖  Powered by Google Gemini AI", "💡  Interface com CustomTkinter", "☁️  Aprendizado com Supabase"]:
            ctk.CTkLabel(ab, text=ln, font=("", 12), text_color=COLOR_TEXT).pack(pady=1)

        ctk.CTkLabel(ab, text="© 2024-2026 Prod. Aki", font=("", 10), text_color=COLOR_TEXT_DIM).pack(pady=(10, 15))

    def test_api_key(self, key):
        """Testa a chave de API com melhor feedback"""
        if not key:
            messagebox.showerror("Erro", "Digite uma chave de API válida.")
            return

        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content("Teste de conexão. Responda apenas 'OK'.", 
                                            generation_config={'max_output_tokens': 10})
            
            if response and response.text and 'ok' in response.text.lower():
                messagebox.showinfo("Sucesso", "✅ Chave de API válida e funcionando!")
            else:
                messagebox.showerror("Erro", "❌ Chave de API não está funcionando corretamente.")
                
        except Exception as e:
            error_msg = str(e)
            if "quota" in error_msg.lower():
                messagebox.showerror("Erro", "❌ Cota da API excedida. Tente novamente mais tarde.")
            elif "invalid" in error_msg.lower():
                messagebox.showerror("Erro", "❌ Chave de API inválida.")
            else:
                messagebox.showerror("Erro", f"❌ Erro ao testar chave de API:\n{error_msg}")

    def run_organization_logic(self):
        """Lógica principal de organização com feedback visual melhorado"""
        analysis_mode = self.analysis_mode_combo.get()
        verificar_silencio = analysis_mode != "Nenhuma Análise (Mais Rápido)"
        verificacao_profunda = analysis_mode == "Análise Profunda (Lenta)"

        try:
            # Inicializar feedback
            self.execution_feedback.start_feedback(100)

            # Etapa 1: Configuração
            self.execution_feedback.update_activity("Configurando sistema e baixando regras...")
            self.update_status("Configurando e baixando regras...", 0.05)

            if not self.load_rules_from_sources():
                return
            if not self.load_prompt_from_web():
                return

            # Configurar API
            if self.api_configured and os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                        api_key = f.read().strip()
                    genai.configure(api_key=api_key)
                except Exception as e:
                    logger.error(f"Erro ao configurar API: {e}")
                    self.api_configured = False
            
            # Verificar cancelamento
            if self.cancel_requested:
                self.update_status("⛔ Análise cancelada pelo usuário.", 0)
                return

            # Etapa 2: Coleta de arquivos
            self.execution_feedback.update_activity("Coletando arquivos .wav...")
            pasta_raiz = self.folder_path_full
            todos_os_arquivos = {}

            try:
                for root, dirs, files in os.walk(pasta_raiz):
                    for file in files:
                        if file.lower().endswith('.wav'):
                            full_path = os.path.join(root, file)
                            todos_os_arquivos[full_path] = file
            except Exception as e:
                raise Exception(f"Erro ao coletar arquivos: {e}")

            if not todos_os_arquivos:
                self.update_status("Nenhum arquivo .wav encontrado.", 0)
                return

            logger.info(f"Encontrados {len(todos_os_arquivos)} arquivos .wav")

            # Etapa 3: Descobrir prefixo
            self.execution_feedback.update_activity("Analisando padrões de nomenclatura...")
            prefixo_sessao = self.descobrir_prefixo_recorrente(list(todos_os_arquivos.values()))
            if prefixo_sessao:
                logger.info(f"Prefixo de sessão encontrado: {prefixo_sessao}")

            candidatos_para_analise = {}
            total_files = len(todos_os_arquivos)

            # Etapa 4: Classificação local
            self.execution_feedback.update_activity("Iniciando classificação local...")
            
            for i, (caminho, nome_original) in enumerate(todos_os_arquivos.items()):
                # Verificar cancelamento
                if self.cancel_requested:
                    self.update_status("⛔ Análise cancelada pelo usuário.", 0)
                    return
                    
                progress = 0.15 + ((i + 1) / total_files) * 0.4
                self.files_processed = i + 1
                
                # Calcular ETA
                eta = self.calculate_eta()
                
                # Atualizar feedback em tempo real
                self.execution_feedback.update_activity(f"Processando: {nome_original}")
                self.execution_feedback.update_stats('processed')
                self.update_status(f"[{i+1}/{total_files}] {nome_original} | {eta}", progress)

                nome_limpo = nome_original.strip()
                nome_final = nome_limpo[len(prefixo_sessao):].strip() if prefixo_sessao and nome_limpo.startswith(prefixo_sessao) else nome_limpo

                # Verificar se deve descartar por padrão de nome
                if self.should_discard_file(nome_limpo):
                    self.armazenar_acao('delete', caminho)
                    self.execution_feedback.add_file_entry(nome_original, "Descartados", "🗑️")
                    self.execution_feedback.update_stats('discarded')
                    continue

                # *** VERIFICAR SILÊNCIO PRIMEIRO - ANTES DA CLASSIFICAÇÃO ***
                if verificar_silencio:
                    if self.is_audio_insignificant(caminho, deep_check=verificacao_profunda):
                        self.armazenar_acao('delete', caminho)
                        self.execution_feedback.add_file_entry(nome_original, "Silencioso", "🔇")
                        self.execution_feedback.update_stats('discarded')
                        logger.info(f"Arquivo silencioso descartado: {nome_original}")
                        continue

                # Classificação local (só se não foi descartado por silêncio)
                categoria_encontrada = self.classify_locally(nome_final)
                if categoria_encontrada:
                    self.mover_arquivo(caminho, nome_final, categoria_encontrada, pasta_raiz, is_dry_run=True)
                    self.execution_feedback.add_file_entry(nome_final, categoria_encontrada, "🎤")
                    self.execution_feedback.update_stats('classified')
                else:
                    candidatos_para_analise[nome_final] = caminho

                # Pequena pausa para não sobrecarregar a UI
                if i % 10 == 0:
                    time.sleep(0.01)

            # A verificação de silêncio já foi feita na Etapa 4 para TODOS os arquivos
            # Os candidatos restantes são apenas os que não são silenciosos
            candidatos_para_ia = candidatos_para_analise

            # Etapa 6: Classificação com IA
            if candidatos_para_ia and self.api_configured:
                total_ia = len(candidatos_para_ia)
                self.execution_feedback.update_activity(f"Consultando IA para {total_ia} arquivos...")
                self.update_status(f"Consultando IA para {total_ia} arquivos...", 0.7)

                # Processar em lotes menores para evitar timeout
                batch_size = 15
                processed_count = 0

                for i in range(0, total_ia, batch_size):
                    batch_files = list(candidatos_para_ia.keys())[i:i+batch_size]
                    batch_results = self.classificar_com_ia_mestre(batch_files)

                    if batch_results:
                        for nome, categoria in batch_results.items():
                            processed_count += 1
                            final_progress = 0.7 + (processed_count / total_ia) * 0.25
                            
                            self.execution_feedback.update_activity(f"Processando resultado IA: {nome}")
                            self.update_status(f"Processando IA [{processed_count}/{total_ia}]: {nome}", final_progress)

                            caminho_original = candidatos_para_ia.get(nome)
                            if categoria != "Outros" and caminho_original:
                                self.mover_arquivo(caminho_original, nome, categoria, pasta_raiz, is_dry_run=True)
                                self.execution_feedback.add_file_entry(nome, categoria, "🧠")
                                self.execution_feedback.update_stats('classified')
                                self.submit_suggestion_to_supabase(nome, categoria)
                            else:
                                if caminho_original:
                                    self.renomear_arquivo_no_local(caminho_original, nome, is_dry_run=True)
                                    self.execution_feedback.add_file_entry(nome, "Não Classificados", "❓")

                    # Pausa entre lotes
                    time.sleep(0.5)

            # Finalizar
            self.execution_feedback.update_activity("Análise concluída! Preparando relatório...")
            self.update_status("Análise concluída! Clique em 'Aplicar' para confirmar.", 1.0)

            # Aguardar um pouco para mostrar o status final
            time.sleep(1)

            # Mostrar relatório final
            self.root.after(0, self.show_final_report)
            self.root.after(100, lambda: self.play_lightning_effect(self.start_button))

        except Exception as e:
            error_msg = f"Erro durante análise: {str(e)}"
            self.update_status(error_msg, 0)
            self.root.after(0, lambda: messagebox.showerror("Erro", error_msg))
            print(f"DEBUG: {error_msg}")

        finally:
            self.is_processing = False
            self.root.after(0, self.hide_cancel_button)
            self.root.after(0, self.enable_controls)

    def should_discard_file(self, filename):
        """Verifica se arquivo deve ser descartado"""
        discard_patterns = [
            "('_0)",
            "master.wav",
            ".tmp",
            "_backup",
            "_old"
        ]
        
        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in discard_patterns)

    def classify_locally(self, filename):
        """Classifica arquivo usando regras locais"""
        filename_lower = filename.lower()
        
        for categoria, keywords in self.LOCAL_CLASSIFICATION_RULES.items():
            if any(keyword.lower() in filename_lower for keyword in keywords):
                return categoria
        
        return None

    def enable_controls(self):
        """Habilita os controles da UI e mostra o botão 'Aplicar' se necessário"""
        try:
            self.start_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.analysis_mode_combo.configure(state="normal")
            
            if self.planned_actions:
                self.show_apply_button()
        except:
            pass

    def show_final_report(self):
        """Mostra relatório final com design moderno"""
        self.clear_frame(self.visual_organizer_frame)

        report_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        report_frame.pack(fill="both", expand=True, padx=20, pady=10)
        report_frame.grid_columnconfigure(0, weight=1)
        report_frame.grid_columnconfigure(1, weight=2)
        report_frame.grid_rowconfigure(0, weight=1)

        # Contadores de ações
        move_count = len([a for a in self.planned_actions if a['action'] == 'move'])
        delete_count = len([a for a in self.planned_actions if a['action'] == 'delete'])
        rename_count = len([a for a in self.planned_actions if a['action'] == 'rename'])
        total_count = len(self.planned_actions)

        # ============= PAINEL DE RESUMO (ESQUERDA) =============
        summary_panel = ctk.CTkFrame(report_frame, fg_color=COLOR_FRAME, corner_radius=15, width=280)
        summary_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15), pady=0)
        summary_panel.pack_propagate(False)

        # Título do resumo
        title_frame = ctk.CTkFrame(summary_panel, fg_color=COLOR_ACCENT_CYAN, corner_radius=10)
        title_frame.pack(fill="x", padx=15, pady=(15, 20))
        
        ctk.CTkLabel(
            title_frame,
            text="📊 Resumo",
            font=("", 18, "bold"),
            text_color=COLOR_BACKGROUND
        ).pack(pady=12)

        # Cards de estatísticas
        stats_items = [
            ("🎵 Mover", move_count, COLOR_SUCCESS, "#2E7D32"),
            ("🗑️ Descartar", delete_count, COLOR_ERROR, "#C62828"),
            ("📝 Renomear", rename_count, COLOR_WARNING, "#F57C00")
        ]

        for label, count, color, hover_color in stats_items:
            card = ctk.CTkFrame(summary_panel, fg_color=COLOR_BACKGROUND, corner_radius=10)
            card.pack(fill="x", padx=15, pady=8)
            
            # Layout horizontal
            inner_frame = ctk.CTkFrame(card, fg_color="transparent")
            inner_frame.pack(fill="x", padx=15, pady=12)
            
            ctk.CTkLabel(
                inner_frame, 
                text=label, 
                font=("", 14),
                text_color=COLOR_TEXT,
                anchor="w"
            ).pack(side="left")
            
            # Badge com número
            badge = ctk.CTkLabel(
                inner_frame, 
                text=str(count), 
                font=("", 16, "bold"),
                text_color="#FFFFFF",
                fg_color=color,
                corner_radius=8,
                width=50,
                height=32
            )
            badge.pack(side="right")

        # Total
        total_frame = ctk.CTkFrame(summary_panel, fg_color=COLOR_ACCENT_PURPLE, corner_radius=10)
        total_frame.pack(fill="x", padx=15, pady=(20, 15))
        
        total_inner = ctk.CTkFrame(total_frame, fg_color="transparent")
        total_inner.pack(fill="x", padx=15, pady=12)
        
        ctk.CTkLabel(
            total_inner,
            text="Total de Ações",
            font=("", 14, "bold"),
            text_color="#FFFFFF"
        ).pack(side="left")
        
        ctk.CTkLabel(
            total_inner,
            text=str(total_count),
            font=("", 20, "bold"),
            text_color="#FFFFFF"
        ).pack(side="right")

        # ============= PAINEL DE AÇÕES (DIREITA) =============
        actions_panel = ctk.CTkFrame(report_frame, fg_color=COLOR_FRAME, corner_radius=15)
        actions_panel.grid(row=0, column=1, sticky="nsew", pady=0)

        # Título das ações
        actions_title = ctk.CTkFrame(actions_panel, fg_color=COLOR_ACCENT_PURPLE, corner_radius=10)
        actions_title.pack(fill="x", padx=15, pady=(15, 15))
        
        ctk.CTkLabel(
            actions_title,
            text="📋 Ações Planejadas",
            font=("", 18, "bold"),
            text_color="#FFFFFF"
        ).pack(pady=12)

        # Frame scrollável para ações
        actions_scroll = ctk.CTkScrollableFrame(
            actions_panel, 
            fg_color="transparent",
            scrollbar_button_color=COLOR_ACCENT_PURPLE,
            scrollbar_button_hover_color=COLOR_BUTTON_HOVER
        )
        actions_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        if not self.planned_actions:
            empty_frame = ctk.CTkFrame(actions_scroll, fg_color=COLOR_BACKGROUND, corner_radius=10)
            empty_frame.pack(fill="x", pady=20, padx=10)
            
            ctk.CTkLabel(
                empty_frame,
                text="✨ Tudo organizado!\nNenhuma ação necessária.",
                font=("", 16),
                text_color=COLOR_SUCCESS
            ).pack(pady=40)
        else:
            # Agrupar ações por tipo
            type_config = {
                'move': ("📁 Arquivos a mover", COLOR_SUCCESS, "➡️"),
                'delete': ("🗑️ Arquivos a descartar", COLOR_ERROR, "✖️"),
                'rename': ("📝 Arquivos a renomear", COLOR_WARNING, "✏️")
            }

            for action_type, (title, color, icon) in type_config.items():
                actions_of_type = [a for a in self.planned_actions if a['action'] == action_type]
                if not actions_of_type:
                    continue

                # Cabeçalho do grupo
                group_header = ctk.CTkFrame(actions_scroll, fg_color=color, corner_radius=8)
                group_header.pack(fill="x", pady=(10, 5), padx=5)
                
                ctk.CTkLabel(
                    group_header,
                    text=f"{title} ({len(actions_of_type)})",
                    font=("", 13, "bold"),
                    text_color="#FFFFFF"
                ).pack(pady=8, padx=10, anchor="w")

                # Listar ações
                for action in actions_of_type[:15]:  # Limitar a 15 por tipo
                    action_frame = ctk.CTkFrame(actions_scroll, fg_color=COLOR_BACKGROUND, corner_radius=6)
                    action_frame.pack(fill="x", padx=10, pady=2)
                    
                    inner = ctk.CTkFrame(action_frame, fg_color="transparent")
                    inner.pack(fill="x", padx=10, pady=8)

                    # Icon
                    ctk.CTkLabel(inner, text=icon, font=("", 14)).pack(side="left", padx=(0, 10))

                    # Detalhes
                    if action_type == 'move':
                        detail_text = f"{action['source_name']} → {action['category']}"
                    elif action_type == 'delete':
                        detail_text = os.path.basename(action['source_path'])
                    else:
                        detail_text = f"{os.path.basename(action['source_path'])} → {action['target_name']}"

                    ctk.CTkLabel(
                        inner,
                        text=detail_text,
                        font=("", 12),
                        text_color=COLOR_TEXT,
                        anchor="w"
                    ).pack(side="left", fill="x", expand=True)

                # Se há mais ações
                if len(actions_of_type) > 15:
                    ctk.CTkLabel(
                        actions_scroll,
                        text=f"... e mais {len(actions_of_type) - 15} arquivos",
                        font=("", 11),
                        text_color="#888888"
                    ).pack(pady=5)

    def start_apply_thread(self):
        """Inicia aplicação das mudanças em thread separada"""
        if not self.planned_actions:
            ToastNotification(self.root, "Nenhuma ação para aplicar.", "info")
            return

        if self.is_processing:
            ToastNotification(self.root, "Uma operação já está em andamento.", "warning")
            return

        # Confirmar aplicação
        response = messagebox.askyesno(
            "Confirmar Aplicação",
            f"Deseja aplicar {len(self.planned_actions)} ações?\n\n"
            "Esta operação não pode ser desfeita.",
            icon='question'
        )
        
        if not response:
            return

        self.is_processing = True
        self.apply_button.configure(state="disabled")
        self.start_button.configure(state="disabled")

        threading.Thread(target=self.apply_planned_actions, daemon=True).start()

    def apply_planned_actions(self):
        """Aplica as ações planejadas com feedback visual"""
        undo_batch = []  # Registrar ações para desfazer
        
        try:
            # Inicializar feedback para aplicação
            self.execution_feedback = ExecutionFeedback(self.visual_organizer_frame)
            self.execution_feedback.start_feedback(len(self.planned_actions))

            success_count = 0
            error_count = 0
            errors = []

            for i, action in enumerate(self.planned_actions):
                progress = (i + 1) / len(self.planned_actions)
                
                try:
                    if action['action'] == 'move':
                        self.execution_feedback.update_activity(f"Movendo: {action['source_name']}")
                        self.update_status(f"Movendo [{i+1}/{len(self.planned_actions)}]: {action['source_name']}", progress)
                        
                        # Calcular destino antes de mover
                        pasta_pai = self.PARENT_FOLDER_MAP.get(action['category'], "Outros")
                        categoria_path = os.path.join(self.folder_path_full, pasta_pai, action['category'])
                        destino = os.path.join(categoria_path, action['target_name'])
                        
                        # Executar movimento real
                        self.mover_arquivo(
                            action['source_path'], 
                            action['target_name'], 
                            action['category'], 
                            self.folder_path_full, 
                            is_dry_run=False
                        )
                        
                        # Registrar para undo
                        undo_batch.append({
                            'type': 'move',
                            'source': action['source_path'],
                            'destination': destino
                        })
                        
                        self.execution_feedback.add_file_entry(action['target_name'], action['category'], "✅")
                        
                    elif action['action'] == 'delete':
                        filename = os.path.basename(action['source_path'])
                        self.execution_feedback.update_activity(f"Descartando: {filename}")
                        self.update_status(f"Descartando [{i+1}/{len(self.planned_actions)}]: {filename}", progress)
                        
                        # Mover para lixeira (criar pasta Discarded)
                        discarded_folder = os.path.join(self.folder_path_full, "Discarded")
                        os.makedirs(discarded_folder, exist_ok=True)
                        target_path = os.path.join(discarded_folder, filename)
                        shutil.move(action['source_path'], target_path)
                        
                        # Registrar para undo
                        undo_batch.append({
                            'type': 'move',
                            'source': action['source_path'],
                            'destination': target_path
                        })
                        
                        self.execution_feedback.add_file_entry(filename, "Descartados", "🗑️")
                        
                    elif action['action'] == 'rename':
                        old_name = os.path.basename(action['source_path'])
                        self.execution_feedback.update_activity(f"Renomeando: {old_name}")
                        self.update_status(f"Renomeando [{i+1}/{len(self.planned_actions)}]: {old_name}", progress)
                        
                        # Calcular novo caminho
                        pasta_pai = os.path.dirname(action['source_path'])
                        new_path = os.path.join(pasta_pai, action['target_name'])
                        
                        # Executar renomeação real
                        self.renomear_arquivo_no_local(
                            action['source_path'], 
                            action['target_name'], 
                            is_dry_run=False
                        )
                        
                        # Registrar para undo
                        undo_batch.append({
                            'type': 'rename',
                            'old_path': action['source_path'],
                            'new_path': new_path
                        })
                        
                        self.execution_feedback.add_file_entry(action['target_name'], "Renomeados", "📝")

                    success_count += 1
                    self.execution_feedback.update_stats('classified')

                except Exception as e:
                    error_count += 1
                    error_msg = f"Erro ao processar {action.get('source_name', 'arquivo')}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    self.execution_feedback.update_stats('discarded')

                # Pequena pausa
                time.sleep(0.05)

            # Salvar histórico para undo se houve sucesso
            if undo_batch:
                self.undo_history.append(undo_batch)
                self.root.after(0, self.show_undo_button)

            # Finalizar
            final_message = f"Aplicação concluída!\n✅ {success_count} sucessos"
            if error_count > 0:
                final_message += f"\n❌ {error_count} erros"

            self.execution_feedback.update_activity("Aplicação concluída!")
            self.update_status(final_message, 1.0)

            # Mostrar resultado final
            time.sleep(2)
            self.root.after(0, lambda: self.show_completion_screen(success_count, error_count, errors))

        except Exception as e:
            error_msg = f"Erro durante aplicação: {str(e)}"
            self.update_status(error_msg, 0)
            self.root.after(0, lambda: messagebox.showerror("Erro", error_msg))
            logger.error(error_msg)

        finally:
            self.is_processing = False
            self.planned_actions = []
            self.root.after(0, self.enable_controls_after_apply)
            # Som de conclusão
            try:
                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                pass

    def show_completion_screen(self, success_count, error_count, errors):
        """Mostra tela de conclusão"""
        self.clear_frame(self.visual_organizer_frame)

        # Salvar no histórico de sessões
        duration = time.time() - self.processing_start_time if self.processing_start_time else 0
        categories = len(set(a.get('category', '') for a in (self.undo_history[-1] if self.undo_history else []) if a.get('type') == 'move'))
        SessionHistory.add(self.folder_path_full, success_count, max(categories, 1), duration)

        # Toast de conclusão
        if error_count == 0:
            ToastNotification(self.root, f"✅ {success_count} arquivos organizados com sucesso!", "success")
        else:
            ToastNotification(self.root, f"⚠️ {success_count} OK, {error_count} erros", "warning")

        completion_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        completion_frame.pack(expand=True)

        # Icon de sucesso
        success_icon = ctk.CTkLabel(
            completion_frame,
            text="🎉",
            font=("", 64)
        )
        success_icon.pack(pady=(50, 20))

        # Título
        title = ctk.CTkLabel(
            completion_frame,
            text="Organização Concluída!",
            font=("", 28, "bold"),
            text_color=COLOR_SUCCESS
        )
        title.pack(pady=(0, 10))

        # Estatísticas
        stats_text = f"✅ {success_count} arquivos processados com sucesso"
        if error_count > 0:
            stats_text += f"\n❌ {error_count} erros encontrados"

        stats_label = ctk.CTkLabel(
            completion_frame,
            text=stats_text,
            font=("", 16),
            text_color=COLOR_TEXT
        )
        stats_label.pack(pady=(0, 30))

        # Mostrar erros se houver
        if errors:
            errors_frame = ctk.CTkFrame(completion_frame, fg_color=COLOR_BACKGROUND)
            errors_frame.pack(padx=40, pady=10)

            ctk.CTkLabel(
                errors_frame,
                text="⚠️ Erros encontrados:",
                font=("", 14, "bold"),
                text_color=COLOR_WARNING
            ).pack(pady=(15, 5))

            for error in errors[:5]:  # Mostrar apenas os primeiros 5 erros
                error_label = ctk.CTkLabel(
                    errors_frame,
                    text=error,
                    font=("", 12),
                    text_color=COLOR_TEXT,
                    wraplength=600
                )
                error_label.pack(pady=2, padx=15)

            if len(errors) > 5:
                ctk.CTkLabel(
                    errors_frame,
                    text=f"... e mais {len(errors) - 5} erros",
                    font=("", 12),
                    text_color="#888888"
                ).pack(pady=(5, 15))

        # Botão para nova organização
        new_button = ctk.CTkButton(
            completion_frame,
            text="Nova Organização",
            font=("", 14, "bold"),
            fg_color=COLOR_ACCENT_PURPLE,
            hover_color=COLOR_BUTTON_HOVER,
            command=self.reset_for_new_organization,
            width=200
        )
        new_button.pack(pady=30)

    def reset_for_new_organization(self):
        """Reset para nova organização"""
        self.folder_path_entry.configure(state="normal")
        self.folder_path_entry.delete(0, ctk.END)
        self.folder_path_entry.insert(0, "Nenhuma pasta selecionada...")
        self.folder_path_entry.configure(state="readonly")
        self.folder_path_full = ""
        self.planned_actions = []
        self.hide_apply_button()
        self.start_button.configure(state="disabled")
        self.show_welcome_screen()

    def enable_controls_after_apply(self):
        """Habilita controles após aplicação"""
        try:
            self.start_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.analysis_mode_combo.configure(state="normal")
            self.hide_apply_button()
        except:
            pass

    def descobrir_prefixo_recorrente(self, arquivos):
        """Descobre prefixo comum nos nomes dos arquivos"""
        if not arquivos:
            return ""

        # Extrair possíveis prefixos (até 20 caracteres)
        possibles_prefixes = []
        for arquivo in arquivos:
            nome_limpo = arquivo.strip()
            for i in range(3, min(21, len(nome_limpo))):
                prefixo = nome_limpo[:i]
                if prefixo.endswith(('_', '-', ' ', '.')):
                    possibles_prefixes.append(prefixo)

        # Contar ocorrências
        contador_prefixos = Counter(possibles_prefixes)
        
        # Encontrar prefixo mais comum que apareça pelo menos MIN_PREFIX_OCCURRENCES vezes
        for prefixo, count in contador_prefixos.most_common():
            if count >= MIN_PREFIX_OCCURRENCES:
                return prefixo

        return ""

    def is_audio_insignificant(self, arquivo_path, deep_check=False):
        """Verifica se arquivo de áudio é insignificante usando FFmpeg volumedetect"""
        if not FFMPEG_AVAILABLE:
            logger.warning("FFmpeg não disponível - pulando verificação de silêncio")
            return False
            
        try:
            # Usar FFmpeg volumedetect (mesmo método do BAT que funciona)
            result = subprocess.run(
                ['ffmpeg', '-i', arquivo_path, '-af', 'volumedetect', '-f', 'null', 'NUL'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stderr  # FFmpeg output vai para stderr
            
            # Procurar max_volume na saída
            max_volume = None
            for line in output.split('\n'):
                if 'max_volume' in line:
                    # Extrair valor: "max_volume: -inf dB" ou "max_volume: -45.2 dB"
                    try:
                        # Formato: [Parsed_volumedetect_0 @ ...] max_volume: -inf dB
                        if '-inf' in line:
                            max_volume = float('-inf')
                        else:
                            # Extrair número antes de " dB"
                            import re
                            match = re.search(r'max_volume:\s*([-\d.]+)\s*dB', line)
                            if match:
                                max_volume = float(match.group(1))
                    except ValueError:
                        continue
            
            if max_volume is None:
                logger.debug(f"Não foi possível detectar volume de: {arquivo_path}")
                return False
            
            # Verificar se é silencioso (-inf ou <= -91 dB como no BAT)
            if max_volume == float('-inf'):
                logger.info(f"🔇 Silêncio total detectado (-inf dB): {os.path.basename(arquivo_path)}")
                return True
            
            if max_volume <= -91:
                logger.info(f"🔇 Arquivo muito silencioso ({max_volume:.1f} dB): {os.path.basename(arquivo_path)}")
                return True
            
            # Verificação adicional para análise profunda
            if deep_check and max_volume <= -60:
                logger.info(f"🔇 Arquivo silencioso em análise profunda ({max_volume:.1f} dB): {os.path.basename(arquivo_path)}")
                return True
                
            return False

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout ao analisar áudio: {arquivo_path}")
            return False
        except Exception as e:
            logger.debug(f"Erro ao analisar áudio {arquivo_path}: {e}")
            return False

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def classificar_com_ia_mestre(self, lista_arquivos):
        """Classifica arquivos usando IA com prompt mestre otimizado"""
        if not lista_arquivos or not self.api_configured:
            return {}

        # Verificar cache primeiro
        cached_results = {}
        files_to_classify = []
        
        for arquivo in lista_arquivos:
            cached = self.get_cached_result(arquivo)
            if cached:
                cached_results[arquivo] = cached
                logger.debug(f"Cache hit para: {arquivo}")
            else:
                files_to_classify.append(arquivo)
        
        # Se todos estão em cache, retornar
        if not files_to_classify:
            return cached_results

        try:
            # Preparar lista de categorias válidas
            valid_categories = list(self.LOCAL_CLASSIFICATION_RULES.keys()) + ["Outros"]
            
            # Preparar prompt apenas para arquivos não em cache
            files_str = "\n".join([f"- {arquivo}" for arquivo in files_to_classify])
            
            prompt = self.master_prompt.format(
                file_list=files_str,
                valid_categories_list=", ".join(valid_categories)
            )

            # Chamar API
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={
                    'max_output_tokens': 2048,
                    'temperature': 0.1,
                }
            )

            if not response or not response.text:
                logger.debug("Resposta vazia da IA")
                return {}

            # Parse do JSON - mais robusto
            response_text = response.text.strip()
            
            # Limpar resposta (remover markdown se presente) - suporta múltiplos formatos
            # Remove ```json, ```JSON, ``` no início
            response_text = re.sub(r'^```(?:json|JSON)?\s*\n?', '', response_text)
            # Remove ``` no final
            response_text = re.sub(r'\n?```\s*$', '', response_text)
            
            response_text = response_text.strip()
            
            # Tentar extrair JSON com regex se parse direto falhar
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Tentar encontrar JSON no texto usando regex
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.debug(f"Não foi possível extrair JSON da resposta: {response_text[:200]}")
                    return {}
            
            # Validar resultado e armazenar no cache
            validated_result = {}
            for arquivo, categoria in result.items():
                if categoria in valid_categories:
                    validated_result[arquivo] = categoria
                    # Armazenar no cache
                    self.cache_result(arquivo, categoria)
                else:
                    logger.debug(f"Categoria inválida '{categoria}' para arquivo '{arquivo}'")
                    validated_result[arquivo] = "Outros"
                    self.cache_result(arquivo, "Outros")

            logger.info(f"IA classificou {len(validated_result)} arquivos (cache: {len(cached_results)})")
            
            # Mesclar com resultados em cache
            validated_result.update(cached_results)
            return validated_result

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse do JSON da IA: {e}")
            logger.debug(f"Resposta da IA: {response.text if response else 'None'}")
            return cached_results  # Retornar ao menos os resultados em cache
        except Exception as e:
            logger.error(f"Erro geral na classificação por IA: {e}")
            raise  # Re-raise para o retry decorator

    def mover_arquivo(self, caminho_origem, nome_novo, categoria, pasta_raiz, is_dry_run=True):
        """Move arquivo para categoria apropriada"""
        try:
            # Determinar pasta pai
            pasta_pai = self.PARENT_FOLDER_MAP.get(categoria, "Outros")
            
            # Criar estrutura de pastas
            pasta_pai_path = os.path.join(pasta_raiz, pasta_pai)
            categoria_path = os.path.join(pasta_pai_path, categoria)
            
            if not is_dry_run:
                os.makedirs(categoria_path, exist_ok=True)
                
                # Mover arquivo
                destino = os.path.join(categoria_path, nome_novo)
                
                # Evitar sobrescrever arquivos
                counter = 1
                base_name, ext = os.path.splitext(nome_novo)
                while os.path.exists(destino):
                    destino = os.path.join(categoria_path, f"{base_name}_{counter}{ext}")
                    counter += 1
                
                shutil.move(caminho_origem, destino)
            else:
                # Apenas armazenar ação
                self.armazenar_acao('move', caminho_origem, nome_novo, categoria)

        except Exception as e:
            print(f"DEBUG: Erro ao mover arquivo {caminho_origem}: {e}")
            raise

    def renomear_arquivo_no_local(self, caminho_origem, nome_novo, is_dry_run=True):
        """Renomeia arquivo no local"""
        try:
            if not is_dry_run:
                pasta_pai = os.path.dirname(caminho_origem)
                destino = os.path.join(pasta_pai, nome_novo)
                
                # Evitar sobrescrever
                counter = 1
                base_name, ext = os.path.splitext(nome_novo)
                while os.path.exists(destino):
                    destino = os.path.join(pasta_pai, f"{base_name}_{counter}{ext}")
                    counter += 1
                
                os.rename(caminho_origem, destino)
            else:
                # Apenas armazenar ação
                self.armazenar_acao('rename', caminho_origem, nome_novo)

        except Exception as e:
            print(f"DEBUG: Erro ao renomear arquivo {caminho_origem}: {e}")
            raise

    def armazenar_acao(self, action_type, source_path, target_name=None, category=None):
        """Armazena ação planejada"""
        action = {
            'action': action_type,
            'source_path': source_path,
            'source_name': os.path.basename(source_path)
        }
        
        if target_name:
            action['target_name'] = target_name
        if category:
            action['category'] = category
            
        self.planned_actions.append(action)

    def submit_suggestion_to_supabase(self, filename, category):
        """Submete sugestão para Supabase para aprendizado colaborativo"""
        if not self.supabase:
            return

        try:
            # Extrair palavras-chave do nome do arquivo
            keywords = re.findall(r'\b\w+\b', filename.lower())
            
            for keyword in keywords:
                if len(keyword) >= 3:  # Palavras com pelo menos 3 caracteres
                    # Verificar se já existe
                    existing = self.supabase.table('rule_suggestions')\
                        .select('id')\
                        .eq('keyword', keyword)\
                        .eq('category', category)\
                        .execute()
                    
                    if not existing.data:
                        # Submeter nova sugestão
                        self.supabase.table('rule_suggestions').insert({
                            'keyword': keyword,
                            'category': category,
                            'confidence': 0.8,
                            'is_approved': False
                        }).execute()

        except Exception as e:
            print(f"DEBUG: Erro ao submeter sugestão: {e}")

# Função principal
def main():
    root = ctk.CTk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
