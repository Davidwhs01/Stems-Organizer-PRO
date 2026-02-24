"""
Stems Organizer PRO — Histórico de Sessões
Persiste sessões de organização em JSON.
"""
import os
import json
import time

from .config import SESSION_HISTORY_FILE


class SessionHistory:
    """Gerencia histórico de sessões de organização"""

    @staticmethod
    def load():
        try:
            if os.path.exists(SESSION_HISTORY_FILE):
                with open(SESSION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    @staticmethod
    def save(sessions):
        try:
            with open(SESSION_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(sessions[-10:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def add(folder_path, file_count, categories_found, duration_seconds):
        sessions = SessionHistory.load()
        sessions.append({
            'date': time.strftime('%Y-%m-%d %H:%M'),
            'folder': folder_path,
            'files': file_count,
            'categories': categories_found,
            'duration': round(duration_seconds, 1)
        })
        SessionHistory.save(sessions)
