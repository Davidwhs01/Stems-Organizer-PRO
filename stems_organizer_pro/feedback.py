"""
Stems Organizer PRO — Feedback de Execução
Dashboard em tempo real durante processamento.
"""
import time
import customtkinter as ctk
from .config import (
    COLOR_FRAME, COLOR_BACKGROUND, COLOR_TEXT,
    COLOR_ACCENT_CYAN, COLOR_ACCENT_PURPLE
)


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
        self.clear_parent_frame()

        self.feedback_frame = ctk.CTkFrame(self.parent_frame, fg_color="transparent")
        self.feedback_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.title_label = ctk.CTkLabel(
            self.feedback_frame,
            text="🎯 Processando seus arquivos...",
            font=("", 24, "bold"),
            text_color=COLOR_ACCENT_CYAN
        )
        self.title_label.pack(pady=(40, 20))

        main_container = ctk.CTkFrame(self.feedback_frame, fg_color=COLOR_FRAME)
        main_container.pack(fill="both", expand=True, padx=40, pady=20)

        self.stats_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=20)

        stats_container = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        stats_container.pack()
        stats_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.create_stat_card(stats_container, "🎵 Processados", "0", 0)
        self.create_stat_card(stats_container, "🎤 Classificados", "0", 1)
        self.create_stat_card(stats_container, "🗑️ Descartados", "0", 2)
        self.create_stat_card(stats_container, "⏱️ Tempo", "00:00", 3)

        activity_frame = ctk.CTkFrame(main_container, fg_color=COLOR_BACKGROUND)
        activity_frame.pack(fill="x", padx=20, pady=10)

        self.activity_label = ctk.CTkLabel(
            activity_frame, text="Iniciando análise...",
            font=("", 16), text_color=COLOR_TEXT
        )
        self.activity_label.pack(pady=15)

        self.file_list_frame = ctk.CTkScrollableFrame(
            main_container, fg_color=COLOR_BACKGROUND, height=200
        )
        self.file_list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

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

        ctk.CTkLabel(card, text=title, font=("", 12), text_color="#888888").pack(pady=(10, 5))
        value_label = ctk.CTkLabel(card, text=value, font=("", 18, "bold"), text_color=COLOR_ACCENT_PURPLE)
        value_label.pack(pady=(0, 10))
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

            ctk.CTkLabel(entry_frame, text=icon, width=30).pack(side="left", padx=(10, 5))
            ctk.CTkLabel(
                entry_frame, text=category, width=100,
                font=("", 12, "bold"), text_color=COLOR_ACCENT_CYAN
            ).pack(side="left", padx=5)

            display_name = filename[:50] + "..." if len(filename) > 50 else filename
            ctk.CTkLabel(
                entry_frame, text=display_name, anchor="w", font=("", 12)
            ).pack(side="left", fill="x", expand=True, padx=10)

            def scroll_to_bottom():
                try:
                    if hasattr(self.file_list_frame, '_parent_canvas'):
                        canvas = self.file_list_frame._parent_canvas
                        if canvas and canvas.winfo_exists():
                            canvas.yview_moveto(1.0)
                except:
                    pass

            if hasattr(self.file_list_frame, '_parent_canvas'):
                self.file_list_frame._parent_canvas.after(10, scroll_to_bottom)
        except Exception as e:
            print(f"DEBUG: Erro ao adicionar entrada de arquivo: {e}")

    def update_stats(self, stat_type, increment=1):
        """Atualiza estatísticas de forma thread-safe"""
        if stat_type in self.stats:
            self.stats[stat_type] += increment

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

            if "⏱️ Tempo" in self.stat_labels:
                time_label = self.stat_labels["⏱️ Tempo"]
                if time_label.winfo_exists():
                    elapsed = int(time.time() - self.stats['start_time'])
                    mins, secs = divmod(elapsed, 60)
                    time_label.configure(text=f"{mins:02d}:{secs:02d}")
        except Exception as e:
            print(f"DEBUG: Erro ao atualizar stats: {e}")
