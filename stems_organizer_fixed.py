import os
import re
import shutil
import sys
import threading
import json
import urllib.request
from collections import Counter
import time
import customtkinter as ctk
from tkinter import filedialog, messagebox
import google.generativeai as genai
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from supabase import create_client, Client
from PIL import Image, ImageDraw, ImageFont
import io

# --- Classe Helper para Tooltips ---
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
        self.widget.bind("<Destroy>", self._on_widget_destroy)  # FIX: Cleanup on destroy

    def _on_widget_destroy(self, event=None):
        """Limpa tooltip quando widget Ã© destruÃ­do"""
        self.hide_tooltip(None)

    def show_tooltip(self, event):
        if self.tooltip_window or not self.text or not self.widget.winfo_exists():
            return
        try:
            x, y, _, _ = self.widget.bbox("insert")
        except:
            x, y = 0, 0
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.attributes('-topmost', True)  # FIX: Keep on top
        
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
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            self.tooltip_window.destroy()
        self.tooltip_window = None

# --- CONFIGURAÃ‡Ã•ES ---
MIN_PREFIX_OCCURRENCES = 3
APP_DATA_PATH = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'StemsOrganizerPro')
os.makedirs(APP_DATA_PATH, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DATA_PATH, 'api_key.txt')
RULES_URL = "https://gist.githubusercontent.com/Davidwhs01/ce7dac0b2e6619e5cac9a727269f3cf9/raw/rules.json"
PROMPT_URL = "https://gist.githubusercontent.com/Davidwhs01/b855b1965feaf5a79802e4ff4af3bad1/raw/master_prompt.txt"
LOGO_URL = "https://i.imgur.com/xSHtj64.png"

# --- CREDENCIAIS DO SUPABASE ---
SUPABASE_URL = "https://mytywjgptinbgpapfpum.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im15dHl3amdwdGluYmdwYXBmcHVtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwOTkxNzgsImV4cCI6MjA3MTY3NTE3OH0.9bShsivDy88f2wReb8ggnluk8iGnZ1eA5ALMP5lGCRQ"

# --- PALETA DE CORES "PROD. AKI" ---
COLOR_BACKGROUND = "#1c1c1e"
COLOR_FRAME = "#2c2c2e"
COLOR_TEXT = "#E0E0E0"
COLOR_ACCENT_PURPLE = "#9c27b0"
COLOR_ACCENT_CYAN = "#00bcd4"
COLOR_BUTTON_HOVER = "#7b1fa2"
COLOR_LIGHTNING = "#e1bee7"
COLOR_SUCCESS = "#4CAF50"
COLOR_WARNING = "#FFC107"
COLOR_ERROR = "#F44336"

