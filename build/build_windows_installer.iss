; ============================================================
;  MessageCannon Pro — Inno Setup 6 Installer Script
;  Compile with: ISCC.exe build\build_windows_installer.iss
;  Output:       dist\MessageCannonPro-Setup.exe
; ============================================================

#define MyAppName      "MessageCannon Pro"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "Muhammad Faraz"
#define MyAppURL       "https://muhammad-faraz-dev.netlify.app"
#define MyAppExeName   "MessageCannon Pro.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL=mailto:farazgoal@gmail.com
AppUpdatesURL={#MyAppURL}

; Per-user install (no admin required)
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Installer appearance
WizardStyle=modern
AllowNoIcons=yes
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64os
ArchitecturesAllowed=x64compatible

; Icon & license
SetupIconFile=..\src\assets\icons\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE

; Output
OutputDir=..\dist
OutputBaseFilename=MessageCannonPro-Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; App assets (icons, themes, templates)
Source: "..\src\assets\*"; DestDir: "{app}\assets"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation
Source: "..\README.md";          DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE";            DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\user_guide.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";                  Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\assets\icons\app.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{group}\User Guide";                    Filename: "{app}\docs\user_guide.md"
Name: "{autodesktop}\{#MyAppName}";            Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\assets\icons\app.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\{#MyAppName}"; \
    ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"
Root: HKCU; Subkey: "Software\{#MyAppName}"; \
    ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName,'&','&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove user-data only if the user explicitly chose so during uninstall
; (We do NOT delete AppData automatically — preserves contacts & campaigns)

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    MsgBox(
      'MessageCannon Pro installed successfully.' + #13#10 + #13#10 +
      'On first run, enter your license key to activate.' + #13#10 +
      'Need a key? Contact: farazgoal@gmail.com',
      mbInformation, MB_OK);
end;

function InitializeUninstall(): Boolean;
var
  Res: Integer;
begin
  Res := MsgBox(
    'Do you want to keep your contacts and campaign data?' + #13#10 +
    'Click Yes to keep data, No to remove everything.',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON1);
  if Res = IDNO then
    DelTree(ExpandConstant('{localappdata}\MessageCannon Pro'), True, True, True);
  Result := True;
end;
