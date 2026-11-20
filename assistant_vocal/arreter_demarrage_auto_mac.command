#!/bin/bash
# Double-cliquez (Mac) : arrête Jarvis et retire son démarrage automatique.
PLIST="$HOME/Library/LaunchAgents/fr.jarvis.assistant.plist"
launchctl unload "$PLIST" 2>/dev/null
rm -f "$PLIST"
echo "Jarvis est arrêté et ne démarrera plus tout seul."
