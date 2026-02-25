import os
import time
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox

from stems_organizer_pro.config import (
    COLOR_BACKGROUND, COLOR_FRAME, COLOR_ACCENT_CYAN, 
    COLOR_ACCENT_PURPLE, COLOR_TEXT, COLOR_TEXT_DIM, 
    COLOR_CARD, COLOR_BORDER, COLOR_BUTTON_HOVER, COLOR_SUCCESS, 
    COLOR_WARNING, COLOR_ERROR, CURRENT_VERSION, APP_DATA_PATH, CONFIG_FILE,
    COLOR_SURFACE, COLOR_SIDEBAR,
    FONT_HERO, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD,
    FONT_CAPTION, FONT_CAPTION_DIM, FONT_BUTTON, FONT_NAV, FONT_BRAND,
    FONT_CODE, FONT_FAMILY, FONT_FAMILY_SEMIBOLD
)
from stems_organizer_pro.notifications import ToastNotification
from stems_organizer_pro.history import SessionHistory

# ==========================================
# AUTH SCREENS
# ==========================================
def handle_login(app, email_entry, pass_entry, error_label, login_btn):
    email = email_entry.get().strip()
    password = pass_entry.get().strip()
    
    if not email or not password:
        error_label.configure(text="⚠️ Preencha email e senha.")
        return
        
    error_label.configure(text="⏳ Entrando...", text_color=COLOR_WARNING)
    login_btn.configure(state="disabled")
    app.root.update()
    
    success, err_msg = app.auth.login(email, password)
    
    if success:
        # Puxar a API key salva
        key = app.auth.fetch_user_api_key()
        if key:
            app.api_key = key
            app.classifier.api_key = key
            app.api_configured = True
        app.navigate_to('organize')
    else:
        error_label.configure(text=f"❌ Erro: {err_msg}", text_color=COLOR_ERROR)
        login_btn.configure(state="normal")

def handle_register(app, email_entry, pass_entry, error_label, reg_btn):
    email = email_entry.get().strip()
    password = pass_entry.get().strip()
    
    if not email or not password or len(password) < 6:
        error_label.configure(text="⚠️ Email e Senha (mín. 6 chars).", text_color=COLOR_ERROR)
        return
        
    error_label.configure(text="⏳ Criando conta...", text_color=COLOR_WARNING)
    reg_btn.configure(state="disabled")
    app.root.update()
    
    success, msg = app.auth.register(email, password)
    
    if success:
        error_label.configure(text=msg, text_color=COLOR_SUCCESS)
    else:
        error_label.configure(text=f"❌ {msg}", text_color=COLOR_ERROR)
    reg_btn.configure(state="normal")