class ExecutionFeedback:
    """Classe para gerenciar feedback visual durante execuÃ§Ã£o"""
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.feedback_frame = None
        self.current_step = 0
        self.total_steps = 0
        self.stat_labels = {}
        self.stats = {}
        
    def start_feedback(self, total_steps):
        """Inicia o feedback visual"""
        self.total_steps = total_steps
        self.current_step = 0

        # Limpar frame pai de forma segura
        self.clear_parent_frame()

        # Criar frame de feedback
        self.feedback_frame = ctk.CTkFrame(self.parent_frame, fg_color="transparent")
        self.feedback_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # TÃ­tulo
        self.title_label = ctk.CTkLabel(
            self.feedback_frame,
            text="ðŸ“„ Processando seus arquivos...",
            font=("", 24, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        self.title_label.pack(pady=(40, 20))

        # Container principal
        main_container = ctk.CTkFrame(self.feedback_frame, fg_color=COLOR_FRAME)
        main_container.pack(fill="both", expand=True, padx=40, pady=20)

        # Frame de estatÃ­sticas em tempo real
        self.stats_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=20)

        # EstatÃ­sticas lado a lado
        stats_container = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        stats_container.pack()
        stats_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Cards de estatÃ­sticas
        self.create_stat_card(stats_container, "ðŸ“ Processados", "0", 0)
        self.create_stat_card(stats_container, "ðŸ¤– Classificados", "0", 1)
        self.create_stat_card(stats_container, "ðŸ—‘ï¸ Descartados", "0", 2)
        self.create_stat_card(stats_container, "â±ï¸ Tempo", "00:00", 3)

        # Frame de atividade atual
        activity_frame = ctk.CTkFrame(main_container, fg_color=COLOR_BACKGROUND)
        activity_frame.pack(fill="x", padx=20, pady=10)

        self.activity_label = ctk.CTkLabel(
            activity_frame,
            text="Iniciando anÃ¡lise...",
            font=("", 16),
            text_color=COLOR_TEXT
        )
        self.activity_label.pack(pady=15)

        # Lista de arquivos sendo processados
        self.file_list_frame = ctk.CTkScrollableFrame(
            main_container,
            fg_color=COLOR_BACKGROUND,
            height=200
        )
        self.file_list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Inicializar estatÃ­sticas
        self.stats = {
            'processed': 0,
            'classified': 0,
            'discarded': 0,
            'start_time': time.time()
        }

    def clear_parent_frame(self):
        """Limpa o frame pai de forma segura"""
        if not self.parent_frame.winfo_exists():
            return
        for widget in self.parent_frame.winfo_children():
            try:
                widget.destroy()
            except:
                pass

    def create_stat_card(self, parent, title, value, column):
        """Cria um card de estatÃ­stica"""
        card = ctk.CTkFrame(parent, fg_color=COLOR_BACKGROUND, width=150)
        card.grid(row=0, column=column, padx=10, pady=10, sticky="ew")
        card.pack_propagate(False)

        title_label = ctk.CTkLabel(card, text=title, font=("", 12), text_color="#888888")
        title_label.pack(pady=(10, 5))

        value_label = ctk.CTkLabel(card, text=value, font=("", 18, "bold"), text_color=COLOR_ACCENT_PURPLE)
        value_label.pack(pady=(0, 10))

        # Armazenar referÃªncia para atualizaÃ§Ã£o
        self.stat_labels[title] = value_label

    def update_activity(self, message):
        """Atualiza a atividade atual de forma thread-safe"""
        if hasattr(self, 'activity_label') and self.activity_label.winfo_exists():
            try:
                self.activity_label.configure(text=f"ðŸ“„ {message}")
            except:
                pass

    def add_file_entry(self, filename, category, icon):
        """Adiciona entrada de arquivo processado de forma thread-safe"""
        if not (hasattr(self, 'file_list_frame') and self.file_list_frame.winfo_exists()):
            return
        
        try:
            entry_frame = ctk.CTkFrame(self.file_list_frame, fg_color=COLOR_FRAME)
            entry_frame.pack(fill="x", padx=5, pady=2)

            # Icon e categoria
            icon_label = ctk.CTkLabel(entry_frame, text=icon, width=30)
            icon_label.pack(side="left", padx=(10, 5))

            category_label = ctk.CTkLabel(
                entry_frame,
                text=category,
                width=100,
                font=("", 12, "bold"),
                text_color=COLOR_ACCENT_CYAN
            )
            category_label.pack(side="left", padx=5)

            # Nome do arquivo
            filename_label = ctk.CTkLabel(
                entry_frame,
                text=filename[:50] + "..." if len(filename) > 50 else filename,  # FIX: Truncar nomes longos
                anchor="w",
                font=("", 12)
            )
            filename_label.pack(side="left", fill="x", expand=True, padx=10)

            # Auto-scroll para baixo de forma mais robusta
            def scroll_to_bottom():
                try:
                    if hasattr(self.file_list_frame, '_parent_canvas') and self.file_list_frame._parent_canvas.winfo_exists():
                        self.file_list_frame._parent_canvas.yview_moveto(1.0)
                except:
                    pass
            
            self.file_list_frame._parent_canvas.after(10, scroll_to_bottom)
        except:
            pass

    def update_stats(self, stat_type, increment=1):
        """Atualiza estatÃ­sticas de forma thread-safe"""
        if stat_type in self.stats:
            self.stats[stat_type] += increment

        # Atualizar labels de forma segura
        try:
            if "ðŸ“ Processados" in self.stat_labels and self.stat_labels["ðŸ“ Processados"].winfo_exists():
                self.stat_labels["ðŸ“ Processados"].configure(text=str(self.stats['processed']))
            if "ðŸ¤– Classificados" in self.stat_labels and self.stat_labels["ðŸ¤– Classificados"].winfo_exists():
                self.stat_labels["ðŸ¤– Classificados"].configure(text=str(self.stats['classified']))
            if "ðŸ—‘ï¸ Descartados" in self.stat_labels and self.stat_labels["ðŸ—‘ï¸ Descartados"].winfo_exists():
                self.stat_labels["ðŸ—‘ï¸ Descartados"].configure(text=str(self.stats['discarded']))
            if "â±ï¸ Tempo" in self.stat_labels and self.stat_labels["â±ï¸ Tempo"].winfo_exists():
                elapsed = int(time.time() - self.stats['start_time'])
                mins, secs = divmod(elapsed, 60)
                self.stat_labels["â±ï¸ Tempo"].configure(text=f"{mins:02d}:{secs:02d}")
        except:
            pass

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Stems Organizer Pro by Prod. Aki")
        self.root.geometry("1100x800")
        self.root.minsize(900, 600)  # FIX: Tamanho mÃ­nimo

        ctk.set_appearance_mode("Dark")
        self.root.configure(fg_color=COLOR_BACKGROUND)

        # FIX: Inicializar todas as variÃ¡veis antes de usar
        self.api_configured = False
        self.PARENT_FOLDER_MAP = {}
        self.LOCAL_CLASSIFICATION_RULES = {}
        self.planned_actions = []
        self.supabase = None
        self.master_prompt = ""
        self.folder_path_full = ""
        self.loading_angle = 0
        self.logo_image_pil = None
        self.execution_feedback = None
        self.is_processing = False
        self.logo_image = None
        self.logo_label = None

        # FIX: Inicializar Supabase de forma mais robusta
        self.init_supabase()
        
        self.create_widgets()
        self.load_api_key()

    def init_supabase(self):
        """Inicializa conexÃ£o com Supabase com tratamento de erro melhorado"""
        try:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            # Teste a conexÃ£o de forma mais leve
            test_response = self.supabase.table('rule_suggestions').select('id').limit(1).execute()
            print("DEBUG: Supabase connection successful.")
        except Exception as e:
            print(f"DEBUG: Supabase connection failed - {e}")
            self.supabase = None

    def create_widgets(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # Header frame
        header_frame = ctk.CTkFrame(self.root, fg_color=COLOR_FRAME, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        # Logo e tÃ­tulo
        left_header_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_header_frame.grid(row=0, column=0, padx=15, pady=10)

        # FIX: Download e carregamento de logo mais robusto
        self.load_logo(left_header_frame)

        title_label = ctk.CTkLabel(
            left_header_frame,
            text="Stems Organizer Pro",
            font=("", 20, "bold"),
            text_color=COLOR_TEXT
        )
        title_label.pack(side="left")

        # Controles de pasta e configuraÃ§Ãµes
        right_header_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_header_frame.grid(row=0, column=2, sticky="e", padx=15, pady=10)

        self.folder_path_entry = ctk.CTkEntry(
            right_header_frame,
            placeholder_text="Nenhuma pasta selecionada...",
            state="readonly",
            width=350
        )
        self.folder_path_entry.grid(row=0, column=0, padx=(0, 10))

        self.browse_button = ctk.CTkButton(
            right_header_frame,
            text="Selecionar Pasta",
            width=140,
            fg_color=COLOR_ACCENT_CYAN,
            hover_color="#0097a7",
            text_color="#111111",
            command=self.browse_folder
        )
        self.browse_button.grid(row=0, column=1, padx=(0, 10))

        self.settings_button = ctk.CTkButton(
            right_header_frame,
            text="âš™ï¸",
            width=40,
            fg_color=COLOR_FRAME,
            hover_color=COLOR_BUTTON_HOVER,
            command=self.open_settings_window
        )
        self.settings_button.grid(row=0, column=2)
        Tooltip(self.settings_button, "Abrir ConfiguraÃ§Ãµes e Ajuda")

        # Frame principal organizador visual
        self.visual_organizer_frame = ctk.CTkFrame(self.root, fg_color=COLOR_FRAME)
        self.visual_organizer_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        self.visual_organizer_frame.grid_columnconfigure(0, weight=1)
        self.visual_organizer_frame.grid_rowconfigure(0, weight=1)

        # Inicializar com tela de boas-vindas
        self.show_welcome_screen()

        # Footer frame
        footer_frame = ctk.CTkFrame(self.root, fg_color=COLOR_FRAME, corner_radius=0)
        footer_frame.grid(row=2, column=0, sticky="ew")
        footer_frame.grid_columnconfigure(0, weight=1)

        # Progress frame
        progress_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        progress_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        progress_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Pronto para iniciar.",
            text_color=COLOR_TEXT,
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            mode="determinate",
            progress_color=COLOR_ACCENT_PURPLE
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        # Controls frame
        self.controls_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        self.controls_frame.grid(row=0, column=1, rowspan=2, sticky="e", padx=15, pady=10)

        analysis_options = [
            "AnÃ¡lise RÃ¡pida (PadrÃ£o)",
            "AnÃ¡lise Profunda (Lenta)",
            "Nenhuma AnÃ¡lise (Mais RÃ¡pido)"
        ]
        self.analysis_mode_combo = ctk.CTkComboBox(
            self.controls_frame,
            values=analysis_options,
            button_color=COLOR_ACCENT_PURPLE,
            border_color=COLOR_ACCENT_PURPLE,
            dropdown_hover_color=COLOR_BUTTON_HOVER,
            state="readonly"
        )
        self.analysis_mode_combo.set(analysis_options[0])
        self.analysis_mode_combo.grid(row=0, column=0, padx=(0, 20))
        Tooltip(self.analysis_mode_combo, "Escolha o tipo de anÃ¡lise de Ã¡udio para arquivos silenciosos.")

        self.start_button = ctk.CTkButton(
            self.controls_frame,
            text="Analisar",
            font=("", 14, "bold"),
            fg_color=COLOR_ACCENT_PURPLE,
            hover_color=COLOR_BUTTON_HOVER,
            command=self.start_organization_thread,
            state="disabled",
            width=120
        )
        self.start_button.grid(row=0, column=1, padx=(0, 10))

        self.apply_button = ctk.CTkButton(
            self.controls_frame,
            text="Aplicar",
            font=("", 14, "bold"),
            fg_color=COLOR_ACCENT_CYAN,
            hover_color="#0097a7",
            text_color="#111111",
            command=self.start_apply_thread,
            width=120
        )
        # FIX: Aplicar botÃ£o inicialmente oculto
        # self.apply_button.grid_remove()

        # Credits
        credits_label = ctk.CTkLabel(
            footer_frame,
            text="Made by Prod. Aki",
            text_color="#555555",
            font=("", 10)
        )
        credits_label.grid(row=1, column=1, sticky="se", padx=15, pady=5)

    def load_logo(self, parent_frame):
        """Carrega logo de forma mais robusta"""
        logo_path = os.path.join(APP_DATA_PATH, "logo.png")
        
        try:
            # Tentar carregar logo local primeiro
            if os.path.exists(logo_path):
                self.logo_image_pil = Image.open(logo_path).resize((32, 32), Image.Resampling.LANCZOS)
            else:
                # Baixar logo se nÃ£o existir
                print("DEBUG: Baixando logo...")
                request = urllib.request.Request(LOGO_URL)
                request.add_header('User-Agent', 'StemsOrganizerPro/1.0')
                
                with urllib.request.urlopen(request, timeout=5) as response:
                    image_data = response.read()
                    self.logo_image_pil = Image.open(io.BytesIO(image_data)).resize((32, 32), Image.Resampling.LANCZOS)
                    
                    # Salvar localmente
                    with open(logo_path, "wb") as f:
                        f.write(image_data)

            # Criar widget de logo
            if self.logo_image_pil:
                self.logo_image = ctk.CTkImage(self.logo_image_pil, size=(32, 32))
                self.logo_label = ctk.CTkLabel(parent_frame, image=self.logo_image, text="")
                self.logo_label.pack(side="left", padx=(0, 10))
                
        except Exception as e:
            print(f"DEBUG: Logo load failed - {e}")

    def show_welcome_screen(self):
        """Mostra tela de boas-vindas inicial"""
        self.clear_frame(self.visual_organizer_frame)

        welcome_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        welcome_frame.pack(expand=True)

        # Logo grande
        if self.logo_image_pil:
            large_logo = self.logo_image_pil.resize((128, 128), Image.Resampling.LANCZOS)
            large_logo_ctk = ctk.CTkImage(large_logo, size=(128, 128))
            logo_label = ctk.CTkLabel(welcome_frame, image=large_logo_ctk, text="")
            logo_label.pack(pady=(50, 20))

        # TÃ­tulo de boas-vindas
        welcome_title = ctk.CTkLabel(
            welcome_frame,
            text="Bem-vindo ao Stems Organizer Pro",
            font=("", 28, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        welcome_title.pack(pady=(0, 10))

        # SubtÃ­tulo
        subtitle = ctk.CTkLabel(
            welcome_frame,
            text="Organize seus stems de mÃºsica automaticamente com IA",
            font=("", 16),
            text_color=COLOR_TEXT
        )
        subtitle.pack(pady=(0, 30))

        # InstruÃ§Ãµes
        instructions_frame = ctk.CTkFrame(welcome_frame, fg_color=COLOR_BACKGROUND)
        instructions_frame.pack(padx=40, pady=20)

        instructions = [
            "âž¡ï¸ 1. Selecione uma pasta contendo seus arquivos .wav",
            "âž¡ï¸ 2. Escolha o tipo de anÃ¡lise desejada",
            "âž¡ï¸ 3. Clique em 'Analisar' para ver o plano de organizaÃ§Ã£o",
            "âž¡ï¸ 4. Revise os resultados e clique em 'Aplicar'"
        ]

        for instruction in instructions:
            inst_label = ctk.CTkLabel(
                instructions_frame,
                text=instruction,
                font=("", 14),
                text_color=COLOR_TEXT,
                anchor="w"
            )
            inst_label.pack(pady=8, padx=30, anchor="w")

    def clear_frame(self, frame):
        """Destroi todos os widgets de um frame de forma segura"""
        if not frame.winfo_exists():
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
        """Efeito de flash no widget com verificaÃ§Ãµes de seguranÃ§a"""
        if not widget or not widget.winfo_exists():
            return

        try:
            original_color = widget.cget("fg_color")
        except:
            return

        def flash(count):
            if count <= 0 or not widget.winfo_exists():
                try:
                    if widget.winfo_exists():
                        widget.configure(fg_color=original_color)
                except:
                    pass
                return

            try:
                current_color = COLOR_LIGHTNING if widget.cget("fg_color") == original_color else original_color
                widget.configure(fg_color=current_color)
                self.root.after(80, flash, count - 1)
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
                    self.progress_bar.set(max(0, min(1, progress)))  # FIX: Clamp progress
            except:
                pass
        
        if self.root.winfo_exists():
            self.root.after(0, _update)

    def load_rules_from_sources(self):
        """Carrega regras com melhor tratamento de erro"""
        try:
            # Carregar regras base
            request = urllib.request.Request(RULES_URL)
            request.add_header('User-Agent', 'StemsOrganizerPro/1.0')

            with urllib.request.urlopen(request, timeout=15) as response:  # FIX: Timeout aumentado
                data = json.loads(response.read().decode('utf-8'))
                self.PARENT_FOLDER_MAP = data.get("parent_folder_map", {})
                self.LOCAL_CLASSIFICATION_RULES = data.get("local_classification_rules", {})
                print(f"DEBUG: Loaded {len(self.LOCAL_CLASSIFICATION_RULES)} rule categories")

        except Exception as e:
            self.update_status(f"Erro ao baixar regras base: {e}", 0)
            print(f"DEBUG: Rules loading failed - {e}")
            # FIX: Regras de fallback mais completas
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
                    resultados = json.loads(json_match.group(0))

                # Validar e corrigir categorias
                valid_categories = set(valid_categories_list.replace(" ", "").split(','))
                resultados_validados = {}
                
                for nome, categoria in resultados.items():
                    # Limpar nome do arquivo
                    nome_limpo = nome.strip().strip('"')
                    categoria_limpa = categoria.strip().strip('"')
                    
                    # Verificar se categoria Ã© vÃ¡lida
                    if categoria_limpa not in valid_categories:
                        # Tentar mapear categorias similares
                        categoria_mapeada = self.map_similar_category(categoria_limpa, valid_categories)
                        categoria_limpa = categoria_mapeada if categoria_mapeada else "Outros"
                    
                    resultados_validados[nome_limpo] = categoria_limpa

                print(f"DEBUG: IA classificou {len(resultados_validados)} arquivos com sucesso")
                return resultados_validados

            except json.JSONDecodeError as e:
                print(f"DEBUG: Erro JSON na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                print(f"DEBUG: Tentativa {attempt + 1} de chamada Ã  IA falhou: {e}")
                if "quota" in str(e).lower() or "rate" in str(e).lower():
                    print("DEBUG: Rate limit atingido, aguardando...")
                    time.sleep(3)
                elif attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    print("DEBUG: Todas as tentativas de IA falharam, usando fallback")
                    return {nome: "Outros" for nome in nomes_arquivos}

        return {}

    def map_similar_category(self, categoria, valid_categories):
        """Mapeia categorias similares para categorias vÃ¡lidas"""
        categoria_lower = categoria.lower()
        
        # Mapeamentos comuns
        mappings = {
            'drum': 'Drums',
            'drums': 'Drums',
            'percussion': 'Perc',
            'percussao': 'Perc',
            'guitar': 'GTRs',
            'guitars': 'GTRs',
            'gtr': 'GTRs',
            'voice': 'Vocal',
            'vocals': 'Vocal',
            'vox': 'Vocal',
            'synth': 'Synth',
            'synthesizer': 'Synth',
            'keys': 'Piano',
            'keyboard': 'Piano',
            'effect': 'Fx',
            'effects': 'Fx',
            'string': 'Orchestra',
            'strings': 'Orchestra',
            'pad': 'Pad',
            'pads': 'Pad',
            'bass': 'Bass',
            'baixo': 'Bass'
        }
        
        # Procurar mapeamento direto
        if categoria_lower in mappings:
            return mappings[categoria_lower]
        
        # Procurar substring
        for key, value in mappings.items():
            if key in categoria_lower or categoria_lower in key:
                return value
                
        return None

    def submit_suggestion_to_supabase(self, nome_arquivo, categoria):
        """Submete sugestÃ£o ao Supabase com extraÃ§Ã£o de keyword inteligente"""
        if not self.supabase:
            return

        try:
            # 1. Limpeza e ExtraÃ§Ã£o da Keyword
            clean_name, _ = os.path.splitext(nome_arquivo)
            
            # Remove a prÃ³pria categoria e termos comuns para evitar keywords redundantes
            to_remove = [categoria.lower()] + ['audio', 'stem', 'track', 'sound', 'sample', 'loop', 'wav', 'file']
            keyword_base = clean_name.lower()
            
            for term in to_remove:
                keyword_base = keyword_base.replace(term, '')
                
            # Limpeza final com regex para manter apenas letras, nÃºmeros e espaÃ§os
            keyword = re.sub(r'[^a-zA-Z0-9\s-]', ' ', keyword_base)
            keyword = re.sub(r'\s+', ' ', keyword).strip()
            
            if not keyword or len(keyword) < 2:
                print(f"DEBUG Supabase: Keyword invÃ¡lida ('{keyword}') para '{nome_arquivo}', pulando.")
                return

            print(f"DEBUG Supabase: Sugerindo Keyword: '{keyword}', Categoria: '{categoria}'")

            # 2. VerificaÃ§Ã£o de ExistÃªncia com timeout
            existing_response = self.supabase.table('rule_suggestions')\
                .select('id', 'votes')\
                .eq('keyword', keyword)\
                .eq('category', categoria)\
                .execute()
            
            # 3. Tomada de DecisÃ£o: Votar ou Inserir
            if existing_response.data:
                print(f"DEBUG Supabase: Regra existente encontrada. Incrementando voto.")
                # Usar RPC function se disponÃ­vel, senÃ£o atualizar diretamente
                try:
                    self.supabase.rpc('increment_vote', {
                        'keyword_text': keyword, 
                        'category_text': categoria
                    }).execute()
                except:
                    # Fallback: atualizar diretamente
                    current_votes = existing_response.data[0].get('votes', 0)
                    self.supabase.table('rule_suggestions')\
                        .update({'votes': current_votes + 1})\
                        .eq('keyword', keyword)\
                        .eq('category', categoria)\
                        .execute()
            else:
                print(f"DEBUG Supabase: Nova regra. Inserindo na tabela.")
                self.supabase.table('rule_suggestions').insert({
                    'keyword': keyword,
                    'category': categoria,
                    'votes': 1,
                    'is_approved': False
                }).execute()
                
        except Exception as e:
            # Falha silenciosa para nÃ£o interromper o fluxo principal
            print(f"DEBUG Supabase: Falha ao enviar sugestÃ£o para '{nome_arquivo}': {e}")


def main():
    """FunÃ§Ã£o principal com melhor tratamento de erros"""
    try:
        # Verificar dependÃªncias crÃ­ticas
        required_modules = ['customtkinter', 'google.generativeai', 'pydub', 'supabase', 'PIL']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            print(f"ERRO: MÃ³dulos necessÃ¡rios nÃ£o encontrados: {', '.join(missing_modules)}")
            print("Execute: pip install customtkinter google-generativeai pydub supabase pillow")
            return
        
        # Configurar CustomTkinter
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        # Criar e executar aplicaÃ§Ã£o
        root = ctk.CTk()
        
        # Configurar Ã­cone se disponÃ­vel
        try:
            if sys.platform.startswith('win'):
                root.iconbitmap(default=os.path.join(APP_DATA_PATH, "logo.ico"))
        except:
            pass
        
        # Configurar fechamento seguro
        def on_closing():
            try:
                root.quit()
                root.destroy()
            except:
                pass
            finally:
                sys.exit(0)
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Inicializar app
        app = App(root)
        
        # Executar loop principal
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\nPrograma interrompido pelo usuÃ¡rio")
        sys.exit(0)
    except Exception as e:
        print(f"ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        
        # Tentar mostrar erro em messagebox se possÃ­vel
        try:
            import tkinter as tk
            from tkinter import messagebox as mb
            root = tk.Tk()
            root.withdraw()
            mb.showerror("Erro Fatal", f"Erro inesperado:\n{str(e)}\n\nVerifique o console para mais detalhes.")
            root.destroy()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
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
            # FIX: Prompt de fallback mais robusto
            self.master_prompt = """
VocÃª Ã© um especialista em classificaÃ§Ã£o de stems musicais. Analise os nomes dos arquivos e classifique-os nas seguintes categorias:

CATEGORIAS VÃLIDAS:
- Drums: Elementos de bateria (kick, snare, hihat, cymbal, tom, etc.)
- Bass: Elementos de baixo frequÃªncia (bass, sub, 808, low, etc.) 
- GTRs: Guitarras e instrumentos de corda (guitar, gtr, strum, chord, etc.)
- Vocal: Elementos vocais (vocal, voice, lead, harmony, choir, etc.)
- Synth: Sintetizadores (synth, lead, pluck, arp, etc.)
- Pad: Pads e atmosferas (pad, string, atmosphere, etc.)
- Orchestra: Instrumentos orquestrais (orchestra, violin, cello, brass, etc.)
- Piano: Piano e teclados (piano, keys, electric, etc.)
- Fx: Efeitos sonoros (fx, effect, ambient, riser, sweep, etc.)
- Perc: PercussÃ£o (perc, shaker, tambourine, conga, etc.)
- Outros: Arquivos que nÃ£o se encaixam em nenhuma categoria acima

ARQUIVOS PARA CLASSIFICAR:
{file_list}

INSTRUÃ‡Ã•ES:
1. Analise cada nome de arquivo cuidadosamente
2. Identifique palavras-chave que indiquem o tipo de instrumento/som
3. Classifique usando APENAS as categorias listadas acima
4. Retorne APENAS um JSON vÃ¡lido no formato: {{"nome_arquivo": "categoria"}}
5. NÃ£o adicione explicaÃ§Ãµes ou texto extra

EXEMPLO DE RESPOSTA:
{{"kick_01.wav": "Drums", "bass_line.wav": "Bass", "guitar_chord.wav": "GTRs"}}

Categorias vÃ¡lidas: {valid_categories_list}
"""
            return True

    def load_api_key(self):
        """Carrega chave API com validaÃ§Ã£o melhorada"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                    key = f.read().strip()
                    if key and len(key) > 20:  # FIX: ValidaÃ§Ã£o mais rigorosa
                        self.api_configured = True
                        print("DEBUG: API key loaded successfully")
                    else:
                        print("DEBUG: API key too short, marking as not configured")
            except Exception as e:
                print(f"DEBUG: Erro ao carregar API key: {e}")

    def save_api_key(self, key, popup):
        """Salva chave API com validaÃ§Ã£o melhorada"""
        key = key.strip()
        if not key or len(key) < 20:  # FIX: ValidaÃ§Ã£o mais rigorosa
            messagebox.showerror("Erro", "Chave de API invÃ¡lida. Deve ter pelo menos 20 caracteres.")
            return

        try:
            with open(CONFIG_FILE, "w", encoding='utf-8') as f:
                f.write(key)
            messagebox.showinfo("Sucesso", f"Chave de API salva com seguranÃ§a em:\n{APP_DATA_PATH}")
            popup.destroy()
            self.api_configured = True
        except Exception as e:
            messagebox.showerror("Erro", f"NÃ£o foi possÃ­vel salvar a chave:\n{e}")

    def browse_folder(self):
        """Seleciona pasta com validaÃ§Ã£o melhorada"""
        folder_selected = filedialog.askdirectory(title="Selecione a pasta com arquivos .wav")
        if not folder_selected or not os.path.exists(folder_selected):
            return

        # Verificar se hÃ¡ arquivos .wav na pasta
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

        # Mostrar prÃ©via na tela principal
        self.show_folder_preview(wav_files[:10])

    def show_folder_preview(self, sample_files):
        """Mostra prÃ©via dos arquivos na pasta selecionada"""
        self.clear_frame(self.visual_organizer_frame)

        preview_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        preview_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title = ctk.CTkLabel(
            preview_frame,
            text="ðŸ“ PrÃ©via dos arquivos encontrados",
            font=("", 20, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        title.pack(pady=(20, 15))

        files_frame = ctk.CTkScrollableFrame(preview_frame, fg_color=COLOR_BACKGROUND)
        files_frame.pack(fill="both", expand=True, padx=20)

        for file in sample_files:
            file_frame = ctk.CTkFrame(files_frame, fg_color=COLOR_FRAME)
            file_frame.pack(fill="x", padx=10, pady=5)

            file_icon = ctk.CTkLabel(file_frame, text="ðŸŽµ", width=30)
            file_icon.pack(side="left", padx=10)

            # FIX: Truncar nomes de arquivos muito longos
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
        """Inicia anÃ¡lise com validaÃ§Ãµes melhoradas"""
        if not self.api_configured:
            self.open_settings_window()
            return

        if self.is_processing:
            messagebox.showwarning("Aviso", "Uma anÃ¡lise jÃ¡ estÃ¡ em andamento.")
            return

        if not self.folder_path_full or not os.path.exists(self.folder_path_full):
            messagebox.showwarning("Aviso", "Selecione uma pasta vÃ¡lida primeiro.")
            return

        self.is_processing = True
        self.planned_actions = []
        self.hide_apply_button()

        # Desabilitar controles
        self.start_button.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.analysis_mode_combo.configure(state="disabled")

        # Inicializar feedback visual
        self.execution_feedback = ExecutionFeedback(self.visual_organizer_frame)

        threading.Thread(target=self.run_organization_logic, daemon=True).start()

    def hide_apply_button(self):
        """Esconde o botÃ£o aplicar"""
        try:
            self.apply_button.grid_remove()
        except:
            pass

    def show_apply_button(self):
        """Mostra o botÃ£o aplicar"""
        try:
            self.apply_button.grid(row=0, column=2, padx=(0, 0))
        except:
            pass

    def open_settings_window(self):
        """Janela de configuraÃ§Ãµes melhorada"""
        settings_win = ctk.CTkToplevel(self.root)
        settings_win.title("ConfiguraÃ§Ãµes - Stems Organizer Pro")
        settings_win.geometry("600x450")
        settings_win.transient(self.root)
        settings_win.grab_set()

        # FIX: Centralizar janela de forma mais robusta
        settings_win.update_idletasks()
        try:
            x = (settings_win.winfo_screenwidth() // 2) - (600 // 2)
            y = (settings_win.winfo_screenheight() // 2) - (450 // 2)
            settings_win.geometry(f"600x450+{x}+{y}")
        except:
            pass

        # FIX: Configurar protocolo de fechamento
        def on_closing():
            settings_win.grab_release()
            settings_win.destroy()
        
        settings_win.protocol("WM_DELETE_WINDOW", on_closing)

        tabview = ctk.CTkTabview(settings_win, fg_color=COLOR_FRAME)
        tabview.pack(fill="both", expand=True, padx=15, pady=15)

        # Tab API
        tabview.add("ðŸ”‘ Chave de API")
        api_tab = tabview.tab("ðŸ”‘ Chave de API")

        api_title = ctk.CTkLabel(
            api_tab,
            text="ConfiguraÃ§Ã£o da API do Google Gemini",
            font=("", 16, "bold")
        )
        api_title.pack(pady=(15, 10))

        api_desc = ctk.CTkLabel(
            api_tab,
            text="Para usar a classificaÃ§Ã£o por IA, vocÃª precisa de uma chave API do Google Gemini.\n"
                 "Obtenha gratuitamente em: https://aistudio.google.com/app/apikey",
            font=("", 12),
            text_color="#CCCCCC",
            wraplength=550
        )
        api_desc.pack(pady=(0, 15), padx=20)

        key_frame = ctk.CTkFrame(api_tab, fg_color=COLOR_BACKGROUND)
        key_frame.pack(fill="x", padx=20, pady=10)

        key_label = ctk.CTkLabel(key_frame, text="Chave de API:", font=("", 12))
        key_label.pack(anchor="w", padx=15, pady=(15, 5))

        key_entry = ctk.CTkEntry(key_frame, width=500, show="*", font=("", 12))
        key_entry.pack(padx=15, pady=(0, 15))

        # Carregar chave existente
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                    key_entry.insert(0, f.read().strip())
            except Exception:
                pass

        button_frame = ctk.CTkFrame(api_tab, fg_color="transparent")
        button_frame.pack(pady=15)

        test_button = ctk.CTkButton(
            button_frame,
            text="Testar API",
            fg_color=COLOR_ACCENT_PURPLE,
            hover_color=COLOR_BUTTON_HOVER,
            command=lambda: self.test_api_key(key_entry.get().strip())
        )
        test_button.pack(side="left", padx=(0, 10))

        save_button = ctk.CTkButton(
            button_frame,
            text="Salvar Chave",
            fg_color=COLOR_ACCENT_CYAN,
            hover_color="#0097a7",
            text_color="#111111",
            command=lambda: self.save_api_key(key_entry.get().strip(), settings_win)
        )
        save_button.pack(side="left")

        # Tab Ajuda
        tabview.add("â“ Ajuda")
        help_tab = tabview.tab("â“ Ajuda")

        help_scroll = ctk.CTkScrollableFrame(help_tab, fg_color="transparent")
        help_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        help_content = [
            ("ðŸŽ¯ Como usar", [
                "1. Configure sua chave API do Google Gemini (gratuita)",
                "2. Selecione uma pasta contendo arquivos .wav",
                "3. Escolha o tipo de anÃ¡lise desejada",
                "4. Clique em 'Analisar' para ver o plano de organizaÃ§Ã£o",
                "5. Revise os resultados e clique em 'Aplicar'"
            ]),
            ("ðŸ“‹ Tipos de AnÃ¡lise", [
                "â€¢ AnÃ¡lise RÃ¡pida: Verifica apenas volume mÃ©dio dos arquivos",
                "â€¢ AnÃ¡lise Profunda: Verifica volume mÃ©dio e picos de Ã¡udio",
                "â€¢ Nenhuma AnÃ¡lise: NÃ£o verifica arquivos silenciosos (mais rÃ¡pido)"
            ]),
            ("ðŸ“ Categorias", [
                "O programa organiza automaticamente em pastas como:",
                "â€¢ Drums (bateria)", "â€¢ Bass (baixo)", "â€¢ GTRs (guitarras)",
                "â€¢ Vocal", "â€¢ Synth (sintetizadores)", "â€¢ Pad", "â€¢ Orchestra",
                "â€¢ Piano", "â€¢ Fx (efeitos)", "â€¢ Perc (percussÃ£o)"
            ]),
            ("âš¡ Recursos", [
                "â€¢ ClassificaÃ§Ã£o inteligente com IA",
                "â€¢ Aprendizado colaborativo (melhor com uso)",
                "â€¢ DetecÃ§Ã£o automÃ¡tica de arquivos silenciosos",
                "â€¢ PrÃ©via antes de aplicar mudanÃ§as",
                "â€¢ Interface moderna e intuitiva"
            ])
        ]

        for section_title, items in help_content:
            section_frame = ctk.CTkFrame(help_scroll, fg_color=COLOR_BACKGROUND)
            section_frame.pack(fill="x", pady=(0, 15), padx=5)

            title_label = ctk.CTkLabel(
                section_frame,
                text=section_title,
                font=("", 14, "bold"),
                text_color=COLOR_ACCENT_CYAN
            )
            title_label.pack(anchor="w", padx=15, pady=(15, 10))

            for item in items:
                item_label = ctk.CTkLabel(
                    section_frame,
                    text=item,
                    font=("", 12),
                    anchor="w",
                    text_color=COLOR_TEXT,
                    wraplength=500
                )
                item_label.pack(anchor="w", padx=25, pady=2)

            ctk.CTkLabel(section_frame, text="").pack(pady=5)

        # Tab Sobre
        tabview.add("â„¹ï¸ Sobre")
        about_tab = tabview.tab("â„¹ï¸ Sobre")

        about_frame = ctk.CTkFrame(about_tab, fg_color="transparent")
        about_frame.pack(expand=True)

        if self.logo_image_pil:
            large_logo = self.logo_image_pil.resize((64, 64), Image.Resampling.LANCZOS)
            large_logo_ctk = ctk.CTkImage(large_logo, size=(64, 64))
            logo_about = ctk.CTkLabel(about_frame, image=large_logo_ctk, text="")
            logo_about.pack(pady=(30, 15))

        about_title = ctk.CTkLabel(
            about_frame,
            text="Stems Organizer Pro",
            font=("", 24, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        about_title.pack(pady=(0, 5))

        version_label = ctk.CTkLabel(
            about_frame,
            text="VersÃ£o 1.3 - Bug Fix Edition",
            font=("", 12),
            text_color="#888888"
        )
        version_label.pack(pady=(0, 20))

        about_text = """Organize automaticamente seus stems musicais com inteligÃªncia artificial.

ðŸŽ¼ Desenvolvido por Prod. Aki
ðŸ¤– Powered by Google Gemini AI
ðŸš€ Interface moderna com CustomTkinter
â˜ï¸ Aprendizado colaborativo com Supabase

Â© 2024 Prod. Aki - Todos os direitos reservados"""

        about_desc = ctk.CTkLabel(
            about_frame,
            text=about_text,
            font=("", 12),
            text_color=COLOR_TEXT,
            justify="center"
        )
        about_desc.pack(pady=20)

    def test_api_key(self, key):
        """Testa a chave de API com melhor feedback"""
        if not key:
            messagebox.showerror("Erro", "Digite uma chave de API vÃ¡lida.")
            return

        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.5-flash-lite")  # FIX: Usar modelo mais estÃ¡vel
            response = model.generate_content("Teste de conexÃ£o. Responda apenas 'OK'.", 
                                            generation_config={'max_output_tokens': 10})
            
            if response and response.text and 'ok' in response.text.lower():
                messagebox.showinfo("Sucesso", "âœ… Chave de API vÃ¡lida e funcionando!")
            else:
                messagebox.showerror("Erro", "âŒ Chave de API nÃ£o estÃ¡ funcionando corretamente.")
                
        except Exception as e:
            error_msg = str(e)
            if "quota" in error_msg.lower():
                messagebox.showerror("Erro", "âŒ Cota da API excedida. Tente novamente mais tarde.")
            elif "invalid" in error_msg.lower():
                messagebox.showerror("Erro", "âŒ Chave de API invÃ¡lida.")
            else:
                messagebox.showerror("Erro", f"âŒ Erro ao testar chave de API:\n{error_msg}")

    def run_organization_logic(self):
        """LÃ³gica principal de organizaÃ§Ã£o com feedback visual melhorado"""
        analysis_mode = self.analysis_mode_combo.get()
        verificar_silencio = analysis_mode != "Nenhuma AnÃ¡lise (Mais RÃ¡pido)"
        verificacao_profunda = analysis_mode == "AnÃ¡lise Profunda (Lenta)"

        try:
            # Inicializar feedback
            self.execution_feedback.start_feedback(100)

            # Etapa 1: ConfiguraÃ§Ã£o
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
                    print(f"DEBUG: Erro ao configurar API: {e}")
                    self.api_configured = False

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

            print(f"DEBUG: Found {len(todos_os_arquivos)} .wav files")

            # Etapa 3: Descobrir prefixo
            self.execution_feedback.update_activity("Analisando padrÃµes de nomenclatura...")
            prefixo_sessao = self.descobrir_prefixo_recorrente(list(todos_os_arquivos.values()))
            if prefixo_sessao:
                print(f"DEBUG: Found session prefix: {prefixo_sessao}")

            candidatos_para_analise = {}
            total_files = len(todos_os_arquivos)

            # Etapa 4: ClassificaÃ§Ã£o local
            self.execution_feedback.update_activity("Iniciando classificaÃ§Ã£o local...")
            
            for i, (caminho, nome_original) in enumerate(todos_os_arquivos.items()):
                progress = 0.15 + ((i + 1) / total_files) * 0.4
                
                # Atualizar feedback em tempo real
                self.execution_feedback.update_activity(f"Processando: {nome_original}")
                self.execution_feedback.update_stats('processed')
                self.update_status(f"Processando localmente [{i+1}/{total_files}]: {nome_original}", progress)

                nome_limpo = nome_original.strip()
                nome_final = nome_limpo[len(prefixo_sessao):].strip() if prefixo_sessao and nome_limpo.startswith(prefixo_sessao) else nome_limpo

                # Verificar se deve descartar
                if self.should_discard_file(nome_limpo):
                    self.armazenar_acao('delete', caminho)
                    self.execution_feedback.add_file_entry(nome_original, "Descartados", "ðŸ—‘ï¸")
                    self.execution_feedback.update_stats('discarded')
                    continue

                # ClassificaÃ§Ã£o local
                categoria_encontrada = self.classify_locally(nome_final)
                if categoria_encontrada:
                    self.mover_arquivo(caminho, nome_final, categoria_encontrada, pasta_raiz, is_dry_run=True)
                    self.execution_feedback.add_file_entry(nome_final, categoria_encontrada, "ðŸ¤–")
                    self.execution_feedback.update_stats('classified')
                else:
                    candidatos_para_analise[nome_final] = caminho

                # Pequena pausa para nÃ£o sobrecarregar a UI
                if i % 10 == 0:
                    time.sleep(0.01)

            # Etapa 5: AnÃ¡lise de Ã¡udio
            candidatos_para_ia = {}
            if verificar_silencio and candidatos_para_analise:
                self.execution_feedback.update_activity("Analisando arquivos de Ã¡udio...")
                total_analise = len(candidatos_para_analise)

                for i, (nome, caminho) in enumerate(candidatos_para_analise.items()):
                    progress = 0.55 + ((i + 1) / total_analise) * 0.15
                    self.execution_feedback.update_activity(f"Analisando Ã¡udio: {nome}")
                    self.update_status(f"Analisando Ã¡udio [{i+1}/{total_analise}]: {nome}", progress)

                    if self.is_audio_insignificant(caminho, deep_check=verificacao_profunda):
                        self.armazenar_acao('delete', caminho)
                        self.execution_feedback.add_file_entry(nome, "Descartados", "ðŸ”‡")
                        self.execution_feedback.update_stats('discarded')
                    else:
                        candidatos_para_ia[nome] = caminho

                    if i % 5 == 0:
                        time.sleep(0.01)
            else:
                candidatos_para_ia = candidatos_para_analise

            # Etapa 6: ClassificaÃ§Ã£o com IA
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
                                self.execution_feedback.add_file_entry(nome, categoria, "ðŸ§ ")
                                self.execution_feedback.update_stats('classified')
                                self.submit_suggestion_to_supabase(nome, categoria)
                            else:
                                if caminho_original:
                                    self.renomear_arquivo_no_local(caminho_original, nome, is_dry_run=True)
                                    self.execution_feedback.add_file_entry(nome, "NÃ£o Classificados", "â“")

                    # Pausa entre lotes
                    time.sleep(0.5)

            # Finalizar
            self.execution_feedback.update_activity("AnÃ¡lise concluÃ­da! Preparando relatÃ³rio...")
            self.update_status("AnÃ¡lise concluÃ­da! Clique em 'Aplicar' para confirmar.", 1.0)

            # Aguardar um pouco para mostrar o status final
            time.sleep(1)

            # Mostrar relatÃ³rio final
            self.root.after(0, self.show_final_report)
            self.root.after(100, lambda: self.play_lightning_effect(self.start_button))

        except Exception as e:
            error_msg = f"Erro durante anÃ¡lise: {str(e)}"
            self.update_status(error_msg, 0)
            self.root.after(0, lambda: messagebox.showerror("Erro", error_msg))
            print(f"DEBUG: {error_msg}")

        finally:
            self.is_processing = False
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
        """Habilita os controles da UI e mostra o botÃ£o 'Aplicar' se necessÃ¡rio"""
        try:
            self.start_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.analysis_mode_combo.configure(state="normal")
            
            if self.planned_actions:
                self.show_apply_button()
        except:
            pass

    def show_final_report(self):
        """Mostra relatÃ³rio final melhorado"""
        self.clear_frame(self.visual_organizer_frame)

        report_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        report_frame.pack(fill="both", expand=True)
        report_frame.grid_columnconfigure(1, weight=1)
        report_frame.grid_rowconfigure(0, weight=1)

        # Painel de resumo
        summary_panel = ctk.CTkFrame(report_frame, fg_color=COLOR_FRAME, width=300)
        summary_panel.grid(row=0, column=0, sticky="ns", padx=(0, 15), pady=5)
        summary_panel.pack_propagate(False)

        ctk.CTkLabel(
            summary_panel,
            text="ðŸ“Š Resumo da AnÃ¡lise",
            font=("", 18, "bold"),
            text_color=COLOR_ACCENT_CYAN
        ).pack(pady=20)

        # EstatÃ­sticas
        stats_frame = ctk.CTkFrame(summary_panel, fg_color=COLOR_BACKGROUND)
        stats_frame.pack(fill="x", padx=15, pady=(0, 20))

        moved = sum(1 for action in self.planned_actions if action[0] == 'move')
        deleted = sum(1 for action in self.planned_actions if action[0] == 'delete')
        renamed = sum(1 for action in self.planned_actions if action[0] == 'rename')
        total = moved + deleted + renamed

        stats = [
            ("ðŸ“ Arquivos a Mover", moved, COLOR_ACCENT_PURPLE),
            ("ðŸ—‘ï¸ Arquivos a Deletar", deleted, COLOR_ERROR),
            ("âœï¸ Arquivos a Renomear", renamed, COLOR_WARNING),
            ("ðŸ“Š Total de OperaÃ§Ãµes", total, COLOR_ACCENT_CYAN)
        ]

        for label, value, color in stats:
            stat_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
            stat_frame.pack(fill="x", pady=5, padx=10)

            ctk.CTkLabel(stat_frame, text=label, anchor="w").pack(side="left")
            ctk.CTkLabel(
                stat_frame,
                text=str(value),
                font=("", 12, "bold"),
                text_color=color
            ).pack(side="right")

        # Painel de detalhes
        details_panel = ctk.CTkScrollableFrame(report_frame, fg_color=COLOR_FRAME)
        details_panel.grid(row=0, column=1, sticky="nsew", pady=5)

        # Organizar por categorias
        categories = {}
        for action in self.planned_actions:
            if action[0] == 'move':
                src, dest_folder, filename = action[1:]
                category = os.path.basename(dest_folder)
                if category not in categories:
                    categories[category] = []
                categories[category].append((filename, "ðŸ“"))
            elif action[0] == 'delete':
                src = action[1]
                filename = os.path.basename(src)
                if "Descartados" not in categories:
                    categories["Descartados"] = []
                categories["Descartados"].append((filename, "ðŸ—‘ï¸"))
            elif action[0] == 'rename':
                src, dest = action[1:]
                filename = os.path.basename(dest)
                if "Renomeados" not in categories:
                    categories["Renomeados"] = []
                categories["Renomeados"].append((filename, "âœï¸"))

        # Mostrar categorias
        for category, files in sorted(categories.items()):
            if not files:
                continue

            category_frame = ctk.CTkFrame(details_panel, fg_color="transparent")
            category_frame.pack(fill="x", pady=(15, 5), padx=10)

            header = ctk.CTkLabel(
                category_frame,
                text=f"ðŸ“‚ {category} ({len(files)} arquivos)",
                font=("", 16, "bold"),
                text_color=COLOR_ACCENT_CYAN,
                anchor="w"
            )
            header.pack(fill="x", pady=(0, 10))

            # Mostrar atÃ© 10 arquivos por categoria
            display_files = files[:10]
            for filename, icon in display_files:
                file_frame = ctk.CTkFrame(category_frame, fg_color=COLOR_BACKGROUND)
                file_frame.pack(fill="x", padx=15, pady=2)

                ctk.CTkLabel(file_frame, text=icon, width=25).pack(side="left", padx=5)
                
                # Truncar nomes muito longos
                display_name = filename if len(filename) <= 50 else filename[:47] + "..."
                ctk.CTkLabel(
                    file_frame,
                    text=display_name,
                    anchor="w",
                    font=("", 12)
                ).pack(side="left", fill="x", expand=True, padx=5, pady=8)

            if len(files) > 10:
                more_label = ctk.CTkLabel(
                    category_frame,
                    text=f"... e mais {len(files) - 10} arquivos",
                    font=("", 10),
                    text_color="#888888"
                )
                more_label.pack(padx=15, pady=5)

    def start_apply_thread(self):
        """Inicia aplicaÃ§Ã£o das mudanÃ§as"""
        if self.is_processing:
            messagebox.showwarning("Aviso", "Uma operaÃ§Ã£o jÃ¡ estÃ¡ em andamento.")
            return

        if not self.planned_actions:
            messagebox.showwarning("Aviso", "Nenhuma aÃ§Ã£o para aplicar.")
            return

        # Confirmar aÃ§Ãµes
        total_actions = len(self.planned_actions)
        moved = sum(1 for action in self.planned_actions if action[0] == 'move')
        deleted = sum(1 for action in self.planned_actions if action[0] == 'delete')
        renamed = sum(1 for action in self.planned_actions if action[0] == 'rename')

        confirm_msg = f"Confirma a aplicaÃ§Ã£o de {total_actions} operaÃ§Ãµes?\n\n"
        confirm_msg += f"â€¢ {moved} arquivos serÃ£o movidos\n"
        confirm_msg += f"â€¢ {deleted} arquivos serÃ£o deletados\n"
        confirm_msg += f"â€¢ {renamed} arquivos serÃ£o renomeados\n\n"
        confirm_msg += "Esta operaÃ§Ã£o nÃ£o pode ser desfeita!"

        if not messagebox.askyesno("Confirmar OperaÃ§Ãµes", confirm_msg):
            return

        self.is_processing = True
        self.start_button.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.analysis_mode_combo.configure(state="disabled")
        self.apply_button.configure(state="disabled")

        threading.Thread(target=self.apply_organization_logic, daemon=True).start()

    def apply_organization_logic(self):
        """Aplica as mudanÃ§as com feedback visual melhorado"""
        total_actions = len(self.planned_actions)
        if total_actions == 0:
            return

        # Inicializar feedback para aplicaÃ§Ã£o
        self.clear_frame(self.visual_organizer_frame)

        apply_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        apply_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title = ctk.CTkLabel(
            apply_frame,
            text="âš¡ Aplicando MudanÃ§as...",
            font=("", 24, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        title.pack(pady=(40, 20))

        progress_frame = ctk.CTkFrame(apply_frame, fg_color=COLOR_FRAME)
        progress_frame.pack(fill="x", padx=40, pady=20)

        current_action_label = ctk.CTkLabel(
            progress_frame,
            text="Preparando...",
            font=("", 14)
        )
        current_action_label.pack(pady=15)

        detailed_progress = ctk.CTkProgressBar(
            progress_frame,
            progress_color=COLOR_ACCENT_CYAN
        )
        detailed_progress.pack(fill="x", padx=20, pady=(0, 15))

        successful_actions = []
        failed_actions = []

        try:
            for i, action in enumerate(self.planned_actions):
                progress = (i + 1) / total_actions
                action_type = action[0]
                params = action[1:]

                # Atualizar UI de forma thread-safe
                def update_ui(msg, prog):
                    try:
                        if current_action_label.winfo_exists():
                            current_action_label.configure(text=msg)
                        if detailed_progress.winfo_exists():
                            detailed_progress.set(max(0, min(1, prog)))
                    except:
                        pass

                if action_type == 'move':
                    src, dest_folder, new_name = params
                    self.root.after(0, update_ui, f"Movendo [{i+1}/{total_actions}]: {new_name}", progress)
                    self.update_status(f"Movendo [{i+1}/{total_actions}]: {new_name}", progress)

                    try:
                        # Verificar se arquivo fonte ainda existe
                        if not os.path.exists(src):
                            raise FileNotFoundError(f"Arquivo fonte nÃ£o encontrado: {src}")
                        
                        os.makedirs(dest_folder, exist_ok=True)
                        dest_path = os.path.join(dest_folder, new_name)
                        
                        # Verificar se destino jÃ¡ existe
                        if os.path.exists(dest_path):
                            # Criar nome Ãºnico
                            base, ext = os.path.splitext(new_name)
                            counter = 1
                            while os.path.exists(dest_path):
                                new_name_unique = f"{base}_{counter}{ext}"
                                dest_path = os.path.join(dest_folder, new_name_unique)
                                counter += 1
                        
                        shutil.move(src, dest_path)
                        successful_actions.append(action)
                        
                    except Exception as e:
                        print(f"DEBUG: Error moving {src} - {e}")
                        failed_actions.append((action, str(e)))

                elif action_type == 'delete':
                    src, = params
                    filename = os.path.basename(src)
                    self.root.after(0, update_ui, f"Deletando [{i+1}/{total_actions}]: {filename}", progress)
                    self.update_status(f"Deletando [{i+1}/{total_actions}]: {filename}", progress)

                    try:
                        if os.path.exists(src):
                            os.remove(src)
                            successful_actions.append(action)
                        else:
                            # Arquivo jÃ¡ nÃ£o existe, considerar como sucesso
                            successful_actions.append(action)
                    except Exception as e:
                        print(f"DEBUG: Error deleting {src} - {e}")
                        failed_actions.append((action, str(e)))

                elif action_type == 'rename':
                    src, new_path = params
                    new_name = os.path.basename(new_path)
                    self.root.after(0, update_ui, f"Renomeando [{i+1}/{total_actions}]: {new_name}", progress)
                    self.update_status(f"Renomeando [{i+1}/{total_actions}]: {new_name}", progress)

                    try:
                        if not os.path.exists(src):
                            raise FileNotFoundError(f"Arquivo fonte nÃ£o encontrado: {src}")
                        
                        # Verificar se destino jÃ¡ existe
                        if os.path.exists(new_path) and new_path != src:
                            # Criar nome Ãºnico
                            dir_path = os.path.dirname(new_path)
                            base, ext = os.path.splitext(os.path.basename(new_path))
                            counter = 1
                            while os.path.exists(new_path):
                                new_name_unique = f"{base}_{counter}{ext}"
                                new_path = os.path.join(dir_path, new_name_unique)
                                counter += 1
                        
                        os.rename(src, new_path)
                        successful_actions.append(action)
                        
                    except Exception as e:
                        print(f"DEBUG: Error renaming {src} - {e}")
                        failed_actions.append((action, str(e)))

                # Pequena pausa para nÃ£o sobrecarregar o sistema
                time.sleep(0.02)

            # Finalizar
            success_count = len(successful_actions)
            fail_count = len(failed_actions)

            if fail_count == 0:
                self.update_status("Todas as alteraÃ§Ãµes aplicadas com sucesso!", 1.0)
                status_msg = "âœ… OperaÃ§Ã£o ConcluÃ­da com Sucesso!"
                status_color = COLOR_SUCCESS
            else:
                self.update_status(f"OperaÃ§Ã£o concluÃ­da com {fail_count} falhas.", 1.0)
                status_msg = f"âš ï¸ ConcluÃ­da com {fail_count} Falhas"
                status_color = COLOR_WARNING

            # Mostrar resultado final
            self.root.after(0, lambda: self.show_apply_results(successful_actions, failed_actions, status_msg, status_color))
            self.root.after(100, lambda: self.play_lightning_effect(self.apply_button if hasattr(self, 'apply_button') and self.apply_button.winfo_exists() else self.start_button))

        except Exception as e:
            error_msg = f"Erro durante aplicaÃ§Ã£o: {str(e)}"
            self.update_status(error_msg, 0)
            self.root.after(0, lambda: messagebox.showerror("Erro", error_msg))
            print(f"DEBUG: {error_msg}")

        finally:
            self.planned_actions = []
            self.hide_apply_button()
            self.is_processing = False

            # Reabilitar controles
            try:
                self.start_button.configure(state="normal")
                self.browse_button.configure(state="normal")
                self.analysis_mode_combo.configure(state="normal")
            except:
                pass

    def show_apply_results(self, successful_actions, failed_actions, status_msg, status_color):
        """Mostra resultados da aplicaÃ§Ã£o"""
        self.clear_frame(self.visual_organizer_frame)

        results_frame = ctk.CTkFrame(self.visual_organizer_frame, fg_color="transparent")
        results_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Status principal
        status_frame = ctk.CTkFrame(results_frame, fg_color=COLOR_FRAME)
        status_frame.pack(fill="x", pady=(20, 15))

        status_label = ctk.CTkLabel(
            status_frame,
            text=status_msg,
            font=("", 24, "bold"),
            text_color=status_color
        )
        status_label.pack(pady=25)

        # EstatÃ­sticas
        stats_container = ctk.CTkFrame(results_frame, fg_color=COLOR_FRAME)
        stats_container.pack(fill="x", pady=(0, 15))

        stats_inner = ctk.CTkFrame(stats_container, fg_color="transparent")
        stats_inner.pack(pady=20)

        # Cards de estatÃ­sticas
        col = 0
        success_card = ctk.CTkFrame(stats_inner, fg_color=COLOR_BACKGROUND)
        success_card.grid(row=0, column=col, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(success_card, text="âœ… Sucessos", font=("", 12, "bold"), text_color=COLOR_SUCCESS).pack(pady=(10, 5))
        ctk.CTkLabel(success_card, text=str(len(successful_actions)), font=("", 20, "bold")).pack(pady=(0, 10))
        col += 1

        if failed_actions:
            fail_card = ctk.CTkFrame(stats_inner, fg_color=COLOR_BACKGROUND)
            fail_card.grid(row=0, column=col, padx=10, pady=5, sticky="ew")
            ctk.CTkLabel(fail_card, text="âŒ Falhas", font=("", 12, "bold"), text_color=COLOR_ERROR).pack(pady=(10, 5))
            ctk.CTkLabel(fail_card, text=str(len(failed_actions)), font=("", 20, "bold")).pack(pady=(0, 10))
            col += 1

        total_card = ctk.CTkFrame(stats_inner, fg_color=COLOR_BACKGROUND)
        total_card.grid(row=0, column=col, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(total_card, text="ðŸ“Š Total", font=("", 12, "bold"), text_color=COLOR_ACCENT_PURPLE).pack(pady=(10, 5))
        ctk.CTkLabel(total_card, text=str(len(successful_actions) + len(failed_actions)), font=("", 20, "bold")).pack(pady=(0, 10))

        # Detalhes (se houver falhas)
        if failed_actions:
            details_frame = ctk.CTkFrame(results_frame, fg_color=COLOR_FRAME)
            details_frame.pack(fill="both", expand=True)

            ctk.CTkLabel(
                details_frame,
                text="âŒ OperaÃ§Ãµes que Falharam:",
                font=("", 16, "bold"),
                text_color=COLOR_ERROR
            ).pack(pady=(15, 10))

            failures_scroll = ctk.CTkScrollableFrame(details_frame, fg_color=COLOR_BACKGROUND, height=150)
            failures_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

            for action, error in failed_actions[:20]:  # Mostrar atÃ© 20 falhas
                fail_frame = ctk.CTkFrame(failures_scroll, fg_color=COLOR_FRAME)
                fail_frame.pack(fill="x", padx=5, pady=2)

                action_type = action[0]
                if action_type == 'move':
                    src, dest_folder, new_name = action[1:]
                    desc = f"Mover: {new_name}"
                elif action_type == 'delete':
                    src = action[1]
                    desc = f"Deletar: {os.path.basename(src)}"
                elif action_type == 'rename':
                    src, new_path = action[1:]
                    desc = f"Renomear: {os.path.basename(new_path)}"
                else:
                    desc = "OperaÃ§Ã£o desconhecida"

                ctk.CTkLabel(fail_frame, text="âŒ", width=30).pack(side="left", padx=5)
                
                desc_label = ctk.CTkLabel(
                    fail_frame, 
                    text=desc[:50] + "..." if len(desc) > 50 else desc, 
                    anchor="w"
                )
                desc_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        # BotÃµes de aÃ§Ã£o
        actions_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        actions_frame.pack(pady=15)

        new_analysis_btn = ctk.CTkButton(
            actions_frame,
            text="Nova AnÃ¡lise",
            fg_color=COLOR_ACCENT_PURPLE,
            hover_color=COLOR_BUTTON_HOVER,
            command=self.reset_for_new_analysis
        )
        new_analysis_btn.pack(side="left", padx=(0, 10))

        if failed_actions:
            retry_btn = ctk.CTkButton(
                actions_frame,
                text="Repetir Falhas",
                fg_color=COLOR_ACCENT_CYAN,
                hover_color="#0097a7",
                text_color="#111111",
                command=lambda: self.retry_failed_actions(failed_actions)
            )
            retry_btn.pack(side="left")

    def reset_for_new_analysis(self):
        """Reseta a interface para nova anÃ¡lise"""
        self.planned_actions = []
        self.folder_path_full = ""
        
        try:
            self.folder_path_entry.configure(state="normal")
            self.folder_path_entry.delete(0, ctk.END)
            self.folder_path_entry.insert(0, "Nenhuma pasta selecionada...")
            self.folder_path_entry.configure(state="readonly")
            self.start_button.configure(state="disabled")
        except:
            pass
            
        self.show_welcome_screen()
        self.update_status("Pronto para nova anÃ¡lise.", 0)

    def retry_failed_actions(self, failed_actions):
        """Tenta novamente as aÃ§Ãµes que falharam"""
        self.planned_actions = [action for action, error in failed_actions]
        self.start_apply_thread()

    def descobrir_prefixo_recorrente(self, nomes_de_arquivos):
        """Descobre prefixo recorrente com melhor detecÃ§Ã£o"""
        if not nomes_de_arquivos or len(nomes_de_arquivos) < MIN_PREFIX_OCCURRENCES:
            return None

        # PadrÃµes mais especÃ­ficos para detecÃ§Ã£o de prefixos
        patterns = [
            r'^([A-Za-z0-9]+[_\-])',  # Letras/nÃºmeros seguidos de separador
            r'^([^a-zA-Z0-9\s]{1,3})',  # SÃ­mbolos no inÃ­cio (atÃ© 3)
            r'^(\d+[\-_\.])',  # NÃºmeros seguidos de separador
            r'^([A-Za-z]{2,4}[_\-])',  # Letras curtas seguidas de separador
        ]

        all_prefixes = []

        for pattern in patterns:
            try:
                prefix_pattern = re.compile(pattern)
                prefixes = []

                for nome in nomes_de_arquivos:
                    nome = nome.strip()
                    if not nome:
                        continue
                        
                    match = prefix_pattern.match(nome)
                    if match:
                        prefixes.append(match.group(1))

                if prefixes:
                    prefix_count = Counter(prefixes)
                    most_common = prefix_count.most_common(1)
                    if most_common and most_common[0][1] >= MIN_PREFIX_OCCURRENCES:
                        # Verificar se o prefixo Ã© realmente Ãºtil
                        prefix = most_common[0][0]
                        coverage = most_common[0][1] / len(nomes_de_arquivos)
                        if coverage >= 0.3:  # Pelo menos 30% dos arquivos
                            all_prefixes.append((prefix, most_common[0][1], coverage))
            except re.error:
                continue

        # Retornar o prefixo com melhor cobertura
        if all_prefixes:
            return max(all_prefixes, key=lambda x: x[2])[0]

        return None

    def armazenar_acao(self, action_type, *params):
        """Armazena aÃ§Ã£o com validaÃ§Ã£o"""
        if action_type in ['move', 'delete', 'rename'] and params:
            # Verificar se aÃ§Ã£o jÃ¡ existe para evitar duplicatas
            new_action = (action_type, *params)
            if new_action not in self.planned_actions:
                self.planned_actions.append(new_action)

    def mover_arquivo(self, caminho_original, nome_final, categoria, pasta_raiz, is_dry_run):
        """Move arquivo com estrutura de pasta melhorada"""
        if not caminho_original or not os.path.exists(caminho_original):
            return False
            
        parent = self.PARENT_FOLDER_MAP.get(categoria)

        if parent:
            dest_folder = os.path.join(pasta_raiz, parent, categoria)
        else:
            dest_folder = os.path.join(pasta_raiz, categoria)

        if is_dry_run:
            self.armazenar_acao('move', caminho_original, dest_folder, nome_final)
            return True
        else:
            try:
                os.makedirs(dest_folder, exist_ok=True)
                dest_path = os.path.join(dest_folder, nome_final)
                
                # Verificar se destino jÃ¡ existe
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(nome_final)
                    counter = 1
                    while os.path.exists(dest_path):
                        new_name = f"{base}_{counter}{ext}"
                        dest_path = os.path.join(dest_folder, new_name)
                        counter += 1
                
                shutil.move(caminho_original, dest_path)
                return True
            except Exception as e:
                print(f"DEBUG: Erro ao mover {caminho_original}: {e}")
                return False

    def renomear_arquivo_no_local(self, caminho_original, nome_final, is_dry_run):
        """Renomeia arquivo com validaÃ§Ã£o melhorada"""
        if not caminho_original or not os.path.exists(caminho_original):
            return False

        pasta_original = os.path.dirname(caminho_original)
        novo_caminho = os.path.join(pasta_original, nome_final)

        # Evitar renomeaÃ§Ã£o desnecessÃ¡ria
        if os.path.basename(caminho_original) == nome_final:
            return True

        if is_dry_run:
            self.armazenar_acao('rename', caminho_original, novo_caminho)
            return True
        else:
            try:
                # Verificar se destino jÃ¡ existe
                if os.path.exists(novo_caminho):
                    base, ext = os.path.splitext(nome_final)
                    counter = 1
                    while os.path.exists(novo_caminho):
                        new_name = f"{base}_{counter}{ext}"
                        novo_caminho = os.path.join(pasta_original, new_name)
                        counter += 1
                
                os.rename(caminho_original, novo_caminho)
                return True
            except Exception as e:
                print(f"DEBUG: Erro ao renomear {caminho_original}: {e}")
                return False

    def is_audio_insignificant(self, audio_path, avg_threshold=-55, peak_threshold=-50, deep_check=False):
        """Verifica se Ã¡udio Ã© insignificante com melhor detecÃ§Ã£o"""
        try:
            # Verificar se arquivo existe e tem tamanho vÃ¡lido
            if not os.path.exists(audio_path):
                return True

            file_size = os.path.getsize(audio_path)
            if file_size < 1000:  # Menos que 1KB
                return True

            # Carregar Ã¡udio com timeout implÃ­cito
            audio = AudioSegment.from_wav(audio_path)

            # Verificar duraÃ§Ã£o muito curta
            if len(audio) < 100:  # Menos que 100ms
                return True

            # AnÃ¡lise bÃ¡sica - sÃ³ volume mÃ©dio
            avg_db = audio.dBFS
            
            # Verificar se Ã© completamente silencioso
            if avg_db == float('-inf') or avg_db < -80:
                return True
                
            if avg_db < avg_threshold:
                if not deep_check:
                    return True

                # AnÃ¡lise profunda - verificar picos tambÃ©m
                try:
                    max_db = audio.max_dBFS
                    if max_db < peak_threshold:
                        return True

                    # Verificar se hÃ¡ silÃªncio prolongado (mais que 80% do arquivo)
                    silent_ranges = audio.detect_silence(
                        min_silence_len=100, 
                        silence_thresh=avg_threshold
                    )
                    if silent_ranges:
                        total_silence = sum(end - start for start, end in silent_ranges)
                        silence_ratio = total_silence / len(audio)
                        return silence_ratio > 0.8
                        
                except Exception:
                    # Se anÃ¡lise profunda falhar, usar sÃ³ a bÃ¡sica
                    return True

            return False

        except CouldntDecodeError:
            print(f"DEBUG: Couldn't decode audio file {audio_path}")
            return True
        except Exception as e:
            print(f"DEBUG: Erro ao analisar Ã¡udio {audio_path}: {e}")
            return False

    def classificar_com_ia_mestre(self, nomes_arquivos):
        """Classifica com IA com melhor tratamento de erro e rate limiting"""
        if not self.api_configured or not nomes_arquivos or not self.master_prompt:
            print("DEBUG: IA nÃ£o configurada ou sem dados")
            return {}

        if len(nomes_arquivos) > 25:  # Limitar tamanho do lote
            print(f"DEBUG: Lote muito grande ({len(nomes_arquivos)}), limitando a 25")
            nomes_arquivos = nomes_arquivos[:25]

        valid_categories_list = "Drums, Bass, GTRs, Vocal, Synth, Pad, Orchestra, Piano, Fx, Perc, Outros"
        nomes_formatados = "\n".join(f'- "{nome}"' for nome in nomes_arquivos)

        prompt = self.master_prompt.format(
            valid_categories_list=valid_categories_list,
            file_list=nomes_formatados
        )

        max_retries = 2  # Reduzir tentativas
        for attempt in range(max_retries):
            try:
                # Usar modelo mais recente com configuraÃ§Ã£o otimizada
                generation_config = {
                    'temperature': 0.1,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 1024,  # Reduzir limite
                }

                model = genai.GenerativeModel(
                    "gemini-2.5-flash-lite",
                    generation_config=generation_config
                )

                response = model.generate_content(prompt)

                if not response or not response.text:
                    raise ValueError("Resposta vazia da IA")

                # Extrair JSON da resposta de forma mais robusta
                response_text = response.text.strip()
                
               # Procurar por JSON na resposta
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text)
                if not json_match:
                    # Tentar extrair linhas que parecem mapeamento
                    lines = response_text.split('\n')
                    json_obj = {}
                    for line in lines:
                        if ':' in line and '"' in line:
                            try:
                                # Extrair nome e categoria da linha
                                parts = line.split(':')
                                if len(parts) >= 2:
                                    nome = parts[0].strip().strip('",')
                                    categoria = parts[1].strip().strip('",')
                                    if nome and categoria:
                                        json_obj[nome] = categoria
                            except:
                                continue
                    
                    if json_obj:
                        resultados = json_obj
                    else:
                        raise json.JSONDecodeError("Nenhum JSON válido encontrado", response_text, 0)
                else:
                    resultados = json.loads(json_match.group(0))

                # Validar e corrigir categorias
                valid_categories = set(valid_categories_list.replace(" ", "").split(','))
                resultados_validados = {}
                
                for nome, categoria in resultados.items():
                    # Limpar nome do arquivo
                    nome_limpo = nome.strip().strip('"')
                    categoria_limpa = categoria.strip().strip('"')
                    
                    # Verificar se categoria é válida
                    if categoria_limpa not in valid_categories:
                        # Tentar mapear categorias similares
                        categoria_mapeada = self.map_similar_category(categoria_limpa, valid_categories)
                        categoria_limpa = categoria_mapeada if categoria_mapeada else "Outros"
                    
                    resultados_validados[nome_limpo] = categoria_limpa

                print(f"DEBUG: IA classificou {len(resultados_validados)} arquivos com sucesso")
                return resultados_validados

            except json.JSONDecodeError as e:
                print(f"DEBUG: Erro JSON na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                print(f"DEBUG: Tentativa {attempt + 1} de chamada à IA falhou: {e}")
                if "quota" in str(e).lower() or "rate" in str(e).lower():
                    print("DEBUG: Rate limit atingido, aguardando...")
                    time.sleep(3)
                elif attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    print("DEBUG: Todas as tentativas de IA falharam, usando fallback")
                    return {nome: "Outros" for nome in nomes_arquivos}

        return {}

    def map_similar_category(self, categoria, valid_categories):
        """Mapeia categorias similares para categorias válidas"""
        categoria_lower = categoria.lower()
        
        # Mapeamentos comuns
        mappings = {
            'drum': 'Drums',
            'drums': 'Drums',
            'percussion': 'Perc',
            'percussao': 'Perc',
            'guitar': 'GTRs',
            'guitars': 'GTRs',
            'gtr': 'GTRs',
            'voice': 'Vocal',
            'vocals': 'Vocal',
            'vox': 'Vocal',
            'synth': 'Synth',
            'synthesizer': 'Synth',
            'keys': 'Piano',
            'keyboard': 'Piano',
            'effect': 'Fx',
            'effects': 'Fx',
            'string': 'Orchestra',
            'strings': 'Orchestra',
            'pad': 'Pad',
            'pads': 'Pad',
            'bass': 'Bass',
            'baixo': 'Bass'
        }
        
        # Procurar mapeamento direto
        if categoria_lower in mappings:
            return mappings[categoria_lower]
        
        # Procurar substring
        for key, value in mappings.items():
            if key in categoria_lower or categoria_lower in key:
                return value
                
        return None

    def submit_suggestion_to_supabase(self, nome_arquivo, categoria):
        """Submete sugestão ao Supabase com extração de keyword inteligente"""
        if not self.supabase:
            return

        try:
            # 1. Limpeza e Extração da Keyword
            clean_name, _ = os.path.splitext(nome_arquivo)
            
            # Remove a própria categoria e termos comuns para evitar keywords redundantes
            to_remove = [categoria.lower()] + ['audio', 'stem', 'track', 'sound', 'sample', 'loop', 'wav', 'file']
            keyword_base = clean_name.lower()
            
            for term in to_remove:
                keyword_base = keyword_base.replace(term, '')
                
            # Limpeza final com regex para manter apenas letras, números e espaços
            keyword = re.sub(r'[^a-zA-Z0-9\s-]', ' ', keyword_base)
            keyword = re.sub(r'\s+', ' ', keyword).strip()
            
            if not keyword or len(keyword) < 2:
                print(f"DEBUG Supabase: Keyword inválida ('{keyword}') para '{nome_arquivo}', pulando.")
                return

            print(f"DEBUG Supabase: Sugerindo Keyword: '{keyword}', Categoria: '{categoria}'")

            # 2. Verificação de Existência com timeout
            existing_response = self.supabase.table('rule_suggestions')\
                .select('id', 'votes')\
                .eq('keyword', keyword)\
                .eq('category', categoria)\
                .execute()
            
            # 3. Tomada de Decisão: Votar ou Inserir
            if existing_response.data:
                print(f"DEBUG Supabase: Regra existente encontrada. Incrementando voto.")
                # Usar RPC function se disponível, senão atualizar diretamente
                try:
                    self.supabase.rpc('increment_vote', {
                        'keyword_text': keyword, 
                        'category_text': categoria
                    }).execute()
                except:
                    # Fallback: atualizar diretamente
                    current_votes = existing_response.data[0].get('votes', 0)
                    self.supabase.table('rule_suggestions')\
                        .update({'votes': current_votes + 1})\
                        .eq('keyword', keyword)\
                        .eq('category', categoria)\
                        .execute()
            else:
                print(f"DEBUG Supabase: Nova regra. Inserindo na tabela.")
                self.supabase.table('rule_suggestions').insert({
                    'keyword': keyword,
                    'category': categoria,
                    'votes': 1,
                    'is_approved': False
                }).execute()
                
        except Exception as e:
            # Falha silenciosa para não interromper o fluxo principal
            print(f"DEBUG Supabase: Falha ao enviar sugestão para '{nome_arquivo}': {e}")


def main():
    """Função principal com melhor tratamento de erros"""
    try:
        # Verificar dependências críticas
        required_modules = ['customtkinter', 'google.generativeai', 'pydub', 'supabase', 'PIL']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            print(f"ERRO: Módulos necessários não encontrados: {', '.join(missing_modules)}")
            print("Execute: pip install customtkinter google-generativeai pydub supabase pillow")
            return
        
        # Configurar CustomTkinter
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        # Criar e executar aplicação
        root = ctk.CTk()
        
        # Configurar ícone se disponível
        try:
            if sys.platform.startswith('win'):
                root.iconbitmap(default=os.path.join(APP_DATA_PATH, "logo.ico"))
        except:
            pass
        
        # Configurar fechamento seguro
        def on_closing():
            try:
                root.quit()
                root.destroy()
            except:
                pass
            finally:
                sys.exit(0)
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Inicializar app
        app = App(root)
        
        # Executar loop principal
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\nPrograma interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        
        # Tentar mostrar erro em messagebox se possível
        try:
            import tkinter as tk
            from tkinter import messagebox as mb
            root = tk.Tk()
            root.withdraw()
            mb.showerror("Erro Fatal", f"Erro inesperado:\n{str(e)}\n\nVerifique o console para mais detalhes.")
            root.destroy()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()