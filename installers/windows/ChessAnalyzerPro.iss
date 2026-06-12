; ==============================================================================
; Chess Analyzer Pro - Inno Setup 6 Installer Script
; ==============================================================================
; Requirements:
;   - Inno Setup 6.x  (https://jrsoftware.org/isinfo.php)
;   - PyInstaller build output in: ..\..\dist\ChessAnalyzerPro\
;   - logo.ico placed at: ..\..\assets\images\logo.ico
;
; To build: Right-click this .iss file -> Compile  (or run iscc.exe from CLI)
; ==============================================================================

#define AppName        "Chess Analyzer Pro"
#define AppVersion     "2.0.1"
#define AppPublisher   "imutkarsht"
#define AppURL         "https://github.com/imutkarsht/Chess_analyzer"
#define AppExeName     "ChessAnalyzerPro.exe"
#define AppId          "{{A3F2C1D4-7B8E-4A5F-9C6D-1E2F3A4B5C6D}"
; ^^^ Keep this GUID stable across versions so Windows uninstalls the old version cleanly.

[Setup]
; -- Identity
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases

; -- Install paths
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; -- Output
OutputDir=Output
OutputBaseFilename=ChessAnalyzerPro-{#AppVersion}-Windows-Setup
SetupIconFile=..\..\assets\images\logo.ico

; -- Compression (lzma2/ultra gives best ratio for PyInstaller bundles)
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; -- UI
WizardStyle=modern
WizardResizable=yes
ShowLanguageDialog=no

; -- Privileges (ask only for per-user install; no UAC if not needed)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; -- Uninstall
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; -- Misc
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0          ; Windows 10 minimum (PyQt6 requirement)

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Optional checkboxes in the installer wizard
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}";    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; -----------------------------------------------------------------------
; PyInstaller COLLECT output  (the entire dist\ChessAnalyzerPro\ folder)
; -----------------------------------------------------------------------
Source: "..\..\dist\ChessAnalyzerPro\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; LICENSE file shown in the installer
Source: "..\..\LICENSE"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

[Icons]
; Start-menu shortcut
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional task)
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

; Quick-launch shortcut (optional task)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
; Offer to launch the app after installation completes
Filename: "{app}\{#AppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up app-generated files in AppData on uninstall (optional)
; Chess Analyzer Pro stores user data in %LOCALAPPDATA%\ChessAnalyzerPro
Type: filesandordirs; Name: "{localappdata}\ChessAnalyzerPro"

[Code]
// ---------------------------------------------------------------------------
// Optional: detect if a previous version is running and warn the user
// ---------------------------------------------------------------------------
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;