def show_login_screen(app):
    """Mostra tela de Login/Cadastro com design sofisticado."""
    app.clear_frame(app.visual_organizer_frame)
    
    # Esconder sidebar se existir
    if hasattr(app, 'sidebar_frame') and app.sidebar_frame.winfo_viewable():
        app.sidebar_frame.pack_forget()

    login_container = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
    login_container.place(relx=0.5, rely=0.5, anchor="center")
    
    # Logo
    logo_source = getattr(app, 'logo_image_pil_full', None) or app.logo_image_pil
    if logo_source:
        large_logo = logo_source.copy()
        large_logo.thumbnail((90, 90), Image.Resampling.LANCZOS)
        w, h = large_logo.size
        large_logo_ctk = ctk.CTkImage(large_logo, size=(w, h))
        ctk.CTkLabel(login_container, image=large_logo_ctk, text="").pack(pady=(0, 20))
        
    ctk.CTkLabel(login_container, text="Stems Organizer PRO", font=("", 24, "bold"), text_color=COLOR_ACCENT_CYAN).pack(pady=(0, 5))
    ctk.CTkLabel(login_container, text="Faça login para continuar", font=("", 13), text_color=COLOR_TEXT_DIM).pack(pady=(0, 30))

    # Tabs Login/Register
    tabview = ctk.CTkTabview(login_container, width=350, height=350, corner_radius=12, fg_color=COLOR_FRAME, segmented_button_selected_color=COLOR_ACCENT_PURPLE, segmented_button_selected_hover_color=COLOR_BUTTON_HOVER)
    tabview.pack(padx=20, pady=10)
    
    tab_login = tabview.add("Entrar")
    tab_reg = tabview.add("Criar Conta")
    
    # ====== TAB LOGIN ======
    ctk.CTkLabel(tab_login, text="E-mail", font=("", 12, "bold"), anchor="w").pack(fill="x", padx=20, pady=(20, 5))
    email_login = ctk.CTkEntry(tab_login, placeholder_text="seu@email.com", height=40, font=("", 13))
    email_login.pack(fill="x", padx=20)
    
    ctk.CTkLabel(tab_login, text="Senha", font=("", 12, "bold"), anchor="w").pack(fill="x", padx=20, pady=(15, 5))
    pass_login = ctk.CTkEntry(tab_login, placeholder_text="••••••••", show="•", height=40, font=("", 13))
    pass_login.pack(fill="x", padx=20)
    
    err_login = ctk.CTkLabel(tab_login, text="", text_color=COLOR_ERROR, font=("", 11))
    err_login.pack(pady=10)
    
    btn_login = ctk.CTkButton(tab_login, text="ENTRAR", font=("", 14, "bold"), height=42, fg_color=COLOR_ACCENT_PURPLE, hover_color=COLOR_BUTTON_HOVER, command=lambda: handle_login(app, email_login, pass_login, err_login, btn_login))
    btn_login.pack(fill="x", padx=20, pady=(0, 10))
    
    def on_google_auth_done(success, err_msg):
        # Esta callbacck volta rodando numa background thread. Precisamos agendar na main thread
        app.root.after(0, lambda: _process_google_result(app, err_login, btn_google, success, err_msg))
            
    def _process_google_result(app, err_label, btn_google, success, err_msg):
        if success:
            err_label.configure(text="Sucesso! Redirecionando...", text_color=COLOR_SUCCESS)
            key = app.auth.fetch_user_api_key()
            if key:
                app.api_key = key
                app.classifier.api_key = key
                app.api_configured = True
            app.navigate_to('organize')
        else:
            err_label.configure(text=f"❌ Erro OAuth: {err_msg}", text_color=COLOR_ERROR)
            btn_google.configure(state="normal")
            btn_login.configure(state="normal")

    def handle_google_login():
        err_login.configure(text="⏳ Abra o navegador para entrar com o Google...", text_color=COLOR_WARNING)
        btn_google.configure(state="disabled")
        btn_login.configure(state="disabled")
        app.root.update()
        app.auth.login_with_google(on_google_auth_done)

    # Google Button
    btn_google = ctk.CTkButton(
        tab_login, 
        text="CONTINUAR COM O GOOGLE", 
        font=("", 13, "bold"), 
        height=38, 
        fg_color="#dd4b39", 
        text_color="white", 
        hover_color="#c23321",
        image=None,  # Pode ser adicionado icone do google depois
        command=handle_google_login
    )
    btn_google.pack(fill="x", padx=20, pady=(0, 20))
    
    pass_login.bind('<Return>', lambda e: handle_login(app, email_login, pass_login, err_login, btn_login))
    email_login.bind('<Return>', lambda e: pass_login.focus())
    
    # ====== TAB REGISTER ======
    ctk.CTkLabel(tab_reg, text="E-mail", font=("", 12, "bold"), anchor="w").pack(fill="x", padx=20, pady=(20, 5))
    email_reg = ctk.CTkEntry(tab_reg, placeholder_text="seu@email.com", height=40, font=("", 13))
    email_reg.pack(fill="x", padx=20)
    
    ctk.CTkLabel(tab_reg, text="Senha (mín. 6)", font=("", 12, "bold"), anchor="w").pack(fill="x", padx=20, pady=(15, 5))
    pass_reg = ctk.CTkEntry(tab_reg, placeholder_text="••••••••", show="•", height=40, font=("", 13))
    pass_reg.pack(fill="x", padx=20)
    
    err_reg = ctk.CTkLabel(tab_reg, text="", text_color=COLOR_ERROR, font=("", 11))
    err_reg.pack(pady=10)
    
    btn_reg = ctk.CTkButton(tab_reg, text="CRIAR CONTA", font=("", 14, "bold"), height=42, fg_color=COLOR_ACCENT_CYAN, text_color="black", hover_color="#0097a7", command=lambda: handle_register(app, email_reg, pass_reg, err_reg, btn_reg))
    btn_reg.pack(fill="x", padx=20, pady=(0, 20))

def handle_logout(app):
    app.auth.logout()
    app.api_key = ""
    app.classifier.api_key = ""
    app.api_configured = False
    
    if hasattr(app, 'sidebar_frame') and app.sidebar_frame.winfo_viewable():
        app.sidebar_frame.pack_forget()
        
    app.navigate_to('login')

