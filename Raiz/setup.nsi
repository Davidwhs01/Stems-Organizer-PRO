# ===================================================================
# Script de Instalação Profissional para Stems Organizer PRO
# Versão Final
# ===================================================================

# --- APRIMORAMENTO: Gerenciamento Centralizado de Versão e Nomes ---
!define APP_NAME "Stems Organizer PRO"
!define APP_PUBLISHER "Prod. Aki"
!define APP_VERSION "1.1.0" # <-- Mude APENAS AQUI para futuras atualizações
!define EXE_NAME "Stems Organizer PRO.exe"

# --- Inclusão de Bibliotecas da Interface ---
!include "MUI2.nsh"
!include "LogicLib.nsh" # Necessário para a lógica de verificação

# -- Configurações Gerais do Instalador --
Name "${APP_NAME} ${APP_VERSION}"
OutFile "${APP_NAME}_Setup_v${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\StemsOrganizerPro"
Icon "logo.ico"
RequestExecutionLevel admin

# --- APRIMORAMENTO: Compressão LZMA (muito mais eficiente) ---
SetCompressor /solid lzma

# -- Informações de Versão (Aparece em Propriedades > Detalhes do arquivo .exe) --
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "FileDescription" "Instalador do ${APP_NAME}"
VIAddVersionKey "LegalCopyright" "© 2025 ${APP_PUBLISHER}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"

# -- Definições da Interface Moderna (MUI2) --
!define MUI_ABORTWARNING
!define MUI_ICON "logo.ico"
!define MUI_UNICON "logo.ico"

# -- Páginas da Interface do Instalador --
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "license.txt" # APRIMORAMENTO: Página de licença
!insertmacro MUI_PAGE_COMPONENTS           # APRIMORAMENTO: Página para escolher componentes (atalho)
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

# -- Páginas da Interface do Desinstalador --
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

# -- Idioma --
!insertmacro MUI_LANGUAGE "PortugueseBR"

# ===================================================================
# --- Funções e Lógica ---
# ===================================================================

# APRIMORAMENTO: Função que roda ANTES da instalação começar
Function .onInit
  # Verifica se o aplicativo já está em execução
  FindWindow $R0 "TkTopLevel" "Stems Organizer Pro by Prod. Aki"
  ${If} $R0 != 0
    MessageBox MB_OK|MB_ICONEXCLAMATION "O ${APP_NAME} já está em execução. Por favor, feche o programa antes de continuar a instalação."
    Abort
  ${EndIf}
FunctionEnd

# APRIMORAMENTO: Função que roda ANTES da desinstalação começar
Function un.onInit
  # Verifica se o aplicativo já está em execução
  FindWindow $R0 "TkTopLevel" "Stems Organizer Pro by Prod. Aki"
  ${If} $R0 != 0
    MessageBox MB_OK|MB_ICONEXCLAMATION "O ${APP_NAME} está em execução. Por favor, feche o programa para desinstalá-lo."
    Abort
  ${EndIf}
FunctionEnd

# ===================================================================
# --- SEÇÃO DE INSTALAÇÃO ---
# ===================================================================

# Descreve as seções para a página de componentes
LangString DESC_SEC_CORE ${LANG_PORTUGUESEBR} "O programa principal e seus componentes essenciais."
LangString DESC_SEC_DESKTOPSHORTCUT ${LANG_PORTUGUESEBR} "Cria um atalho na Área de Trabalho para acesso rápido."

Section "Programa Principal" SEC_CORE
  SectionIn RO # Seção obrigatória, não pode ser desmarcada
  SetOutPath $INSTDIR
  
  # Adiciona todos os arquivos necessários
  File "${EXE_NAME}"
  File "ffmpeg.exe"
  File "ffprobe.exe"

  # Cria o desinstalador
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  # Cria os atalhos no Menu Iniciar
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Desinstalar ${APP_NAME}.lnk" "$INSTDIR\uninstall.exe"
  
  # Cria as entradas de Registro para "Adicionar ou Remover Programas"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO" "DisplayIcon" "$INSTDIR\${EXE_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO" "DisplayVersion" "${APP_VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO" "NoRepair" 1
SectionEnd

# APRIMORAMENTO: Seção opcional para o atalho na Área de Trabalho
Section "Criar atalho na Área de Trabalho" SEC_DESKTOPSHORTCUT
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
SectionEnd

# Atribui as descrições às seções na página de componentes
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_CORE} $(DESC_SEC_CORE)
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOPSHORTCUT} $(DESC_SEC_DESKTOPSHORTCUT)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

# ===================================================================
# --- SEÇÃO DE DESINSTALAÇÃO ---
# ===================================================================
Section "Uninstall"
  # Deleta os arquivos da pasta de instalação
  Delete "$INSTDIR\${EXE_NAME}"
  Delete "$INSTDIR\ffmpeg.exe"
  Delete "$INSTDIR\ffprobe.exe"
  Delete "$INSTDIR\uninstall.exe"
  
  # Deleta os atalhos
  Delete "$SMPROGRAMS\${APP_NAME}\*.*"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  
  # Deleta as pastas (somente se estiverem vazias, por segurança)
  RMDir "$SMPROGRAMS\${APP_NAME}"
  RMDir "$INSTDIR"
  
  # Deleta a pasta de dados do usuário (configurações, api_key, etc.)
  RMDir /r "$APPDATA\StemsOrganizerPro"
  
  # Remove as chaves de registro
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\StemsOrganizerPRO"
SectionEnd