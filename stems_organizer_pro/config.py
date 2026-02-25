"""
Stems Organizer PRO — Configurações centrais
Constantes, caminhos, credenciais, paleta de cores.
"""
import os

# --- VERSÃO E REPOSITÓRIO ---
CURRENT_VERSION = "1.7.8"
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

# --- PALETA DE CORES PREMIUM v1.5 ---
COLOR_BACKGROUND = "#0d0d0e"
COLOR_FRAME = "#1a1a2e"
COLOR_SURFACE = "#16213e"
COLOR_CARD = "#1e293b"
COLOR_TEXT = "#e2e8f0"
COLOR_TEXT_DIM = "#94a3b8"
COLOR_ACCENT_PURPLE = "#7c3aed"
COLOR_ACCENT_CYAN = "#06b6d4"
COLOR_BUTTON_HOVER = "#6d28d9"
COLOR_LIGHTNING = "#c4b5fd"
COLOR_SUCCESS = "#10b981"
COLOR_WARNING = "#f59e0b"
COLOR_ERROR = "#ef4444"
COLOR_SIDEBAR = "#111827"
COLOR_SIDEBAR_ACTIVE = "#1e1b4b"
COLOR_BORDER = "#334155"
COLOR_GLASS = "#1e293b"