def show_welcome_screen(app):
    """Mostra tela de boas-vindas com design premium"""
    app.clear_frame(app.visual_organizer_frame)

    welcome_frame = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
    welcome_frame.pack(expand=True)

    # Logo grande com efeito pulsante
    logo_source = getattr(app, 'logo_image_pil_full', None) or app.logo_image_pil
    if logo_source:
        large_logo = logo_source.copy()
        large_logo.thumbnail((120, 120), Image.Resampling.LANCZOS)
        w, h = large_logo.size
        large_logo_ctk = ctk.CTkImage(large_logo, size=(w, h))
        logo_label = ctk.CTkLabel(welcome_frame, image=large_logo_ctk, text="")
        logo_label.pack(pady=(30, 15))
        _pulse_widget(app, logo_label)

    # Título com animação de digitação
    title_text = "Stems Organizer Pro"
    welcome_title = ctk.CTkLabel(
        welcome_frame, text="", font=FONT_HERO, text_color=COLOR_ACCENT_CYAN
    )
    welcome_title.pack(pady=(0, 5))
    _type_animation(app, welcome_title, title_text)

    # Linha de gradiente animada
    gradient_line = ctk.CTkFrame(welcome_frame, fg_color=COLOR_ACCENT_PURPLE, height=2, width=200, corner_radius=2)
    gradient_line.pack(pady=(0, 8))

    # Subtítulo
    subtitle = ctk.CTkLabel(
        welcome_frame, text="Organize seus stems de música automaticamente com IA",
        font=FONT_SUBTITLE, text_color=COLOR_TEXT_DIM
    )
    subtitle.pack(pady=(0, 30))

    # Feature cards com design premium
    cards_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
    cards_frame.pack(padx=20, pady=10)

    features = [
        ("AI",  "IA Inteligente",    "Classificação automática com Gemini"),
        ("//",  "Super Rápido",      "Processamento paralelo de stems"),
        ("))",  "Análise de Áudio",  "Detecção de silêncio com FFmpeg"),
        ("<-",  "Desfazer",          "Reverta qualquer organização")
    ]

    for i, (icon, title, desc) in enumerate(features):
        card = ctk.CTkFrame(cards_frame, fg_color=COLOR_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER, width=180, height=130)
        card.grid(row=0, column=i, padx=8, pady=5)
        card.pack_propagate(False)

        # Ícone estilizado em vez de emoji
        icon_label = ctk.CTkLabel(
            card, text=icon, 
            font=(FONT_FAMILY_SEMIBOLD, 22, "bold"), 
            text_color=COLOR_ACCENT_PURPLE
        )
        icon_label.pack(pady=(18, 5))

        ctk.CTkLabel(card, text=title, font=FONT_BODY_BOLD, text_color=COLOR_TEXT).pack(pady=(0, 3))
        ctk.CTkLabel(card, text=desc, font=FONT_CAPTION_DIM, text_color=COLOR_TEXT_DIM, wraplength=150).pack()

        # Fade-in escalonado
        card.grid_remove()
        app.root.after(400 + i * 200, lambda c=card: c.grid())

    # Instrução de ação
    action_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
    action_frame.pack(pady=(30, 10))

    ctk.CTkLabel(
        action_frame, text="Selecione uma pasta ou arraste para começar",
        font=FONT_SUBTITLE, text_color=COLOR_TEXT_DIM
    ).pack()

def _type_animation(app, label, full_text, index=0):
    """Animação de digitação para labels"""
    if index <= len(full_text):
        try:
            if label.winfo_exists():
                label.configure(text=full_text[:index])
                app.root.after(45, lambda: _type_animation(app, label, full_text, index + 1))
        except:
            pass

def _pulse_widget(app, widget, growing=True, count=0):
    """Efeito pulsante sutil num widget"""
    if count >= 6:  # 3 ciclos
        return
    try:
        if not widget.winfo_exists():
            return
        # Simular pulse alterando padding
        pad = 5 if growing else 0
        widget.configure(pady=pad)
        app.root.after(400, lambda: _pulse_widget(app, widget, not growing, count + 1))
    except:
        pass


