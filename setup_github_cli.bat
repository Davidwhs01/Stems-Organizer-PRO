# Sistema Completo de Versionamento e Atualização - Stems Organizer Pro

## 1. SETUP INICIAL DO SISTEMA

### setup_github_cli.bat
@echo off
echo ================================
echo  SETUP GITHUB CLI E REPOSITORIO
echo ================================

REM Instalar GitHub CLI usando winget
echo Instalando GitHub CLI...
winget install --id GitHub.cli --silent

REM Aguardar instalação
timeout /t 5 /nobreak

REM Verificar se foi instalado
gh --version
if errorlevel 1 (
    echo ERRO: GitHub CLI não foi instalado corretamente
    echo Instale manualmente: https://cli.github.com/
    pause
    exit /b 1
)

echo GitHub CLI instalado com sucesso!

REM Fazer login no GitHub
echo.
echo Fazendo login no GitHub...
echo IMPORTANTE: Uma página do navegador será aberta para autenticação
echo.
pause
gh auth login

REM Verificar se o login funcionou
gh auth status
if errorlevel 1 (
    echo ERRO: Login no GitHub falhou
    pause
    exit /b 1
)

echo.
echo GitHub CLI configurado com sucesso!
echo Agora execute: init_repository.bat
pause

## 2. INICIALIZAÇÃO DO REPOSITÓRIO

### init_repository.bat
@echo off
echo ================================
echo  CRIANDO REPOSITORIO NO GITHUB
echo ================================

set /p REPO_NAME="Digite o nome do repositório (ex: stems-organizer-pro): "
set /p REPO_DESCRIPTION="Digite a descrição do projeto: "

echo.
echo Criando repositório: %REPO_NAME%
echo Descrição: %REPO_DESCRIPTION%
echo.

REM Inicializar git localmente
git init
git add .
git commit -m "Initial commit - Stems Organizer Pro v1.0.0"

REM Criar repositório no GitHub (privado para app comercial)
gh repo create %REPO_NAME% --description "%REPO_DESCRIPTION%" --private --source=. --remote=origin --push

if errorlevel 1 (
    echo ERRO: Falha ao criar repositório
    pause
    exit /b 1
)

echo.
echo ✅ Repositório criado com sucesso!
echo URL: https://github.com/%USERNAME%/%REPO_NAME%
echo.

REM Criar primeira tag/release
git tag v1.0.0
git push origin v1.0.0

echo ✅ Primeira versão (v1.0.0) criada!
echo.
echo Próximos passos:
echo 1. Execute: create_version_files.bat
echo 2. Configure o sistema de atualização
pause

## 3. SCRIPT PARA CRIAR ARQUIVOS DE VERSÃO

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

## 4. SCRIPT PARA NOVAS VERSÕES

### new_version.bat
@echo off
setlocal enabledelayedexpansion

echo ================================
echo  CRIANDO NOVA VERSÃO
echo ================================

REM Pegar versão atual
for /f "tokens=2 delims=:" %%a in ('findstr "current_version" version.json') do (
    set current=%%a
    set current=!current: =!
    set current=!current:"=!
    set current=!current:,=!
)

echo Versão atual: !current!
echo.
echo Tipos de atualização:
echo 1. Patch (1.0.0 -> 1.0.1) - Bug fixes
echo 2. Minor (1.0.0 -> 1.1.0) - Novos recursos
echo 3. Major (1.0.0 -> 2.0.0) - Mudanças importantes
echo.

set /p update_type="Escolha o tipo (1-3): "
set /p changelog="Digite as principais mudanças: "

REM Calcular nova versão (simplificado)
if "%update_type%"=="1" (
    set /p new_version="Digite a nova versão patch (ex: 1.0.1): "
) else if "%update_type%"=="2" (
    set /p new_version="Digite a nova versão minor (ex: 1.1.0): "
) else (
    set /p new_version="Digite a nova versão major (ex: 2.0.0): "
)

echo.
echo Criando versão: !new_version!
echo Changelog: !changelog!
echo.

REM Atualizar version.json
powershell -Command "(Get-Content version.json) -replace 'current_version.*', '\"current_version\": \"!new_version!\",  ' | Set-Content version.json"

REM Commit e tag
git add -A
git commit -m "Release v!new_version! - !changelog!"
git tag v!new_version!
git push origin main
git push origin v!new_version!

REM Criar release no GitHub
gh release create v!new_version! --title "Stems Organizer Pro v!new_version!" --notes "!changelog!"

echo.
echo ✅ Nova versão v!new_version! criada com sucesso!
echo ✅ Release publicado no GitHub
pause