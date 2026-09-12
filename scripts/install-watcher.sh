#!/bin/bash
# Make macOS run scripts/update.sh whenever a file lands in whatsapp_chat/.
#
#   ./scripts/install-watcher.sh          install and start
#   ./scripts/install-watcher.sh remove   stop and uninstall
#
# After this, updating the standings is: AirDrop the export from your phone, save it into
# whatsapp_chat/, and walk away. The rebuild, commit and push happen on their own, and you
# get a notification saying who is leading.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
LABEL="gg.maptap.standings"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$ROOT/.watcher.log"

if [ "${1:-}" = "remove" ]; then
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null
  rm -f "$PLIST"
  echo "watcher removed."
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST_END
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$ROOT/scripts/update.sh</string>
  </array>
  <key>WatchPaths</key>
  <array><string>$ROOT/whatsapp_chat</string></array>
  <key>ThrottleInterval</key><integer>20</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MAPTAP_WATCHED</key><string>1</string>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST_END

launchctl bootout "gui/$UID/$LABEL" 2>/dev/null
if launchctl bootstrap "gui/$UID" "$PLIST" 2>/dev/null || launchctl load "$PLIST" 2>/dev/null; then
  echo "watcher installed."
  echo
  echo "  drop an export into  $ROOT/whatsapp_chat/"
  echo "  log                  $LOG"
  echo "  remove               ./scripts/install-watcher.sh remove"
  echo
  echo "Git needs to be able to push without prompting. If you normally type a password,"
  echo "set up an SSH key or the macOS credential helper first, or the push step will stall."
else
  echo "could not load the agent; the plist is at $PLIST" >&2
  exit 1
fi