def show_folder_preview(app, sample_files):
    """Mostra prévia dos arquivos na pasta selecionada"""
    app.clear_frame(app.visual_organizer_frame)

    preview_frame = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
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

    total_files = app.count_wav_files()
    if len(sample_files) < total_files:
        more_label = ctk.CTkLabel(
            preview_frame,
            text=f"... e mais {total_files - len(sample_files)} arquivos",
            font=("", 12),
            text_color="#888888"
        )
        more_label.pack(pady=10)


def show_settings_screen(app):
    """Tela de configurações premium incorporada no app principal"""
    app.clear_frame(app.visual_organizer_frame)

    settings_frame = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
    settings_frame.pack(fill="both", expand=True)

    # Header
    header = ctk.CTkFrame(settings_frame, fg_color=COLOR_FRAME, corner_radius=0, height=60)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(header, text="⚙️  Configurações", font=("", 20, "bold"), text_color=COLOR_TEXT).pack(side="left", padx=20, pady=15)
    
    def on_logout_click():
        app.handle_logout()
        
    ctk.CTkButton(header, text="Sair da Conta", font=("", 12, "bold"), fg_color=COLOR_ERROR, hover_color="#c62828", width=100, height=28, command=on_logout_click).pack(side="right", padx=20)
    ctk.CTkLabel(header, text=f"v{CURRENT_VERSION}", font=("", 12), text_color=COLOR_TEXT_DIM).pack(side="right", padx=(0, 10))

    # Scrollable content
    content = ctk.CTkScrollableFrame(settings_frame, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=15, pady=15)

    # --- CARD 1: API Key ---
    api_card = ctk.CTkFrame(content, fg_color=COLOR_FRAME, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
    api_card.pack(fill="x", pady=(0, 12))

    api_header = ctk.CTkFrame(api_card, fg_color="transparent")
    api_header.pack(fill="x", padx=20, pady=(15, 5))
    ctk.CTkLabel(api_header, text="🔑  Chave de API", font=("", 16, "bold"), text_color=COLOR_ACCENT_CYAN).pack(side="left")

    api_status = "✅ Configurada" if app.api_configured else "⚠️ Não configurada"
    status_color = COLOR_SUCCESS if app.api_configured else COLOR_WARNING
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
    ctk.CTkButton(btn_frame, text="🧪 Testar", font=("", 13, "bold"), width=120, height=34, fg_color=COLOR_ACCENT_PURPLE, hover_color=COLOR_BUTTON_HOVER, corner_radius=8, command=lambda: app.test_api_key(key_entry.get().strip())).pack(side="left", padx=(0, 8))
    ctk.CTkButton(btn_frame, text="💾 Salvar", font=("", 13, "bold"), width=120, height=34, fg_color=COLOR_ACCENT_CYAN, hover_color="#0097a7", text_color="#111111", corner_radius=8, command=lambda: app.save_api_key(key_entry.get().strip())).pack(side="left")

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

    logo_source = getattr(app, 'logo_image_pil_full', None) or app.logo_image_pil
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


def show_review_screen(app, ai_results):
    """Mostra tela Human-in-the-Loop com visual interativo de pastas em tempo real"""
    app.clear_frame(app.visual_organizer_frame)
    all_categories = list(app.classifier.LOCAL_CLASSIFICATION_RULES.keys()) + ["Outros", "[Descartar]"]

    # Estado isolado para o review
    review_state = {
        'files': ai_results.copy(),
        'file_widgets': {},
        'category_frames': {},
        'counts': {cat: 0 for cat in all_categories}
    }

    # Contagem inicial
    for dados in review_state['files'].values():
        cat = dados['categoria']
        if cat not in review_state['counts']: cat = "Outros"
        review_state['counts'][cat] += 1

    review_frame = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
    review_frame.pack(fill="both", expand=True, padx=20, pady=10)
    review_frame.grid_columnconfigure(0, weight=1)
    review_frame.grid_columnconfigure(1, weight=2)
    review_frame.grid_rowconfigure(0, weight=1)

    # ============= PAINEL DE RESUMO (ESQUERDA) =============
    summary_panel = ctk.CTkFrame(review_frame, fg_color=COLOR_FRAME, corner_radius=15, width=280)
    summary_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15), pady=0)
    summary_panel.pack_propagate(False)

    title_frame = ctk.CTkFrame(summary_panel, fg_color=COLOR_ACCENT_CYAN, corner_radius=10)
    title_frame.pack(fill="x", padx=15, pady=(15, 20))
    ctk.CTkLabel(title_frame, text="🤖 Revisão de IA", font=("", 18, "bold"), text_color=COLOR_BACKGROUND).pack(pady=12)
    
    ctk.CTkLabel(summary_panel, text="Mova os arquivos entre as\npastas para corrigir a IA.", font=("", 12), text_color=COLOR_TEXT_DIM).pack(pady=(0, 20))

    # Atualiza as contagens no painel à esquerda
    count_vars = {}
    stats_frame = ctk.CTkScrollableFrame(summary_panel, fg_color="transparent")
    stats_frame.pack(fill="both", expand=True, padx=5, pady=5)
    
    def update_sidebar_counts():
        for widget in stats_frame.winfo_children():
            widget.destroy()
        
        for cat in all_categories:
            if review_state['counts'].get(cat, 0) > 0:
                row = ctk.CTkFrame(stats_frame, fg_color=COLOR_BACKGROUND, corner_radius=6)
                row.pack(fill="x", padx=10, pady=4)
                ctk.CTkLabel(row, text=f"📂 {cat}", font=("", 12), text_color=COLOR_TEXT).pack(side="left", padx=10, pady=8)
                ctk.CTkLabel(row, text=str(review_state['counts'][cat]), font=("", 14, "bold"), text_color=COLOR_ACCENT_PURPLE).pack(side="right", padx=10)
                
    update_sidebar_counts()

    # ============= PAINEL DE PASTAS INTERATIVAS (DIREITA) =============
    actions_panel = ctk.CTkFrame(review_frame, fg_color=COLOR_FRAME, corner_radius=15)
    actions_panel.grid(row=0, column=1, sticky="nsew", pady=0)

    actions_title = ctk.CTkFrame(actions_panel, fg_color=COLOR_ACCENT_PURPLE, corner_radius=10)
    actions_title.pack(fill="x", padx=15, pady=(15, 5))
    ctk.CTkLabel(actions_title, text="📂 Organização Sugerida (Arraste ou Selecione)", font=("", 16, "bold"), text_color="#FFFFFF").pack(pady=10)

    scroll = ctk.CTkScrollableFrame(actions_panel, fg_color="transparent")
    scroll.pack(fill="both", expand=True, pady=(0, 10))

    # Função que cria ou pega o frame da categoria
    def get_category_container(cat_name):
        if cat_name not in review_state['category_frames']:
            cat_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            cat_frame.pack(fill="x", pady=(10, 5), padx=5)
            
            header = ctk.CTkLabel(cat_frame, text=f"📂 {cat_name}", font=("", 14, "bold"), text_color=COLOR_ACCENT_CYAN)
            header.pack(pady=(0, 5), padx=10, anchor="w")
            
            content_frame = ctk.CTkFrame(cat_frame, fg_color="transparent")
            content_frame.pack(fill="x")
            
            review_state['category_frames'][cat_name] = {'main': cat_frame, 'header': header, 'content': content_frame}
        
        # Atualiza título com contagem
        count = review_state['counts'].get(cat_name, 0)
        review_state['category_frames'][cat_name]['header'].configure(text=f"📂 {cat_name} ({count} arquivos)")
        review_state['category_frames'][cat_name]['main'].pack(fill="x", pady=(10, 5), padx=5) if count > 0 else review_state['category_frames'][cat_name]['main'].pack_forget()
        
        return review_state['category_frames'][cat_name]['content']

    # Função para mover o botão visualmente
    def on_category_change(nome, nova_cat):
        antiga_cat = review_state['files'][nome]['categoria']
        if antiga_cat == nova_cat: return
        
        # Atualiza o estado
        review_state['files'][nome]['categoria'] = nova_cat
        review_state['files'][nome]['foi_alterado'] = True
        
        review_state['counts'][antiga_cat] -= 1
        review_state['counts'][nova_cat] += 1
        
        # Move o widget fisicamente repacking no novo container
        widget_dict = review_state['file_widgets'][nome]
        novo_container = get_category_container(nova_cat)
        
        widget_dict['frame'].pack_forget()
        widget_dict['frame'].pack(in_=novo_container, fill="x", padx=10, pady=2)
        
        # Otimiza: atualiza os headers das duas categorias afetadas
        get_category_container(antiga_cat)
        update_sidebar_counts()

    # Desenha os botões listados pelas pastas
    for nome, dados in review_state['files'].items():
        cat = dados['categoria']
        if cat not in all_categories: cat = "Outros"
        
        container = get_category_container(cat)
        
        row = ctk.CTkFrame(container, fg_color=COLOR_BACKGROUND, corner_radius=8)
        row.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(row, text="🎵", font=("", 14)).pack(side="left", padx=10, pady=10)
        disp_name = nome if len(nome)<=50 else nome[:47]+"..."
        ctk.CTkLabel(row, text=disp_name, font=("", 12), anchor="w").pack(side="left", fill="x", expand=True, padx=5)
        
        combo = ctk.CTkComboBox(row, values=all_categories, width=140, fg_color=COLOR_SURFACE, border_color=COLOR_BORDER, dropdown_fg_color=COLOR_CARD,
                                command=lambda val, n=nome: on_category_change(n, val))
        combo.pack(side="right", padx=15)
        combo.set(cat)
        
        review_state['file_widgets'][nome] = {'frame': row, 'combo': combo}

    # Hide empty categories initially
    for cat in all_categories:
        get_category_container(cat)

    def on_confirm():
        app.processar_resultados_revisados(review_state['files'])

    btn_frame = ctk.CTkFrame(summary_panel, fg_color="transparent")
    btn_frame.pack(fill="x", pady=(10, 20), side="bottom")
    
    ctk.CTkButton(
        btn_frame, text="✅ Confirmar", font=("", 15, "bold"), 
        height=45, fg_color=COLOR_SUCCESS, hover_color="#059669", text_color="white",
        command=on_confirm
    ).pack(padx=20, fill="x")


