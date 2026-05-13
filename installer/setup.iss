; MessageCannon Installer Script
; Inno Setup 6.0+

[Setup]
AppName=MessageCannon
AppVersion=1.0.0
AppPublisher=Muhammad Faraz
AppPublisherURL=https://github.com/farazgoal/MessageCannon
AppSupportURL=https://github.com/farazgoal/MessageCannon/issues
AppUpdatesURL=https://github.com/farazgoal/MessageCannon/releases
DefaultDirName={localappdata}\Programs\MessageCannon
PrivilegesRequired=lowest
DefaultGroupName=MessageCannon
OutputDir=..\installer
OutputBaseFilename=MessageCannon_Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\src\assets\icons\app.ico
UninstallDisplayIcon={app}\MessageCannon.exe
LicenseFile=..\LICENSE
ShowLanguageDialog=auto
AllowUNCPath=no
ArchitecturesInstallIn64BitMode=x64os
ArchitecturesAllowed=x64compatible

[Files]
; Main executable
Source: "..\dist\MessageCannon.exe"; DestDir: "{app}"; Flags: ignoreversion
; Assets
Source: "..\src\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
; Documentation
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\MessageCannon"; Filename: "{app}\MessageCannon.exe"; IconFilename: "{app}\assets\icons\app.ico"
Name: "{group}\Uninstall MessageCannon"; Filename: "{uninstallexe}"
Name: "{group}\User Guide"; Filename: "{app}\docs\user_guide.md"
Name: "{userdesktop}\MessageCannon"; Filename: "{app}\MessageCannon.exe"; IconFilename: "{app}\assets\icons\app.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"

[Run]
Filename: "{app}\MessageCannon.exe"; Description: "{cm:LaunchProgram,MessageCannon}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
procedure InitializeWizard;
begin
  // Custom initialization code if needed
end;

[Registry]
Root: HKCU; Subkey: "Software\MessageCannon"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"
Root: HKCU; Subkey: "Software\MessageCannon"; ValueType: string; ValueName: "Version"; ValueData: "1.0.0"
