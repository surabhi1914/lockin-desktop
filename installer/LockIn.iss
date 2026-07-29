#define MyAppName "LockIn"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Surabhi Nair"
#define MyAppExeName "LockIn.exe"

[Setup]
AppId={{B4257427-A820-4C8E-BD6B-9D51A34EE6A4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\LockIn
DefaultGroupName=LockIn
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=LockIn-Setup-v1.1.0
SetupIconFile=..\app\assets\icons\lockin.ico
UninstallDisplayIcon={app}\LockIn.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion=1.1.0.0
VersionInfoCompany=Surabhi Nair
VersionInfoDescription=LockIn Focus Timer Installer
VersionInfoProductName=LockIn
VersionInfoProductVersion=1.1.0
LicenseFile=..\LICENSE
ChangesAssociations=no
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\LockIn\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LockIn"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\LockIn"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch LockIn"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
