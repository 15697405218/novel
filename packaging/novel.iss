[Setup]
AppName=Novel
AppVersion=0.1.0
DefaultDirName={autopf}\Novel
DefaultGroupName=Novel
OutputBaseFilename=Novel-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "..\dist\Novel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Novel"; Filename: "{app}\Novel.exe"
Name: "{autodesktop}\Novel"; Filename: "{app}\Novel.exe"

[Run]
Filename: "{app}\Novel.exe"; Description: "打开 Novel"; Flags: nowait postinstall skipifsilent