def show_final_report(app):
    """Mostra relatório final com design moderno"""
    app.clear_frame(app.visual_organizer_frame)

    report_frame = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
    report_frame.pack(fill="both", expand=True, padx=20, pady=10)
    report_frame.grid_columnconfigure(0, weight=1)
    report_frame.grid_columnconfigure(1, weight=2)
    report_frame.grid_rowconfigure(0, weight=1)

    # Contadores de ações
    move_count = len([a for a in app.planned_actions if a['action'] == 'move'])
    delete_count = len([a for a in app.planned_actions if a['action'] == 'delete'])
    rename_count = len([a for a in app.planned_actions if a['action'] == 'rename'])
    total_count = len(app.planned_actions)

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

    if not app.planned_actions:
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
            actions_of_type = [a for a in app.planned_actions if a['action'] == action_type]
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


def show_completion_screen(app, success_count, error_count, errors):
    """Mostra tela de conclusão"""
    app.clear_frame(app.visual_organizer_frame)

    # Salvar no histórico de sessões
    duration = time.time() - app.processing_start_time if app.processing_start_time else 0
    categories = len(set(a.get('category', '') for a in (app.undo_history[-1] if app.undo_history else []) if a.get('type') == 'move'))
    SessionHistory.add(app.folder_path_full, success_count, max(categories, 1), duration)

    # Toast de conclusão
    if error_count == 0:
        ToastNotification(app.root, f"✅ {success_count} arquivos organizados com sucesso!", "success")
    else:
        ToastNotification(app.root, f"⚠️ {success_count} OK, {error_count} erros", "warning")

    completion_frame = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
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
        command=app.reset_for_new_organization,
        width=200
    )
    new_button.pack(pady=30)


