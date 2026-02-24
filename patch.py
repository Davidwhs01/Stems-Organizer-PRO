import sys
import re

with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Imports
text = text.replace(
    'from stems_organizer_pro.history import SessionHistory\nfrom stems_organizer_pro.notifications import ToastNotification\nfrom stems_organizer_pro.feedback import ExecutionFeedback\nfrom stems_organizer_pro.updater import AutoUpdater',
    '''from stems_organizer_pro.history import SessionHistory
from stems_organizer_pro.notifications import ToastNotification
from stems_organizer_pro.feedback import ExecutionFeedback
from stems_organizer_pro.updater import AutoUpdater
from stems_organizer_pro.classifier import AudioClassifier
from stems_organizer_pro.file_ops import FileOperations
from stems_organizer_pro import screens'''
)

# 2. Init classifier
text = text.replace(
    '        self.api_key = ""',
    '        self.api_key = ""\n        self.classifier = AudioClassifier(self.api_key, self.supabase, FFMPEG_AVAILABLE)'
)

# 3. count_wav_files
text = text.replace('self.count_wav_files()', 'FileOperations.count_wav_files(self.folder_path_full)')

# 4. armazenar_acao
text = text.replace("self.armazenar_acao('delete', caminho)", "self.planned_actions.append(FileOperations.create_action('delete', caminho))")

# 5. mover_arquivo and renomear_arquivo
# For move:
# Old: self.mover_arquivo(caminho, nome_final, categoria_encontrada, pasta_raiz, is_dry_run=True)
text = text.replace(
    'self.mover_arquivo(caminho, nome_final, categoria_encontrada, pasta_raiz, is_dry_run=True)',
    'FileOperations.move_file(caminho, nome_final, categoria_encontrada, pasta_raiz, self.classifier.PARENT_FOLDER_MAP)'
)
# Second move:
# Old: self.mover_arquivo(caminho_original, nome, categoria, pasta_raiz, is_dry_run=True)
text = text.replace(
    'self.mover_arquivo(caminho_original, nome, categoria, pasta_raiz, is_dry_run=True)',
    'FileOperations.move_file(caminho_original, nome, categoria, pasta_raiz, self.classifier.PARENT_FOLDER_MAP)'
)
# Third move:
# Old: self.mover_arquivo(\n                            action['source_path'], \n                            action['target_name'], \n                            action['category'], \n                            self.folder_path_full, \n                            is_dry_run=False\n                        )
text = re.sub(
    r"self\.mover_arquivo\(\s*action\['source_path'\],\s*action\['target_name'\],\s*action\['category'\],\s*self\.folder_path_full,\s*is_dry_run=False\s*\)",
    r"FileOperations.move_file(action['source_path'], action['target_name'], action['category'], self.folder_path_full, self.classifier.PARENT_FOLDER_MAP)",
    text
)

# For rename:
text = text.replace(
    'self.renomear_arquivo_no_local(caminho_original, nome, is_dry_run=True)',
    'FileOperations.rename_file(caminho_original, nome)'
)
text = re.sub(
    r"self\.renomear_arquivo_no_local\(\s*action\['source_path'\],\s*action\['target_name'\],\s*is_dry_run=False\s*\)",
    r"FileOperations.rename_file(action['source_path'], action['target_name'])",
    text
)

# 6. UI Wrappers
ui_wrappers = '''
    def show_welcome_screen(self): screens.show_welcome_screen(self)
    def show_history_screen(self): screens.show_history_screen(self)
    def show_folder_preview(self, sample_files): screens.show_folder_preview(self, sample_files)
    def open_settings_window(self): screens.open_settings_window(self)
    def show_final_report(self): screens.show_final_report(self)
    def show_completion_screen(self, s, e, err): screens.show_completion_screen(self, s, e, err)
'''
text = text.replace('def main():', ui_wrappers + '\ndef main():')

# API Key update hook
text = text.replace('self.api_key = api_key', 'self.api_key = api_key\n                    self.classifier.api_key = api_key')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Wiring completed successfully via patch.py.')
