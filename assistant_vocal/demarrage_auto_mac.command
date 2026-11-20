#!/bin/bash
# Double-cliquez (Mac) : Jarvis démarrera tout seul à chaque ouverture de session, en arrière-plan.
cd "$(dirname "$0")/.." || exit 1
DOSSIER="$(pwd)"
if [ ! -x .venv-jarvis/bin/python ]; then
  echo "Installation de Jarvis, patientez une minute…"
  python3 -m venv .venv-jarvis || { echo "Python 3 est requis : https://www.python.org/downloads/"; read -r; exit 1; }
fi
.venv-jarvis/bin/pip install -q -r assistant_vocal/requirements.txt
PLIST="$HOME/Library/LaunchAgents/fr.jarvis.assistant.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.assistant_vocal"
cat > "$PLIST" <<FIN
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>fr.jarvis.assistant</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DOSSIER/.venv-jarvis/bin/python</string>
    <string>-m</string><string>assistant_vocal</string><string>--sans-navigateur</string>
  </array>
  <key>WorkingDirectory</key><string>$DOSSIER</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.assistant_vocal/jarvis.log</string>
  <key>StandardErrorPath</key><string>$HOME/.assistant_vocal/jarvis.log</string>
</dict>
</plist>
FIN
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
sleep 3
echo
echo "Jarvis tourne maintenant en arrière-plan et redémarrera avec le Mac."
echo "Ouvrez http://127.0.0.1:5050 (ou l'adresse Tailscale sur le téléphone)."
echo "Pour l'arrêter définitivement : double-cliquez sur arreter_demarrage_auto_mac.command"
open "http://127.0.0.1:5050"
