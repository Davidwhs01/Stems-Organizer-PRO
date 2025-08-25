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

REM CORREÇÃO: Adicionadas aspas em "%REPO_NAME%" para lidar com espaços
gh repo create "%REPO_NAME%" --description "%REPO_DESCRIPTION%" --private --source=. --remote=origin --push

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