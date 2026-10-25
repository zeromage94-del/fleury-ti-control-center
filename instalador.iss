#define MyAppName "Fleury TI Control Center"
#define MyAppVersion "1.3.1"
#define MyAppPublisher "Ferramenta de TI - protótipo independente"
#define MyAppExeName "FleuryTIControlCenter.exe"
[Setup]
AppId={{5E7819F9-2C9F-488F-8F8D-2BDF04B5D853}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Fleury TI Control Center
DefaultGroupName=Fleury TI Control Center
OutputDir=entrega_windows
OutputBaseFilename=Fleury_TI_Instalador_v1.3.1_Windows_x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
SetupLogging=yes
[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
[Files]
Source: "dist\FleuryTIControlCenter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LEIA_PRIMEIRO.txt"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\Fleury TI Control Center"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Fleury TI Control Center"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Ícones adicionais:"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Fleury TI Control Center"; Flags: nowait postinstall skipifsilent
[UninstallDelete]
; Não apagar o banco de dados e as imagens em %LOCALAPPDATA% no uninstall.

