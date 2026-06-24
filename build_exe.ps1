$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip show pyinstaller | Out-Null
python -m PyInstaller --noconfirm --clean --onefile --add-data "web;web" --name CampusCrawler app.py

Write-Host "Built: dist\CampusCrawler.exe"
