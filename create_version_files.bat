### create_version_files.bat
@echo off
echo ================================
echo  CRIANDO ARQUIVOS DE VERSÃO
echo ================================

REM Criar version.json
echo { > version.json
echo   "current_version": "1.0.0", >> version.json
echo   "release_date": "%DATE%", >> version.json
echo   "download_url": "https://github.com/SEU_USERNAME/SEU_REPO/releases/latest/download/stems_organizer_pro.exe", >> version.json
echo   "changelog_url": "https://github.com/SEU_USERNAME/SEU_REPO/releases/latest", >> version.json
echo   "minimum_version": "1.0.0", >> version.json
echo   "update_required": false, >> version.json
echo   "changelog": [ >> version.json
echo     "Lançamento inicial do Stems Organizer Pro", >> version.json
echo     "Classificação automática com IA", >> version.json
echo     "Interface moderna e intuitiva", >> version.json
echo     "Suporte a múltiplos formatos de audio" >> version.json
echo   ] >> version.json
echo } >> version.json

echo ✅ version.json criado!

REM Criar update_info.json (para controle mais granular)
echo { > update_info.json
echo   "version": "1.0.0", >> update_info.json
echo   "build": "001", >> update_info.json
echo   "release_type": "stable", >> update_info.json
echo   "force_update": false, >> update_info.json
echo   "maintenance_mode": false, >> update_info.json
echo   "supported_os": ["windows"], >> update_info.json
echo   "min_python_version": "3.8", >> update_info.json
echo   "dependencies": { >> update_info.json
echo     "customtkinter": ">=5.0.0", >> update_info.json
echo     "google-generativeai": ">=0.3.0", >> update_info.json
echo     "pydub": ">=0.25.0", >> update_info.json
echo     "supabase": ">=2.0.0", >> update_info.json
echo     "pillow": ">=9.0.0" >> update_info.json
echo   } >> update_info.json
echo } >> update_info.json

echo ✅ update_info.json criado!
echo.
echo Arquivos de versão criados com sucesso!
echo Lembre-se de atualizar os URLs com seu username/repo real
pause