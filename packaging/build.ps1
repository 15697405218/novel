$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$version = "3.10.11"
$cache = Join-Path $PSScriptRoot "cache"
$zip = Join-Path $cache "python-$version-embed-amd64.zip"
$pipScript = Join-Path $cache "get-pip.py"
$dist = Join-Path (Get-Location) "dist\Novel"
$pythonDir = Join-Path $dist "python"
$app = Join-Path $dist "app"

New-Item -ItemType Directory -Force -Path $cache | Out-Null
if (-not (Test-Path $zip)) {
    Invoke-WebRequest "https://www.python.org/ftp/python/$version/python-$version-embed-amd64.zip" -OutFile $zip
}
if (-not (Test-Path $pipScript)) {
    Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $pipScript
}

if (Test-Path $dist) {
    Remove-Item $dist -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $pythonDir | Out-Null
Expand-Archive $zip -DestinationPath $pythonDir
New-Item -ItemType Directory -Force -Path (Join-Path $pythonDir "Lib\site-packages") | Out-Null

@"
python310.zip
.
..\app
Lib\site-packages
import site
"@ | Set-Content -Encoding ascii (Join-Path $pythonDir "python310._pth")

Copy-Item $pipScript (Join-Path $pythonDir "get-pip.py")
$python = Join-Path $pythonDir "python.exe"
& $python (Join-Path $pythonDir "get-pip.py")
& $python -m pip install -r requirements.txt

New-Item -ItemType Directory -Force -Path $app | Out-Null
Copy-Item desktop (Join-Path $app "desktop") -Recurse
Copy-Item auth (Join-Path $app "auth") -Recurse
Copy-Item prompts (Join-Path $app "prompts") -Recurse
Get-ChildItem $app -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force

$iss = Join-Path $PSScriptRoot "novel.iss"
$compiler = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($compiler) {
    & $compiler $iss
    Write-Output "安装包已生成。"
} else {
    Write-Output "目录在 dist\Novel。安装 Inno Setup 6 后可编译 packaging\novel.iss。"
}
