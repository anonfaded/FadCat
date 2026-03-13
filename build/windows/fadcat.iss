[Setup]
; NOTE: Version must be kept in sync with src/version.py (__version__)
; TODO: Automate this by parsing src/version.py before build
AppName=FadCat
AppVersion=1.0.0
DefaultDirName={userappdata}\FadCat
OutputDir=dist
OutputBaseFilename=FadCat-Setup
WizardStyle=modern
UninstallDisplayIcon={app}\FadCat.exe
LicenseFile=LICENSE

[Files]
Source: "dist\FadCat\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Dirs]
Name: "{app}"

[Tasks]
Name: addToPath; Description: "Add fadcat to PATH"; Flags: exclusive

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  Path: string;
begin
  if CurStep = ssFinished then
  begin
    if IsTaskSelected('addToPath') then
    begin
      // Create batch file
      SetLength(Path, 260);
      ExpandEnvironmentStrings('{app}\fadcat.bat', Path, Length(Path));
      SetLength(Path, StrLen(PChar(Path)));
      
      // Write fadcat command wrapper
      SaveStringToFile('{app}\fadcat.bat', '@echo off' + #13#10 + '"{app}\FadCat.exe" %*', False);
      
      // Add to PATH
      if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'PATH', Path) then
      begin
        if Pos('{app}', Path) = 0 then
          RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'PATH', Path + ';{app}');
      end;
    end;
  end;
end;
