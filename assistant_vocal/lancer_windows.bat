@echo off
rem Double-cliquez sur ce fichier (Windows) pour lancer Jarvis.
cd /d "%~dp0\.."
if not exist .venv-jarvis (
  echo Premiere installation, patientez une minute...
  py -3 -m venv .venv-jarvis || (echo Python 3 est requis : https://www.python.org/downloads/ & pause & exit /b 1)
)
call .venv-jarvis\Scripts\activate.bat
pip install -q -r assistant_vocal\requirements.txt
python -m assistant_vocal %*
pause
