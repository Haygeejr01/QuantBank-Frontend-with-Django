$ErrorActionPreference = "Stop"

$Python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Bundled Python was not found. Install Python 3.12 from python.org and use: python manage.py runserver"
}

Write-Host "Using Python: $Python"
& $Python -m pip install -r requirements.txt
& $Python manage.py migrate
& $Python manage.py runserver
