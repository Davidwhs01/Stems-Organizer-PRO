"""
Stems Organizer PRO — Configurações centrais
Constantes, caminhos, credenciais, paleta de cores.
"""
import os

# --- VERSÃO E REPOSITÓRIO ---
CURRENT_VERSION = "1.9.1"
GITHUB_REPO = "Davidwhs01/Stems-Organizer-PRO"

# --- CAMINHOS ---
APP_DATA_PATH = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'StemsOrganizerPro')
os.makedirs(APP_DATA_PATH, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DATA_PATH, 'api_key.txt')
SESSION_HISTORY_FILE = os.path.join(APP_DATA_PATH, 'session_history.json')

# --- URLS ---
RULES_URL = "https://gist.githubusercontent.com/Davidwhs01/ce7dac0b2e6619e5cac9a727269f3cf9/raw/rules.json"
PROMPT_URL = "https://gist.githubusercontent.com/Davidwhs01/b855b1965feaf5a79802e4ff4af3bad1/raw/master_prompt.txt"
LOGO_URL = "https://i.imgur.com/SRKbEpf.png"

# --- MISC ---
MIN_PREFIX_OCCURRENCES = 3

# --- CREDENCIAIS DO SUPABASE ---
SUPABASE_URL = os.environ.get(
    'SUPABASE_URL',
    "https://uebbdfgvqiwypnzobbnv.supabase.co"
)
SUPABASE_KEY = os.environ.get(
    'SUPABASE_KEY',
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVlYmJkZmd2cWl3eXBuem9iYm52Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE5MDQ3ODAsImV4cCI6MjA4NzQ4MDc4MH0.X_2w3Zqch7vKYnuOTcVr8TZGedhV38c-l9oE3QjnS5A"
)

# --- PALETA DE CORES PREMIUM v2.0 ---
COLOR_BACKGROUND = "#0a0a0b"
COLOR_FRAME = "#141422"
COLOR_SURFACE = "#16213e"
COLOR_CARD = "#1a1a2e"
COLOR_TEXT = "#e2e8f0"
COLOR_TEXT_DIM = "#8892a4"
COLOR_ACCENT_PURPLE = "#7c3aed"
COLOR_ACCENT_CYAN = "#06b6d4"
COLOR_BUTTON_HOVER = "#6d28d9"
COLOR_LIGHTNING = "#c4b5fd"
COLOR_SUCCESS = "#10b981"
COLOR_WARNING = "#f59e0b"
COLOR_ERROR = "#ef4444"
COLOR_SIDEBAR = "#0e0e14"
COLOR_SIDEBAR_ACTIVE = "#1a1a2e"
COLOR_BORDER = "#262640"
COLOR_GLASS = "#1e293b"

# --- SISTEMA DE FONTES (Windows 11 Native) ---
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_SEMIBOLD = "Segoe UI Semibold"
FONT_MONO = "Cascadia Code"

# Hierarquia tipográfica
FONT_HERO = (FONT_FAMILY, 36, "bold")        # Títulos de tela grande
FONT_TITLE = (FONT_FAMILY_SEMIBOLD, 22)      # Títulos de seção
FONT_SUBTITLE = (FONT_FAMILY, 15)            # Subtítulos
FONT_BODY = (FONT_FAMILY, 13)                # Texto padrão  
FONT_BODY_BOLD = (FONT_FAMILY_SEMIBOLD, 13)  # Texto enfatizado
FONT_CAPTION = (FONT_FAMILY, 11)             # Textos pequenos
FONT_CAPTION_DIM = (FONT_FAMILY, 10)         # Textos muito pequenos
FONT_BUTTON = (FONT_FAMILY_SEMIBOLD, 13)     # Botões
FONT_NAV = (FONT_FAMILY_SEMIBOLD, 14)        # Navegação sidebar
FONT_BRAND = (FONT_FAMILY_SEMIBOLD, 16)      # Brand name
FONT_CODE = (FONT_MONO, 10)                  # Código/atalhos
