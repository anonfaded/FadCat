[Setup]
; Values are injected by build/windows/build.ps1 from src/version.py.
AppName={#AppName}
AppVerName={#AppName} {#AppVersion}
AppVersion={#AppVersion}
AppPublisher={#AppCompany}
AppPublisherURL={#AppWebsiteURL}
AppSupportURL={#AppWebsiteURL}
AppUpdatesURL={#AppGithubURL}
AppComments={#AppDescription}
DefaultDirName={userappdata}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\..\dist
OutputBaseFilename={#AppName}-v{#AppVersion}-Windows-Setup
WizardStyle=modern dynamic
WizardImageFile=..\..\icon-assets\fadcat-wizard.png
WizardSmallImageFile=..\..\icon-assets\fadcat-small.png
SetupIconFile=..\..\icon-assets\fadcat.ico
UninstallDisplayIcon={app}\FadCat-GUI.exe,0
LicenseFile=..\..\LICENSE
VersionInfoVersion={#AppVersionInfo}
VersionInfoProductVersion={#AppVersionInfo}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppDescription}
VersionInfoCompany={#AppCompany}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

[Files]
Source: "..\..\dist\FadCat-GUI\*"; DestDir: "{app}"; Flags: recursesubdirs replacesameversion
Source: "..\..\icon-assets\fadcat.png"; DestDir: "{app}\icon-assets"; Flags: replacesameversion
; Note: do not install wrapper batch files. Default `fadcat.exe` will be the CLI binary.

[Dirs]
Name: "{app}"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\FadCat-GUI.exe"; Comment: "Launch FadCat"


[Run]
Filename: "{app}\FadCat-GUI.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\icon-assets"
Type: filesandordirs; Name: "{app}"

[Code]
// Add the application directory to PATH during installation
procedure AddAppToPath();
var
  AppPath: string;
  OldPath: string;
  NewPath: string;
begin
  AppPath := ExpandConstant('{app}');
  
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'PATH', OldPath) then
  begin
    if Pos(AppPath, OldPath) = 0 then
    begin
      NewPath := AppPath + ';' + OldPath;
      RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'PATH', NewPath);
    end;
  end
  else
  begin
    RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'PATH', AppPath);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AddAppToPath();
end;
