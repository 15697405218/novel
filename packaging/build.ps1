$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.\.venv\Scripts\pyinstaller --noconfirm --windowed --name Novel --paths . desktop\__main__.py
Write-Output "目录在 dist\Novel。安装包请用 Inno Setup 编译 packaging\novel.iss。"