def show_history_screen(app):
    """Mostra tela de histórico de sessões"""
    app.clear_frame(app.visual_organizer_frame)

    # Header
    header = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
    header.pack(fill="x", padx=20, pady=(20, 10))

    ctk.CTkLabel(header, text="📊 Histórico de Sessões", font=("", 24, "bold"), text_color=COLOR_TEXT).pack(side="left")

    sessions = SessionHistory.load()

    if not sessions:
        empty_frame = ctk.CTkFrame(app.visual_organizer_frame, fg_color="transparent")
        empty_frame.pack(expand=True)
        ctk.CTkLabel(empty_frame, text="📭", font=("", 48)).pack(pady=(30, 10))
        ctk.CTkLabel(empty_frame, text="Nenhuma sessão registrada ainda.", font=("", 16), text_color=COLOR_TEXT_DIM).pack()
        ctk.CTkLabel(empty_frame, text="As sessões serão salvas automaticamente após cada organização.", font=("", 13), text_color=COLOR_TEXT_DIM).pack(pady=5)
        return

    # Lista de sessões
    scroll = ctk.CTkScrollableFrame(app.visual_organizer_frame, fg_color="transparent")
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
                command=lambda p=folder_path: app._reopen_folder(p)
            )
            reopen_btn.grid(row=0, column=2, rowspan=2, padx=(10, 0))


