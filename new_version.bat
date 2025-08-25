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