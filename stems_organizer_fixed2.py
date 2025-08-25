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
        self.widget.bind("<Destroy>", self._on_widget_destroy)

    def _on_widget_destroy(self, event=None):
        """Limpa tooltip quando widget é destruído"""
        self.hide_tooltip(None)

    def show_tooltip(self, event):
        if self.tooltip_window or not self.text:
            return
        
        # Verificar se widget ainda existe
        try:
            if not self.widget.winfo_exists():
                return
        except:
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
            except:
                pass
            self.tooltip_window = None

# --- CONFIGURAÇÕES ---
MIN_PREFIX_OCCURRENCES = 3
APP_DATA_PATH = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'StemsOrganizerPro')
os.makedirs(APP_DATA_PATH, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DATA_PATH, 'api_key.txt')
RULES_URL = "https://gist.githubusercontent.com/Davidwhs01/ce7dac0b2e6619e5cac9a727269f3cf9/raw/rules.json"
PROMPT_URL = "https://gist.githubusercontent.com/Davidwhs01/b855b1965feaf5a79802e4ff4af3bad1/raw/master_prompt.txt"
LOGO_URL = "https://i.imgur.com/SRKbEpf.png"

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
    """Classe para gerenciar feedback visual durante execução"""
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

        # Título
        self.title_label = ctk.CTkLabel(
            self.feedback_frame,
            text="🎯 Processando seus arquivos...",
            font=("", 24, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        self.title_label.pack(pady=(40, 20))

        # Container principal
        main_container = ctk.CTkFrame(self.feedback_frame, fg_color=COLOR_FRAME)
        main_container.pack(fill="both", expand=True, padx=40, pady=20)

        # Frame de estatísticas em tempo real
        self.stats_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=20)

        # Estatísticas lado a lado
        stats_container = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        stats_container.pack()
        stats_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Cards de estatísticas
        self.create_stat_card(stats_container, "🎵 Processados", "0", 0)
        self.create_stat_card(stats_container, "🎤 Classificados", "0", 1)
        self.create_stat_card(stats_container, "🗑️ Descartados", "0", 2)
        self.create_stat_card(stats_container, "⏱️ Tempo", "00:00", 3)

        # Frame de atividade atual
        activity_frame = ctk.CTkFrame(main_container, fg_color=COLOR_BACKGROUND)
        activity_frame.pack(fill="x", padx=20, pady=10)

        self.activity_label = ctk.CTkLabel(
            activity_frame,
            text="Iniciando análise...",
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

        # Inicializar estatísticas
        self.stats = {
            'processed': 0,
            'classified': 0,
            'discarded': 0,
            'start_time': time.time()
        }

    def clear_parent_frame(self):
        """Limpa o frame pai de forma segura"""
        try:
            if not self.parent_frame.winfo_exists():
                return
        except:
            return
            
        for widget in self.parent_frame.winfo_children():
            try:
                widget.destroy()
            except:
                pass

    def create_stat_card(self, parent, title, value, column):
        """Cria um card de estatística"""
        card = ctk.CTkFrame(parent, fg_color=COLOR_BACKGROUND, width=150)
        card.grid(row=0, column=column, padx=10, pady=10, sticky="ew")
        card.pack_propagate(False)

        title_label = ctk.CTkLabel(card, text=title, font=("", 12), text_color="#888888")
        title_label.pack(pady=(10, 5))

        value_label = ctk.CTkLabel(card, text=value, font=("", 18, "bold"), text_color=COLOR_ACCENT_PURPLE)
        value_label.pack(pady=(0, 10))

        # Armazenar referência para atualização
        self.stat_labels[title] = value_label

    def update_activity(self, message):
        """Atualiza a atividade atual de forma thread-safe"""
        try:
            if hasattr(self, 'activity_label') and self.activity_label.winfo_exists():
                self.activity_label.configure(text=f"🎯 {message}")
        except:
            pass

    def add_file_entry(self, filename, category, icon):
        """Adiciona entrada de arquivo processado de forma thread-safe"""
        try:
            if not (hasattr(self, 'file_list_frame') and self.file_list_frame.winfo_exists()):
                return
        except:
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

            # Nome do arquivo (truncar se muito longo)
            display_name = filename[:50] + "..." if len(filename) > 50 else filename
            filename_label = ctk.CTkLabel(
                entry_frame,
                text=display_name,
                anchor="w",
                font=("", 12)
            )
            filename_label.pack(side="left", fill="x", expand=True, padx=10)

            # Auto-scroll para baixo de forma mais robusta
            def scroll_to_bottom():
                try:
                    if hasattr(self.file_list_frame, '_parent_canvas'):
                        canvas = self.file_list_frame._parent_canvas
                        if canvas and canvas.winfo_exists():
                            canvas.yview_moveto(1.0)
                except:
                    pass
            
            # Agendar scroll com delay
            if hasattr(self.file_list_frame, '_parent_canvas'):
                self.file_list_frame._parent_canvas.after(10, scroll_to_bottom)
        except Exception as e:
            print(f"DEBUG: Erro ao adicionar entrada de arquivo: {e}")

    def update_stats(self, stat_type, increment=1):
        """Atualiza estatísticas de forma thread-safe"""
        if stat_type in self.stats:
            self.stats[stat_type] += increment

        # Atualizar labels de forma segura
        try:
            label_map = {
                "🎵 Processados": 'processed',
                "🎤 Classificados": 'classified', 
                "🗑️ Descartados": 'discarded'
            }
            
            for label_key, stat_key in label_map.items():
                if label_key in self.stat_labels:
                    label = self.stat_labels[label_key]
                    if label.winfo_exists():
                        label.configure(text=str(self.stats[stat_key]))
            
            # Atualizar tempo
            if "⏱️ Tempo" in self.stat_labels:
                time_label = self.stat_labels["⏱️ Tempo"]
                if time_label.winfo_exists():
                    elapsed = int(time.time() - self.stats['start_time'])
                    mins, secs = divmod(elapsed, 60)
                    time_label.configure(text=f"{mins:02d}:{secs:02d}")
        except Exception as e:
            print(f"DEBUG: Erro ao atualizar stats: {e}")

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Stems Organizer Pro by Prod. Aki")
        self.root.geometry("1100x800")
        self.root.minsize(900, 600)

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

        # Inicializar Supabase
        self.init_supabase()
        
        self.create_widgets()
        self.load_api_key()

    def init_supabase(self):
        """Inicializa conexão com Supabase com tratamento de erro melhorado"""
        try:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            # Teste simples da conexão
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

        # Logo e título
        left_header_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_header_frame.grid(row=0, column=0, padx=15, pady=10)

        # Carregar logo
        self.load_logo(left_header_frame)

        title_label = ctk.CTkLabel(
            left_header_frame,
            text="Stems Organizer Pro",
            font=("", 20, "bold"),
            text_color=COLOR_TEXT
        )
        title_label.pack(side="left")

        # Controles de pasta e configurações
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
            text="⚙️",
            width=40,
            fg_color=COLOR_FRAME,
            hover_color=COLOR_BUTTON_HOVER,
            command=self.open_settings_window
        )
        self.settings_button.grid(row=0, column=2)
        Tooltip(self.settings_button, "Abrir Configurações e Ajuda")

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
            "Análise Rápida (Padrão)",
            "Análise Profunda (Lenta)",
            "Nenhuma Análise (Mais Rápido)"
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
        Tooltip(self.analysis_mode_combo, "Escolha o tipo de análise de áudio para arquivos silenciosos.")

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
        # Botão aplicar inicialmente oculto
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
                # Baixar logo se não existir
                print("DEBUG: Baixando logo...")
                request = urllib.request.Request(LOGO_URL)
                request.add_header('User-Agent', 'StemsOrganizerPro/1.0')
                
                with urllib.request.urlopen(request, timeout=10) as response:
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

        # Título de boas-vindas
        welcome_title = ctk.CTkLabel(
            welcome_frame,
            text="Bem-vindo ao Stems Organizer Pro",
            font=("", 28, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        welcome_title.pack(pady=(0, 10))

        # Subtítulo
        subtitle = ctk.CTkLabel(
            welcome_frame,
            text="Organize seus stems de música automaticamente com IA",
            font=("", 16),
            text_color=COLOR_TEXT
        )
        subtitle.pack(pady=(0, 30))

        # Instruções
        instructions_frame = ctk.CTkFrame(welcome_frame, fg_color=COLOR_BACKGROUND)
        instructions_frame.pack(padx=40, pady=20)

        instructions = [
            "➡️ 1. Selecione uma pasta contendo seus arquivos .wav",
            "➡️ 2. Escolha o tipo de análise desejada",
            "➡️ 3. Clique em 'Analisar' para ver o plano de organização",
            "➡️ 4. Revise os resultados e clique em 'Aplicar'"
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

    def open_settings_window(self):
        """Janela de configurações melhorada"""
        settings_win = ctk.CTkToplevel(self.root)
        settings_win.title("Configurações - Stems Organizer Pro")
        settings_win.geometry("600x450")
        settings_win.transient(self.root)
        settings_win.grab_set()

        # Centralizar janela de forma mais robusta
        settings_win.update_idletasks()
        try:
            x = (settings_win.winfo_screenwidth() // 2) - (600 // 2)
            y = (settings_win.winfo_screenheight() // 2) - (450 // 2)
            settings_win.geometry(f"600x450+{x}+{y}")
        except:
            pass

        # Configurar protocolo de fechamento
        def on_closing():
            settings_win.grab_release()
            settings_win.destroy()
        
        settings_win.protocol("WM_DELETE_WINDOW", on_closing)

        tabview = ctk.CTkTabview(settings_win, fg_color=COLOR_FRAME)
        tabview.pack(fill="both", expand=True, padx=15, pady=15)

        # Tab API
        tabview.add("🔑 Chave de API")
        api_tab = tabview.tab("🔑 Chave de API")

        api_title = ctk.CTkLabel(
            api_tab,
            text="Configuração da API do Google Gemini",
            font=("", 16, "bold")
        )
        api_title.pack(pady=(15, 10))

        api_desc = ctk.CTkLabel(
            api_tab,
            text="Para usar a classificação por IA, você precisa de uma chave API do Google Gemini.\n"
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
        tabview.add("❓ Ajuda")
        help_tab = tabview.tab("❓ Ajuda")

        help_scroll = ctk.CTkScrollableFrame(help_tab, fg_color="transparent")
        help_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        help_content = [
            ("🎯 Como usar", [
                "1. Configure sua chave API do Google Gemini (gratuita)",
                "2. Selecione uma pasta contendo arquivos .wav",
                "3. Escolha o tipo de análise desejada",
                "4. Clique em 'Analisar' para ver o plano de organização",
                "5. Revise os resultados e clique em 'Aplicar'"
            ]),
            ("🎹 Tipos de Análise", [
                "• Análise Rápida: Verifica apenas volume médio dos arquivos",
                "• Análise Profunda: Verifica volume médio e picos de áudio",
                "• Nenhuma Análise: Não verifica arquivos silenciosos (mais rápido)"
            ]),
            ("🎵 Categorias", [
                "O programa organiza automaticamente em pastas como:",
                "• Drums (bateria)", "• Bass (baixo)", "• GTRs (guitarras)",
                "• Vocal", "• Synth (sintetizadores)", "• Pad", "• Orchestra",
                "• Piano", "• Fx (efeitos)", "• Perc (percussão)"
            ]),
            ("⭐ Recursos", [
                "• Classificação inteligente com IA",
                "• Aprendizado colaborativo (melhor com uso)",
                "• Detecção automática de arquivos silenciosos",
                "• Prévia antes de aplicar mudanças",
                "• Interface moderna e intuitiva"
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
        tabview.add("ℹ️ Sobre")
        about_tab = tabview.tab("ℹ️ Sobre")

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
            text="Versão 1.4 - Optimized Edition",
            font=("", 12),
            text_color="#888888"
        )
        version_label.pack(pady=(0, 20))

        about_text = """Organize automaticamente seus stems musicais com inteligência artificial.

🎼 Desenvolvido por Prod. Aki
🤖 Powered by Google Gemini AI
💡 Interface moderna com CustomTkinter
☁️ Aprendizado colaborativo com Supabase

© 2024 Prod. Aki - Todos os direitos reservados"""

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
            self.execution_feedback.update_activity("Analisando padrões de nomenclatura...")
            prefixo_sessao = self.descobrir_prefixo_recorrente(list(todos_os_arquivos.values()))
            if prefixo_sessao:
                print(f"DEBUG: Found session prefix: {prefixo_sessao}")

            candidatos_para_analise = {}
            total_files = len(todos_os_arquivos)

            # Etapa 4: Classificação local
            self.execution_feedback.update_activity("Iniciando classificação local...")
            
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
                    self.execution_feedback.add_file_entry(nome_original, "Descartados", "🗑️")
                    self.execution_feedback.update_stats('discarded')
                    continue

                # Classificação local
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

            # Etapa 5: Análise de áudio
            candidatos_para_ia = {}
            if verificar_silencio and candidatos_para_analise:
                self.execution_feedback.update_activity("Analisando arquivos de áudio...")
                total_analise = len(candidatos_para_analise)

                for i, (nome, caminho) in enumerate(candidatos_para_analise.items()):
                    progress = 0.55 + ((i + 1) / total_analise) * 0.15
                    self.execution_feedback.update_activity(f"Analisando áudio: {nome}")
                    self.update_status(f"Analisando áudio [{i+1}/{total_analise}]: {nome}", progress)

                    if self.is_audio_insignificant(caminho, deep_check=verificacao_profunda):
                        self.armazenar_acao('delete', caminho)
                        self.execution_feedback.add_file_entry(nome, "Descartados", "🔇")
                        self.execution_feedback.update_stats('discarded')
                    else:
                        candidatos_para_ia[nome] = caminho

                    if i % 5 == 0:
                        time.sleep(0.01)
            else:
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
        """Mostra relatório final melhorado"""
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
            text="📊 Resumo da Análise",
            font=("", 18, "bold"),
            text_color=COLOR_ACCENT_CYAN
        ).pack(pady=(20, 15))

        # Contadores de ações
        move_count = len([a for a in self.planned_actions if a['action'] == 'move'])
        delete_count = len([a for a in self.planned_actions if a['action'] == 'delete'])
        rename_count = len([a for a in self.planned_actions if a['action'] == 'rename'])

        stats_items = [
            ("🎵 Arquivos a mover", move_count, COLOR_SUCCESS),
            ("🗑️ Arquivos a descartar", delete_count, COLOR_ERROR),
            ("📝 Arquivos a renomear", rename_count, COLOR_WARNING)
        ]

        for label, count, color in stats_items:
            stat_frame = ctk.CTkFrame(summary_panel, fg_color=COLOR_BACKGROUND)
            stat_frame.pack(fill="x", padx=15, pady=5)

            ctk.CTkLabel(stat_frame, text=label, anchor="w").pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(
                stat_frame, 
                text=str(count), 
                font=("", 14, "bold"),
                text_color=color
            ).pack(side="right", padx=10, pady=8)

        # Lista de ações detalhada
        actions_panel = ctk.CTkFrame(report_frame, fg_color=COLOR_FRAME)
        actions_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=5)

        ctk.CTkLabel(
            actions_panel,
            text="📋 Ações Planejadas",
            font=("", 18, "bold"),
            text_color=COLOR_ACCENT_CYAN
        ).pack(pady=(20, 15))

        # Frame scrollável para ações
        actions_scroll = ctk.CTkScrollableFrame(actions_panel, fg_color=COLOR_BACKGROUND)
        actions_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        if not self.planned_actions:
            no_actions_label = ctk.CTkLabel(
                actions_scroll,
                text="Nenhuma ação necessária.\nTodos os arquivos já estão organizados!",
                font=("", 14),
                text_color="#888888"
            )
            no_actions_label.pack(pady=50)
        else:
            # Agrupar ações por tipo
            actions_by_type = {}
            for action in self.planned_actions:
                action_type = action['action']
                if action_type not in actions_by_type:
                    actions_by_type[action_type] = []
                actions_by_type[action_type].append(action)

            for action_type, actions in actions_by_type.items():
                # Cabeçalho do grupo
                if action_type == 'move':
                    group_title = "📁 Arquivos a serem movidos"
                    icon = "➡️"
                elif action_type == 'delete':
                    group_title = "🗑️ Arquivos a serem descartados"
                    icon = "❌"
                else:
                    group_title = "📝 Arquivos a serem renomeados"
                    icon = "✏️"

                group_frame = ctk.CTkFrame(actions_scroll, fg_color=COLOR_FRAME)
                group_frame.pack(fill="x", pady=(10, 5))

                ctk.CTkLabel(
                    group_frame,
                    text=group_title,
                    font=("", 14, "bold"),
                    text_color=COLOR_ACCENT_PURPLE
                ).pack(pady=10)

                # Listar ações do grupo
                for action in actions:
                    action_frame = ctk.CTkFrame(actions_scroll, fg_color="#1a1a1c")
                    action_frame.pack(fill="x", padx=5, pady=2)

                    # Icon
                    ctk.CTkLabel(action_frame, text=icon, width=30).pack(side="left", padx=5)

                    # Detalhes da ação
                    if action_type == 'move':
                        detail_text = f"{action['source_name']} → {action['category']}/{action['target_name']}"
                    elif action_type == 'delete':
                        detail_text = f"Descartar: {os.path.basename(action['source_path'])}"
                    else:
                        detail_text = f"{os.path.basename(action['source_path'])} → {action['target_name']}"

                    ctk.CTkLabel(
                        action_frame,
                        text=detail_text,
                        anchor="w",
                        font=("", 12)
                    ).pack(side="left", fill="x", expand=True, padx=10, pady=8)

    def start_apply_thread(self):
        """Inicia aplicação das mudanças em thread separada"""
        if not self.planned_actions:
            messagebox.showinfo("Info", "Nenhuma ação para aplicar.")
            return

        if self.is_processing:
            messagebox.showwarning("Aviso", "Uma operação já está em andamento.")
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
                        
                        # Executar movimento real
                        self.mover_arquivo(
                            action['source_path'], 
                            action['target_name'], 
                            action['category'], 
                            self.folder_path_full, 
                            is_dry_run=False
                        )
                        
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
                        
                        self.execution_feedback.add_file_entry(filename, "Descartados", "🗑️")
                        
                    elif action['action'] == 'rename':
                        old_name = os.path.basename(action['source_path'])
                        self.execution_feedback.update_activity(f"Renomeando: {old_name}")
                        self.update_status(f"Renomeando [{i+1}/{len(self.planned_actions)}]: {old_name}", progress)
                        
                        # Executar renomeação real
                        self.renomear_arquivo_no_local(
                            action['source_path'], 
                            action['target_name'], 
                            is_dry_run=False
                        )
                        
                        self.execution_feedback.add_file_entry(action['target_name'], "Renomeados", "📝")

                    success_count += 1
                    self.execution_feedback.update_stats('classified')

                except Exception as e:
                    error_count += 1
                    error_msg = f"Erro ao processar {action.get('source_name', 'arquivo')}: {e}"
                    errors.append(error_msg)
                    print(f"DEBUG: {error_msg}")
                    self.execution_feedback.update_stats('discarded')

                # Pequena pausa
                time.sleep(0.05)

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
            print(f"DEBUG: {error_msg}")

        finally:
            self.is_processing = False
            self.planned_actions = []
            self.root.after(0, self.enable_controls_after_apply)

    def show_completion_screen(self, success_count, error_count, errors):
        """Mostra tela de conclusão"""
        self.clear_frame(self.visual_organizer_frame)

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
        """Verifica se arquivo de áudio é insignificante (silencioso/vazio)"""
        try:
            audio = AudioSegment.from_wav(arquivo_path)
            
            # Verificação básica - RMS médio
            rms = audio.rms
            if rms < 100:  # Limite para considerar silencioso
                return True

            # Verificação profunda se solicitada
            if deep_check:
                # Verificar picos
                raw_data = audio.get_array_of_samples()
                if raw_data:
                    max_amplitude = max(abs(x) for x in raw_data)
                    if max_amplitude < 1000:  # Limite para picos muito baixos
                        return True

            return False

        except (CouldntDecodeError, FileNotFoundError, Exception) as e:
            print(f"DEBUG: Erro ao analisar áudio {arquivo_path}: {e}")
            return False

    def classificar_com_ia_mestre(self, lista_arquivos):
        """Classifica arquivos usando IA com prompt mestre otimizado"""
        if not lista_arquivos or not self.api_configured:
            return {}

        try:
            # Preparar lista de categorias válidas
            valid_categories = list(self.LOCAL_CLASSIFICATION_RULES.keys()) + ["Outros"]
            
            # Preparar prompt
            files_str = "\n".join([f"- {arquivo}" for arquivo in lista_arquivos])
            
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
                print("DEBUG: Resposta vazia da IA")
                return {}

            # Parse do JSON
            response_text = response.text.strip()
            
            # Limpar resposta (remover markdown se presente)
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Validar resultado
            validated_result = {}
            for arquivo, categoria in result.items():
                if categoria in valid_categories:
                    validated_result[arquivo] = categoria
                else:
                    print(f"DEBUG: Categoria inválida '{categoria}' para arquivo '{arquivo}'")
                    validated_result[arquivo] = "Outros"

            print(f"DEBUG: IA classificou {len(validated_result)} arquivos")
            return validated_result

        except json.JSONDecodeError as e:
            print(f"DEBUG: Erro ao fazer parse do JSON da IA: {e}")
            print(f"DEBUG: Resposta da IA: {response.text if response else 'None'}")
            return {}
        except Exception as e:
            print(f"DEBUG: Erro geral na classificação por IA: {e}")
            return {}

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
