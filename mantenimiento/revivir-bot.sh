#!/bin/zsh
# Revisa cada 2 min (LaunchAgent com.claude-telegram.revivir) que el bot siga vivo.
# Si se cayó, lo vuelve a arrancar y avisa por Telegram.
# Para pausarlo a propósito: touch ~/claude-telegram/.no-revivir   (y borrarlo para reactivar)
B="$HOME/claude-telegram"
LOG="$B/mantenimiento/revivir-bot.log"
[ -f "$B/.no-revivir" ] && exit 0

vivo() { pgrep -f "channels plugin:telegram" >/dev/null && pgrep -f "bun server.ts" >/dev/null; }

vivo && exit 0
sleep 60            # por si justo se estaba reiniciando
vivo && exit 0

echo "$(date) bot caído, reiniciando" >> "$LOG"
pkill -f "iniciar-bot.command"; pkill -f "channels plugin:telegram"; pkill -f "bun server.ts"; sleep 2
osascript -e 'tell application "Terminal" to close (every window whose busy is false)' 2>/dev/null
launchctl kickstart "gui/$(id -u)/com.claude-telegram.bot"
for i in {1..45}; do vivo && break; sleep 2; done

TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$HOME/.claude/channels/telegram/.env" | cut -d= -f2- | tr -d '"')
if vivo; then MSG="Jefe, el bot se había caído y ya lo reviví. Todo bien."; else MSG="Jefe, el bot se cayó y no pude revivirlo. Revisa la compu."; fi
echo "$(date) $MSG" >> "$LOG"
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=$MSG" >/dev/null
