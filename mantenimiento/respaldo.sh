#!/bin/zsh
# Respaldo nocturno (LaunchAgent com.claude-telegram.respaldo, 23:30) a iCloud Drive.
# Guarda los últimos 14 días. NO respalda el token del bot ni el de Spotify.
B="$HOME/claude-telegram"
DEST="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Respaldo bot Telegram"
HOY=$(date +%Y-%m-%d)
/usr/bin/python3 "$B/archivar-chats.py" >/dev/null 2>&1   # memoria total (idea 48)
TMP=$(mktemp -d)
mkdir -p "$TMP/bot" "$TMP/memoria-bot" "$TMP/telegram"
rsync -a --exclude '.whisper' --exclude '.whisper-models' --exclude 'voces' --exclude '*.log' \
  --exclude '.spotify-token.json' --exclude '.env' "$B/" "$TMP/bot/"
rsync -a "$HOME/.claude/projects/${PROYECTO_CLAUDE}/memory/" "$TMP/memoria-bot/" 2>/dev/null
cp "$HOME/.claude/channels/telegram/access.json" "$TMP/telegram/" 2>/dev/null
cp "$HOME/Library/LaunchAgents/"com.claude-telegram.*.plist "$TMP/telegram/" 2>/dev/null
mkdir -p "$DEST" || { echo "$(date) no pude crear $DEST"; exit 1; }
(cd "$TMP" && zip -qr "$DEST/respaldo-$HOY.zip" .) && echo "$(date) respaldo-$HOY.zip ok ($(du -h "$DEST/respaldo-$HOY.zip" | cut -f1))"
rm -rf "$TMP"
ls -1t "$DEST"/respaldo-*.zip 2>/dev/null | tail -n +15 | while read -r f; do rm -f "$f"; done
