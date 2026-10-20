[Setup]
AppId={{A7B2C4E1-6D58-4F0A-9C33-1E5A8B7D2F64}
AppName=Novel
AppVersion=0.1.0
DefaultDirName={localappdata}\Novel
DefaultGroupName=Novel
PrivilegesRequired=lowest
OutputBaseFilename=Novel-Setup
OutputDir=..\dist
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\python\pythonw.exe

[Files]
Source: "..\dist\Novel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{autoprograms}\Novel"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m desktop"; WorkingDir: "{app}\app"
Name: "{autodesktop}\Novel"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m desktop"; WorkingDir: "{app}\app"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-m desktop"; WorkingDir: "{app}\app"; Description: "打开 Novel"; Flags: nowait postinstall skipifsilent
