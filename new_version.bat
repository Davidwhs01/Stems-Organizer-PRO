@echo off
setlocal enabledelayedexpansion
cls

echo ================================
echo  CRIANDO NOVA VERSAO
echo ================================

REM Pegar versão atual
for /f "tokens=2 delims=:" %%a in ('findstr "current_version" version.json') do (
    set current=%%a
    set current=!current: =!
    set current=!current:"=!
    set current=!current:,=!
)

echo Versao atual: !current!
echo.
echo -----------------------------------------------------------------
echo  O que significam os Tipos de Atualizacao (Versionamento Semantico)?
echo -----------------------------------------------------------------
echo.
echo   PATCH (ex: 1.0.0 -> 1.0.1)
echo   - Use para pequenas correcoes de BUGS que nao adicionam
echo     novas funcionalidades.
echo.
echo   MINOR (ex: 1.0.0 -> 1.1.0)
echo   - Use quando voce ADICIONA NOVAS FUNCIONALIDADES que sao
echo     compativeis com a versao anterior.
echo.
echo   MAJOR (ex: 1.0.0 -> 2.0.0)
echo   - Use para GRANDES MUDANCAS que alteram drasticamente o
echo     programa ou quebram a compatibilidade.
echo.
echo -----------------------------------------------------------------
echo.

echo Tipos de atualizacao:
echo 1. Patch
echo 2. Minor
echo 3. Major
echo.

set /p update_type="Escolha o tipo de atualizacao (1-3): "
set /p changelog="Digite as principais mudancas desta versao: "

REM Calcular nova versão (simplificado)
if "%update_type%"=="1" (
    set /p new_version="Digite a nova versao patch (ex: 1.0.1): "
) else if "%update_type%"=="2" (
    set /p new_version="Digite a nova versao minor (ex: 1.1.0): "
) else (
    set /p new_version="Digite a nova versao major (ex: 2.0.0): "
)

echo.
echo Criando versao: !new_version!
echo Changelog: !changelog!
echo.
pause

REM Atualizar version.json
powershell -Command "(Get-Content version.json) -replace '\"current_version\": \".*\"', '\"current_version\": \"!new_version!\"' | Set-Content version.json"

REM Commit e tag
git add -A
git commit -m "Release v!new_version! - !changelog!"
git tag v!new_version!
git push origin main
git push origin v!new_version!

REM Criar release no GitHub
gh release create v!new_version! --title "Stems Organizer Pro v!new_version!" --notes "!changelog!"

echo.
echo ✅ Nova versao v!new_version! criada com sucesso!
echo ✅ Release publicado no GitHub
pause