@echo off
set "PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON%" (
  echo Bundled Python was not found.
  echo Install Python 3.12 from python.org, then run: python manage.py runserver
  exit /b 1
)

echo Using Python: %PYTHON%
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

"%PYTHON%" manage.py migrate
if errorlevel 1 exit /b %errorlevel%

"%PYTHON%" manage.py runserver
