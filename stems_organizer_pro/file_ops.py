import os
import shutil
import logging

logger = logging.getLogger(__name__)

class FileOperations:
    """Centraliza operações de arquivo (mover, renomear, contar)."""
    
    @staticmethod
    def count_wav_files(folder_path):
        """Conta total de arquivos .wav na pasta"""
        if not folder_path or not os.path.exists(folder_path):
            return 0
        
        count = 0
        try:
            for root, dirs, files in os.walk(folder_path):
                count += sum(1 for f in files if f.lower().endswith('.wav'))
        except Exception as e:
            logger.debug(f"Erro ao contar arquivos: {e}")
            
        return count

    @staticmethod
    def move_file(source_path, target_name, category, root_folder, parent_folder_map):
        """Move arquivo para a categoria apropriada e retorna novo caminho"""
        try:
            parent_folder = parent_folder_map.get(category, "Outros")
            cat_path = os.path.join(root_folder, parent_folder, category)
            os.makedirs(cat_path, exist_ok=True)
            
            dest = os.path.join(cat_path, target_name)
            
            # Evitar sobrescrever
            counter = 1
            base, ext = os.path.splitext(target_name)
            while os.path.exists(dest):
                dest = os.path.join(cat_path, f"{base}_{counter}{ext}")
                counter += 1
            
            shutil.move(source_path, dest)
            return dest
            
        except Exception as e:
            logger.error(f"Erro ao mover arquivo {source_path}: {e}")
            raise

    @staticmethod
    def rename_file(source_path, target_name):
        """Renomeia arquivo na mesma pasta e retorna novo caminho"""
        try:
            parent_dir = os.path.dirname(source_path)
            dest = os.path.join(parent_dir, target_name)
            
            # Evitar sobrescrever
            counter = 1
            base, ext = os.path.splitext(target_name)
            while os.path.exists(dest):
                dest = os.path.join(parent_dir, f"{base}_{counter}{ext}")
                counter += 1
                
            os.rename(source_path, dest)
            return dest
            
        except Exception as e:
            logger.error(f"Erro ao renomear arquivo {source_path}: {e}")
            raise

    @staticmethod
    def create_action(action_type, source_path, target_name=None, category=None):
        """Cria dicionário descritivo de ação planejada"""
        action = {
            'action': action_type,
            'source_path': source_path,
            'source_name': os.path.basename(source_path)
        }
        if target_name:
            action['target_name'] = target_name
        if category:
            action['category'] = category
        return action
