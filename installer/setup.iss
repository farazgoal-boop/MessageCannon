; MessageCannon Installer Script
; Inno Setup 6.0+
;
; Version is passed in by CI via `ISCC /DMyAppVersion=x.y.z setup.iss` (computed
; from the git tag, same pattern build-mac-linux.yml already uses for the Linux
; .deb package version) so a release doesn't silently ship as "1.0.0" forever.
; The #ifndef fallback keeps a plain local `ISCC setup.iss` (no /D flag) working
; for manual test builds.
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

[Setup]
AppId={{9C5BC6E1-4A94-4C72-BE29-1D9BC9B0C6A8}
AppName=MessageCannon
AppVerName=MessageCannon Premium {#MyAppVersion}
AppVersion={#MyAppVersion}
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
InfoBeforeFile=..\installer\PREMIUM_INSTALL_BRIEF.txt
InfoAfterFile=..\installer\ACTIVATION_NOTICE.txt
ShowLanguageDialog=auto
AllowUNCPath=no
ArchitecturesInstallIn64BitMode=x64os
ArchitecturesAllowed=x64compatible
WizardStyle=modern

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
; uninsdeletekey on the subkey itself (needs it on only one line, but Inno
; Setup only evaluates uninsdeletekey against the specific Subkey value of
; the line it's on, so both carry it for safety): without this flag, real
; installs were confirmed (by actually installing then uninstalling) to
; leave HKCU\Software\MessageCannon behind forever after uninstall.
Root: HKCU; Subkey: "Software\MessageCannon"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\MessageCannon"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Messages]
WelcomeLabel1=Welcome to the MessageCannon Premium Setup Wizard
WelcomeLabel2=This installer prepares the premium messaging workspace with persistent sessions, delivery analytics, and activation-ready campaign controls.
FinishedHeadingLabel=MessageCannon Premium Is Ready
FinishedLabelNoIcons=Setup has finished installing MessageCannon Premium on your computer.%n%nLaunch the app to see the branded startup workspace and complete activation if your 3-day trial has ended.
