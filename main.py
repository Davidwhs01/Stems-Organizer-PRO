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
from google import genai
from google.genai import types

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
from stems_organizer_pro.utils import retry_on_failure, check_ffmpeg, download_ffmpeg, init_ffmpeg, Tooltip, enable_native_windows_effects
from stems_organizer_pro.history import SessionHistory
from stems_organizer_pro.notifications import ToastNotification
from stems_organizer_pro.feedback import ExecutionFeedback
from stems_organizer_pro.updater import AutoUpdater
from stems_organizer_pro.classifier import AudioClassifier
from stems_organizer_pro.file_ops import FileOperations
from stems_organizer_pro.auth import AuthManager
from stems_organizer_pro import screens

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
        
        # Obter o caminho base que funciona nativo ou compilado via PyInstaller
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        
        # Configurar ícone da janela
        try:
            icon_path = os.path.join(base_path, 'logo2.ico')
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Erro ao carregar ícone da janela: {e}")

        ctk.set_appearance_mode("Dark")
        self.root.configure(fg_color=COLOR_BACKGROUND)

        # Inicializar todas as variáveis
        self.api_configured = False

        self.planned_actions = []
        self.supabase = None
        self.master_prompt = ""
        self.folder_path_full = ""
        self.execution_feedback = None
        self.is_processing = False
        self.api_key = ""
        self.classifier = AudioClassifier(self.api_key, self.supabase, FFMPEG_AVAILABLE)
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

        # Inicializar Supabase e Auth
        self.init_supabase()
        self.auth = AuthManager(self.supabase)
        
        self.create_widgets()
        
        # Aplicar efeitos Premium Nativos do Windows 11 (Dark Titlebar + Cantos Arredondados)
        enable_native_windows_effects(self.root)
        
        # Tentar Auto-Login
        if not self.auth.attempt_auto_login():
            self.root.after(100, self.show_login_screen)
        else:
            # Se logou auto, pega a key do Supabase pra memoria
            key = self.auth.fetch_user_api_key()
            if key:
                self.api_key = key
                self.classifier.api_key = key
                self.api_configured = True
            self.root.after(100, lambda: self.navigate_to('organize'))

        self.load_api_key()
        
        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.browse_folder())
        self.root.bind('<Control-Return>', lambda e: self.start_organization_thread() if not self.is_processing else None)
        self.root.bind('<Control-z>', lambda e: self.undo_last_action())
        self.root.bind('<Control-comma>', lambda e: self.navigate_to('settings'))
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
            test_response = self.supabase.table('ai_learning_rules').select('id').limit(1).execute()
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
        
        brand_label = ctk.CTkLabel(brand_frame, text="Stems Organizer", font=FONT_BRAND, text_color=COLOR_TEXT)
        brand_label.pack(side="left")
        
        version_label = ctk.CTkLabel(sidebar, text=f"PRO v{CURRENT_VERSION}", font=FONT_CAPTION_DIM, text_color=COLOR_TEXT_DIM)
        version_label.pack(anchor="w", padx=20, pady=(0, 20))

        # Separator
        sep = ctk.CTkFrame(sidebar, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", padx=15, pady=(0, 15))

        # Navigation buttons — clean text, no emojis
        nav_items = [
            ("organize",  "Organizar",      lambda: self.navigate_to("organize")),
            ("history",   "Histórico",      lambda: self.navigate_to("history")),
            ("settings",  "Configurações",  lambda: self.navigate_to("settings")),
        ]

        self.nav_indicators = {}  # Active indicator bars
        for key, label, cmd in nav_items:
            # Container for indicator + button
            nav_row = ctk.CTkFrame(sidebar, fg_color="transparent", height=42)
            nav_row.pack(fill="x", padx=6, pady=1)
            nav_row.pack_propagate(False)

            # Active indicator bar (left edge)
            indicator = ctk.CTkFrame(nav_row, fg_color="transparent", width=3, corner_radius=2)
            indicator.pack(side="left", fill="y", padx=(0, 0))
            self.nav_indicators[key] = indicator

            btn = ctk.CTkButton(
                nav_row, text=label, font=FONT_NAV, anchor="w",
                fg_color="transparent", hover_color=COLOR_SIDEBAR_ACTIVE,
                text_color=COLOR_TEXT_DIM, height=42, corner_radius=8,
                command=cmd
            )
            btn.pack(side="left", fill="both", expand=True, padx=(4, 4))
            self.sidebar_buttons[key] = btn

        # Spacer
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Shortcuts hint at bottom
        shortcuts_frame = ctk.CTkFrame(sidebar, fg_color=COLOR_SURFACE, corner_radius=8)
        shortcuts_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(shortcuts_frame, text="Atalhos", font=FONT_CAPTION, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=10, pady=(8, 2))
        shortcuts_text = "Ctrl+O  Abrir pasta\nCtrl+⏎  Analisar\nCtrl+Z  Desfazer\nEsc     Cancelar"
        ctk.CTkLabel(shortcuts_frame, text=shortcuts_text, font=FONT_CODE, text_color=COLOR_TEXT_DIM, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

        # Credits
        ctk.CTkLabel(sidebar, text="by Prod. Aki", text_color="#444444", font=FONT_CAPTION_DIM).pack(pady=(0, 15))

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

        self.status_label = ctk.CTkLabel(progress_frame, text="Pronto para iniciar.", text_color=COLOR_TEXT, anchor="w", font=FONT_BODY)
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
            state="readonly", width=280, height=34, font=FONT_BODY,
            fg_color=COLOR_SURFACE, border_color=COLOR_BORDER, corner_radius=10
        )
        self.folder_path_entry.grid(row=0, column=0, padx=(0, 8))

        self.browse_button = ctk.CTkButton(
            self.controls_frame, text="Abrir", width=80, height=34,
            fg_color=COLOR_ACCENT_CYAN, hover_color="#0891b2", text_color="#0a0a0b",
            font=FONT_BUTTON, command=self.browse_folder, corner_radius=10
        )
        self.browse_button.grid(row=0, column=1, padx=(0, 8))

        self.clear_button = ctk.CTkButton(
            self.controls_frame, text="\u2715", width=34, height=34,
            fg_color=COLOR_ERROR, hover_color="#c62828", text_color="white",
            font=FONT_BUTTON, command=self.clear_folder_selection, corner_radius=10
        )

        analysis_options = ["Análise Rápida (Padrão)", "Análise Profunda (Lenta)", "Nenhuma Análise (Mais Rápido)"]
        self.analysis_mode_combo = ctk.CTkComboBox(
            self.controls_frame, values=analysis_options, width=190, height=34,
            button_color=COLOR_ACCENT_PURPLE, border_color=COLOR_BORDER,
            dropdown_hover_color=COLOR_BUTTON_HOVER, state="readonly", font=FONT_BODY,
            corner_radius=10
        )
        self.analysis_mode_combo.set(analysis_options[0])
        self.analysis_mode_combo.grid(row=0, column=2, padx=(0, 8))

        self.start_button = ctk.CTkButton(
            self.controls_frame, text="Analisar", font=FONT_BUTTON, width=110, height=34,
            fg_color=COLOR_ACCENT_PURPLE, hover_color=COLOR_BUTTON_HOVER,
            command=self.start_organization_thread, state="disabled", corner_radius=10
        )
        self.start_button.grid(row=0, column=3, padx=(0, 5))

        self.apply_button = ctk.CTkButton(
            self.controls_frame, text="Aplicar", font=FONT_BUTTON, width=110, height=34,
            fg_color=COLOR_SUCCESS, hover_color="#059669", text_color="#ffffff",
            command=self.start_apply_thread, corner_radius=10
        )

        self.cancel_button = ctk.CTkButton(
            self.controls_frame, text="Cancelar", font=FONT_BUTTON, width=110, height=34,
            fg_color=COLOR_ERROR, hover_color="#dc2626", corner_radius=10,
            command=self.request_cancel
        )

        self.undo_button = ctk.CTkButton(
            self.controls_frame, text="Desfazer", font=FONT_BUTTON, width=100, height=34,
            fg_color=COLOR_WARNING, hover_color="#d97706", text_color="#0a0a0b",
            command=self.undo_last_action, corner_radius=10
        )

        # Inicializar no Organizar
        self.navigate_to("organize")
            
    def navigate_to(self, page):
        """Navega para uma página da sidebar com transição"""
        self.current_page = page
        
        # Atualizar visual dos botões e indicadores da sidebar
        for key, btn in self.sidebar_buttons.items():
            indicator = self.nav_indicators.get(key)
            if key == page:
                btn.configure(fg_color=COLOR_SIDEBAR_ACTIVE, text_color=COLOR_ACCENT_CYAN)
                if indicator:
                    indicator.configure(fg_color=COLOR_ACCENT_CYAN)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_DIM)
                if indicator:
                    indicator.configure(fg_color="transparent")
        
        # Roteamento de páginas
        self.pages = {
            "organize": self.show_welcome_screen,
            "history": self.show_history_screen,
            "settings": self.show_settings_screen
        }
        
        # Clear current content frame
        self.clear_frame(self.visual_organizer_frame)

        # Call the appropriate page function
        if page == "organize":
            if self.folder_path_full:
                self.show_folder_preview([f for f in os.listdir(self.folder_path_full) if f.lower().endswith('.wav')][:10])
            else:
                self.pages[page]()
        elif page in self.pages:
            self.pages[page]()
        else:
            logger.warning(f"Página desconhecida: {page}")


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

    def save_api_key(self, key):
        """Salva chave API com validação melhorada"""
        key = key.strip()
        if not key or len(key) < 20:
            messagebox.showerror("Erro", "Chave de API inválida. Deve ter pelo menos 20 caracteres.")
            return

        try:
            with open(CONFIG_FILE, "w", encoding='utf-8') as f:
                f.write(key)
            messagebox.showinfo("Sucesso", f"Chave de API salva com segurança em:\n{APP_DATA_PATH}")
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
        self.set_ui_state("idle")

        # Mostrar prévia na tela principal
        self.show_folder_preview(wav_files[:10])

    def clear_folder_selection(self):
        """Limpa a pasta selecionada"""
        self.folder_path_full = ""
        self.folder_path_entry.configure(state="normal")
        self.folder_path_entry.delete(0, ctk.END)
        self.folder_path_entry.configure(state="readonly")
        self.start_button.configure(state="disabled")
        self.set_ui_state("idle")
        self.navigate_to("organize")

    def start_organization_thread(self):
        """Inicia análise com validações melhoradas"""
        if not self.api_configured:
            self.navigate_to('settings')
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
        self.set_ui_state("processing")
        
        # Inicializar ETA
        self.processing_start_time = time.time()
        self.files_processed = 0
        self.total_files_to_process = FileOperations.count_wav_files(self.folder_path_full)



        # Inicializar feedback visual
        self.execution_feedback = ExecutionFeedback(self.visual_organizer_frame)

        threading.Thread(target=self.run_organization_logic, daemon=True).start()

    def set_ui_state(self, state):
        """Gerencia centralizadamente o estado visual dos controles inferiores para evitar sobreposições"""
        try:
            # Limpar todos os itens da grid no controls_frame primeiro
            for widget in self.controls_frame.winfo_children():
                widget.grid_remove()
                
            if state == "idle":
                # Estado Inicial / Organizar
                self.folder_path_entry.grid(row=0, column=0, padx=(0, 8))
                self.browse_button.grid(row=0, column=1, padx=(0, 8))
                
                if hasattr(self, 'folder_path_full') and self.folder_path_full:
                    self.clear_button.grid(row=0, column=2, padx=(0, 8))
                    self.analysis_mode_combo.grid(row=0, column=3, padx=(0, 8))
                    self.start_button.grid(row=0, column=4, padx=(0, 5))
                else:
                    self.analysis_mode_combo.grid(row=0, column=2, padx=(0, 8))
                    self.start_button.grid(row=0, column=3, padx=(0, 5))
                
                self.folder_path_entry.configure(state="normal" if not self.folder_path_full else "readonly")
                self.start_button.configure(state="normal" if self.folder_path_full else "disabled")
                self.browse_button.configure(state="normal")
                self.analysis_mode_combo.configure(state="normal")
                
            elif state == "processing":
                # Durante processamento
                self.cancel_button.grid(row=0, column=0, padx=(10, 0))
                
            elif state == "review" or state == "report":
                # Tela de revisão ou relatório final onde precisam "Aplicar"
                self.apply_button.grid(row=0, column=0, padx=(0, 8))
                self.undo_button.grid(row=0, column=1, padx=(0, 8))
                self.start_button.grid(row=0, column=2, padx=(0, 5))
                
                self.start_button.configure(state="normal")
                self.apply_button.configure(state="normal")
                self.undo_button.configure(state="normal")
                
        except Exception as e:
            logger.error(f"Erro ao mudar estado da UI: {e}")

    def hide_apply_button(self):
        """Compatibilidade legado"""
        pass

    def show_apply_button(self):
        """Compatibilidade legado"""
        pass

    def request_cancel(self):
        """Solicita cancelamento do processamento"""
        if self.is_processing:
            self.cancel_requested = True
            self.update_status("⏹️ Cancelando... Aguarde a conclusão da operação atual.", 0)
            logger.info("Cancelamento solicitado pelo usuário")
            
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





    def test_api_key(self, key):
        """Testa a chave de API com melhor feedback"""
        if not key:
            messagebox.showerror("Erro", "Digite uma chave de API válida.")
            return

        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents="Teste de conexão. Responda apenas 'OK'.",
                config=types.GenerateContentConfig(max_output_tokens=10)
            )
            
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

            if not self.classifier.load_rules():
                return
            if not self.classifier.load_prompt():
                return

            # Configurar API
            if self.api_configured and os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                        api_key = f.read().strip()
                    self.api_key = api_key
                    self.classifier.api_key = api_key
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
            prefixo_sessao = self.classifier.find_common_prefix(list(todos_os_arquivos.values()))
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
                if self.classifier.should_discard(nome_limpo):
                    self.planned_actions.append(FileOperations.create_action('delete', caminho))
                    self.execution_feedback.add_file_entry(nome_original, "Descartados", "🗑️")
                    self.execution_feedback.update_stats('discarded')
                    continue

                # *** VERIFICAR SILÊNCIO PRIMEIRO - ANTES DA CLASSIFICAÇÃO ***
                if verificar_silencio:
                    if self.classifier.is_audio_silent(caminho, deep_check=verificacao_profunda):
                        self.planned_actions.append(FileOperations.create_action('delete', caminho))
                        self.execution_feedback.add_file_entry(nome_original, "Silencioso", "🔇")
                        self.execution_feedback.update_stats('discarded')
                        logger.info(f"Arquivo silencioso descartado: {nome_original}")
                        continue

                # Classificação local (só se não foi descartado por silêncio)
                categoria_encontrada = self.classifier.classify_locally(nome_final)
                if categoria_encontrada:
                    FileOperations.move_file(caminho, nome_final, categoria_encontrada, pasta_raiz, self.classifier.PARENT_FOLDER_MAP)
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

            # Etapa 6: Classificação com IA e Human-in-the-Loop
            ai_results_collected = {}

            if candidatos_para_ia and self.api_configured:
                total_ia = len(candidatos_para_ia)
                self.execution_feedback.update_activity(f"Consultando IA para {total_ia} arquivos...")
                self.update_status(f"Consultando IA para {total_ia} arquivos...", 0.7)

                # Processar em lotes menores para evitar timeout
                batch_size = 15
                processed_count = 0

                for i in range(0, total_ia, batch_size):
                    batch_files = list(candidatos_para_ia.keys())[i:i+batch_size]
                    batch_results = self.classifier.classify_with_ai(batch_files)

                    if batch_results:
                        for nome, categoria in batch_results.items():
                            processed_count += 1
                            final_progress = 0.7 + (processed_count / total_ia) * 0.25
                            
                            self.execution_feedback.update_activity(f"Processando resultado IA: {nome}")
                            self.update_status(f"Processando IA [{processed_count}/{total_ia}]: {nome}", final_progress)

                            caminho_original = candidatos_para_ia.get(nome)
                            if caminho_original:
                                ai_results_collected[nome] = {
                                    'categoria': categoria,
                                    'caminho': caminho_original
                                }

                    # Pausa entre lotes
                    time.sleep(0.5)

            # Ao inves de ir para o relatorio final direto, mostramos a tela de Revisão
            self.execution_feedback.update_activity("Análise concluída! Abrindo painel de revisão...")
            self.update_status("Análise concluída! Por favor, revise as classificações.", 1.0)
            time.sleep(1)
            
            # Se a IA não sugeriu nada, ir direto pro relatório
            if not ai_results_collected:
                self.set_ui_state("report")
                self.root.after(0, self.show_final_report)
            else:
                self.set_ui_state("review")
                self.root.after(0, lambda: self.show_review_screen(ai_results_collected))

        except Exception as e:
            error_msg = f"Aviso de IA: {str(e)}"
            self.update_status("Classificação IA falhou ou limite atingido. Agrupando desconhecidos...", 0.9)
            
            # FALLBACK DE IA: Adicionar os não classificados como 'Outros' para revisão manual
            if 'candidatos_para_ia' in locals() and candidatos_para_ia:
                for nome, caminho in candidatos_para_ia.items():
                    if nome not in ai_results_collected:
                       # Só adicionamos os que falharam na IA
                       ai_results_collected[nome] = {
                           'categoria': "Outros",
                           'caminho': caminho
                       }
            
            # Forçar tela de revisão com os 'Outros' para não inutilizar a ferramenta
            if ai_results_collected:
                # Mostrar o Toast em vez de error popup travando tudo
                self.root.after(0, lambda: ToastNotification(self.root, "Cota da IA atingida/Erro. Arquivos foram marcados como 'Outros' para revisão manual.", "warning"))
                self.set_ui_state("review")
                self.root.after(2000, lambda: self.show_review_screen(ai_results_collected))
            else:
                self.set_ui_state("report")
                self.root.after(0, self.show_final_report)

        finally:
            self.is_processing = False
            # self.enable_controls() # Movido para set_ui_state

    def processar_resultados_revisados(self, final_results):
        """Chamado pelo botão da tela de revisão após o usuário validar as categorias"""
        pasta_raiz = self.folder_path_full
        
        for nome, result in final_results.items():
            categoria = result['categoria']
            caminho_original = result['caminho']
            foi_alterado = result['foi_alterado']
            
            # Ensinar a IA se o usuário alterou ativamente a sugestão
            if foi_alterado and categoria != "Outros" and categoria != "[Descartar]":
                self.submit_suggestion_to_supabase(nome, categoria)
                
            # Adicionar a lista de ações que serao aplicadas
            if categoria == "[Descartar]":
                self.planned_actions.append(FileOperations.create_action('delete', caminho_original))
            elif categoria != "Outros":
                pasta_pai = self.classifier.PARENT_FOLDER_MAP.get(categoria, "Outros")
                categoria_path = os.path.join(pasta_raiz, pasta_pai, categoria)
                destino = os.path.join(categoria_path, nome)
                action = FileOperations.create_action('move', caminho_original, destino=destino, category=categoria, source_name=nome, target_name=nome)
                self.planned_actions.append(action)
            else:
                action = FileOperations.create_action('rename', caminho_original, target_name=nome)
                self.planned_actions.append(action)
                
        # Mostra o relatório final confirmando tudo
        self.show_final_report()



        # Remove enable_controls and map it to set_ui_state
    def enable_controls(self):
        self.set_ui_state("idle")


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
        self.set_ui_state("processing")

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
                        pasta_pai = self.classifier.PARENT_FOLDER_MAP.get(action['category'], "Outros")
                        categoria_path = os.path.join(self.folder_path_full, pasta_pai, action['category'])
                        destino = os.path.join(categoria_path, action['target_name'])
                        
                        # Executar movimento real
                        FileOperations.move_file(action['source_path'], action['target_name'], action['category'], self.folder_path_full, self.classifier.PARENT_FOLDER_MAP)
                        
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
                        FileOperations.rename_file(action['source_path'], action['target_name'])
                        
                        # Registrar para undo
                        undo_batch.append({
                            'type': 'rename',
                            'old_path': action['source_path'],
                            'new_path': new_path
                        })
                        
                        self.execution_feedback.add_file_entry(action['target_name'], "Renomeados", "📝")

                    success_count += 1
                    self.execution_feedback.update_stats('classified')
                    self.execution_feedback.update_global_progress(i + 1, len(self.planned_actions))

                except Exception as e:
                    error_count += 1
                    error_msg = f"Erro ao processar {action.get('source_name', 'arquivo')}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    self.execution_feedback.update_stats('discarded')
                    self.execution_feedback.update_global_progress(i + 1, len(self.planned_actions))

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



    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)




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
                    existing = self.supabase.table('ai_learning_rules')\
                        .select('id')\
                        .eq('keyword', keyword)\
                        .eq('category', category)\
                        .execute()
                    
                    if not existing.data:
                        # Submeter nova sugestão
                        self.supabase.table('ai_learning_rules').insert({
                            'keyword': keyword,
                            'category': category,
                            'user_id': self.auth.user.id if self.auth and self.auth.user else None,
                            'global_confidence': 1.0,
                            'is_approved': False
                        }).execute()

        except Exception as e:
            print(f"DEBUG: Erro ao submeter sugestão: {e}")

# Função principal

    def show_login_screen(self): screens.show_login_screen(self)
    def show_review_screen(self, candidates): screens.show_review_screen(self, candidates)
    def handle_login(self, email, password): screens.handle_login(self, email, password)
    def handle_register(self, email, password): screens.handle_register(self, email, password)
    def handle_logout(self): screens.handle_logout(self)
    
    def show_welcome_screen(self): screens.show_welcome_screen(self)
    def show_history_screen(self): screens.show_history_screen(self)
    def show_folder_preview(self, sample_files): screens.show_folder_preview(self, sample_files)
    def show_settings_screen(self): screens.show_settings_screen(self)
    def show_final_report(self): screens.show_final_report(self)
    def show_completion_screen(self, s, e, err): screens.show_completion_screen(self, s, e, err)

def main():
    root = ctk.CTk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
