"""
Stems Organizer PRO — Notificações Toast
Sistema de notificações com animação slide-in.
"""
import customtkinter as ctk
from .config import (
    COLOR_TEXT, COLOR_TEXT_DIM,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING,
    COLOR_ACCENT_PURPLE, COLOR_ACCENT_CYAN,
    FONT_BODY, FONT_BODY_BOLD, FONT_CAPTION, FONT_BUTTON
)


class ToastNotification:
    """Sistema de notificações toast com animação slide-in"""
    _active_toasts = []

    def __init__(self, root, message, toast_type="info", duration=4000, action_text=None, action_callback=None):
        self.root = root
        self.duration = duration
        self._destroyed = False

        configs = {
            "success": {"icon": "✓", "bg": "#064e3b", "border": COLOR_SUCCESS, "accent": COLOR_SUCCESS},
            "error":   {"icon": "✕", "bg": "#450a0a", "border": COLOR_ERROR, "accent": COLOR_ERROR},
            "warning": {"icon": "!", "bg": "#451a03", "border": COLOR_WARNING, "accent": COLOR_WARNING},
            "update":  {"icon": "↻", "bg": "#1e1b4b", "border": COLOR_ACCENT_PURPLE, "accent": COLOR_ACCENT_PURPLE},
            "info":    {"icon": "i", "bg": "#0c1929", "border": COLOR_ACCENT_CYAN, "accent": COLOR_ACCENT_CYAN}
        }
        cfg = configs.get(toast_type, configs["info"])

        # Calcular posição vertical (empilhar toasts)
        y_offset = 20
        for t in ToastNotification._active_toasts:
            try:
                if t.toast_frame and t.toast_frame.winfo_exists():
                    y_offset += 75
            except:
                pass

        # Frame principal do toast
        self.toast_frame = ctk.CTkFrame(
            root, fg_color=cfg["bg"], corner_radius=12,
            border_width=1, border_color=cfg["border"],
            width=420, height=60
        )
        self.toast_frame.place(relx=1.0, y=y_offset, anchor="ne", x=430)
        self.toast_frame.pack_propagate(False)

        content = ctk.CTkFrame(self.toast_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=8)

        ctk.CTkLabel(content, text=cfg["icon"], font=("Segoe UI Semibold", 16, "bold"), width=30, text_color=cfg["accent"]).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            content, text=message, font=FONT_BODY, text_color=COLOR_TEXT,
            anchor="w", wraplength=250
        ).pack(side="left", fill="x", expand=True)

        if action_text and action_callback:
            ctk.CTkButton(
                content, text=action_text, font=FONT_BUTTON, width=90, height=28,
                fg_color=cfg["accent"], hover_color=cfg["border"], corner_radius=8,
                command=lambda: [action_callback(), self.dismiss()]
            ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            content, text="✕", width=24, height=24, font=FONT_CAPTION,
            fg_color="transparent", hover_color="#374151", text_color=COLOR_TEXT_DIM,
            command=self.dismiss
        ).pack(side="right")

        ToastNotification._active_toasts.append(self)
        self._slide_in(y_offset)

    def _slide_in(self, y_offset, current_x=430):
        if self._destroyed:
            return
        if current_x > -10:
            try:
                if self.toast_frame.winfo_exists():
                    self.toast_frame.place(relx=1.0, y=y_offset, anchor="ne", x=current_x)
                    self.root.after(12, lambda: self._slide_in(y_offset, current_x - 30))
            except:
                pass
        else:
            try:
                if self.toast_frame.winfo_exists():
                    self.toast_frame.place(relx=1.0, y=y_offset, anchor="ne", x=-10)
            except:
                pass
            if self.duration > 0:
                self.root.after(self.duration, self.dismiss)

    def dismiss(self):
        if self._destroyed:
            return
        self._destroyed = True
        try:
            if self in ToastNotification._active_toasts:
                ToastNotification._active_toasts.remove(self)
            if self.toast_frame and self.toast_frame.winfo_exists():
                self.toast_frame.destroy()
        except:
            pass
