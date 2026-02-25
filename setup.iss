[Setup]
AppName=Stems Organizer PRO
AppVersion=1.8.0
AppPublisher=Prod. Aki
AppPublisherURL=https://github.com/Davidwhs01/Stems-Organizer-PRO
DefaultDirName={autopf}\Stems Organizer PRO
DefaultGroupName=Stems Organizer PRO
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=StemsOrganizerPRO_Setup
SetupIconFile=logo2.ico
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Stems Organizer PRO.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Raiz\ffmpeg.exe"; DestDir: "{userappdata}\StemsOrganizerPro\ffmpeg"; Flags: ignoreversion
Source: "Raiz\ffprobe.exe"; DestDir: "{userappdata}\StemsOrganizerPro\ffmpeg"; Flags: ignoreversion

[Icons]
Name: "{group}\Stems Organizer PRO"; Filename: "{app}\Stems Organizer PRO.exe"
Name: "{group}\{cm:UninstallProgram,Stems Organizer PRO}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Stems Organizer PRO"; Filename: "{app}\Stems Organizer PRO.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Stems Organizer PRO.exe"; Description: "{cm:LaunchProgram,Stems Organizer PRO}"; Flags: nowait postinstall skipifsilent
