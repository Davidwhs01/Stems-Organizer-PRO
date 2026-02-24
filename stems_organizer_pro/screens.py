import os
import time
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox

from stems_organizer_pro.config import (
    COLOR_BACKGROUND, COLOR_FRAME, COLOR_ACCENT_CYAN, 
    COLOR_ACCENT_PURPLE, COLOR_TEXT, COLOR_TEXT_DIM, 
    COLOR_CARD, COLOR_BORDER, COLOR_BUTTON_HOVER, COLOR_SUCCESS, 
    COLOR_WARNING, COLOR_ERROR, CURRENT_VERSION, APP_DATA_PATH, CONFIG_FILE
)
from stems_organizer_pro.notifications import ToastNotification
from stems_organizer_pro.history import SessionHistory

def show_welcome_screen(app):
    """Mostra tela de boas-vindas animada"""
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
        # Efeito pulsante no logo
        app._pulse_widget(logo_label)

    # Título com animação de digitação
    title_text = "Stems Organizer Pro"
    welcome_title = ctk.CTkLabel(
        welcome_frame, text="", font=("", 32, "bold"), text_color=COLOR_ACCENT_CYAN
    )
    welcome_title.pack(pady=(0, 5))
    app._type_animation(welcome_title, title_text)

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
        app.root.after(400 + i * 200, lambda c=card: c.grid())

    # Instrução de ação
    action_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
    action_frame.pack(pady=(25, 10))

    ctk.CTkLabel(
        action_frame, text="📂  Selecione uma pasta ou arraste para começar",
        font=("", 14), text_color=COLOR_TEXT_DIM
    ).pack()

def _type_animation(app, label, full_text, index=0):
    """Animação de digitação para labels"""
    if index <= len(full_text):
        try:
            if label.winfo_exists():
                label.configure(text=full_text[:index])
                app.root.after(45, lambda: app._type_animation(label, full_text, index + 1))
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
        app.root.after(400, lambda: app._pulse_widget(widget, not growing, count + 1))
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


def open_settings_window(app):
    """Janela de configurações premium"""
    settings_win = ctk.CTkToplevel(app.root)
    settings_win.title("⚙️ Configurações")
    settings_win.geometry("650x700")
    settings_win.transient(app.root)
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
    ctk.CTkButton(btn_frame, text="💾 Salvar", font=("", 13, "bold"), width=120, height=34, fg_color=COLOR_ACCENT_CYAN, hover_color="#0097a7", text_color="#111111", corner_radius=8, command=lambda: app.save_api_key(key_entry.get().strip(), settings_win)).pack(side="left")

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


