#!/bin/bash
# Double-cliquez sur ce fichier (Mac) pour lancer Jarvis.
cd "$(dirname "$0")/.." || exit 1
if [ ! -d .venv-jarvis ]; then
  echo "Première installation, patientez une minute…"
  python3 -m venv .venv-jarvis || { echo "Python 3 est requis : https://www.python.org/downloads/"; read -r; exit 1; }
fi
source .venv-jarvis/bin/activate
pip install -q -r assistant_vocal/requirements.txt
python -m assistant_vocal "$@"
