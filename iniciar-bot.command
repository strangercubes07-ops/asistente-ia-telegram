#!/bin/zsh
# Inicia el bot de Telegram y mantiene la Mac despierta mientras corre.
# Si Claude se cierra o truena, lo vuelve a abrir solo a los 10 s (sin esperar al revividor).
# Para apagarlo a propósito: touch ~/claude-telegram/.no-revivir
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
cd "$HOME/claude-telegram" || exit 1
B="$HOME/claude-telegram"
LOG="$B/mantenimiento/revivir-bot.log"
avisar() {
  local TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$HOME/.claude/channels/telegram/.env" | cut -d= -f2- | tr -d '"')
  curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=$1" >/dev/null
}
# Si ya hay un bot corriendo, no abrir otro (dos bots se pelean).
pgrep -f "channels plugin:telegram" >/dev/null && { echo "Ya hay un bot corriendo."; exit 0; }
# Vigilante de WhatsApp (sin Claude, cero tokens). Se apaga solo en su fecha.
pgrep -fx "/bin/zsh $HOME/claude-telegram/vigilar-whatsapp.sh" >/dev/null || nohup "$HOME/claude-telegram/vigilar-whatsapp.sh" >>"$HOME/claude-telegram/vigilar-whatsapp.log" 2>&1 &!
# Mensajes programados de WhatsApp (sin Claude). Lee mensajes-programados.txt.
pgrep -fx "$HOME/claude-telegram/.whisper/bin/python $HOME/claude-telegram/programados.py" >/dev/null || nohup "$HOME/claude-telegram/.whisper/bin/python" "$HOME/claude-telegram/programados.py" >>"$HOME/claude-telegram/programados.log" 2>&1 &!
# Aviso de WhatsApp sin contestar (sin Claude, sin abrir la app). Mantiene WhatsApp oculto.
pgrep -fx "$HOME/claude-telegram/.whisper/bin/python $HOME/claude-telegram/sin-contestar.py" >/dev/null || nohup "$HOME/claude-telegram/.whisper/bin/python" "$HOME/claude-telegram/sin-contestar.py" >>"$HOME/claude-telegram/sin-contestar.log" 2>&1 &!
pgrep -f "claude-telegram/ayudante-whatsapp.py" >/dev/null || nohup "$HOME/claude-telegram/.whisper/bin/python" "$HOME/claude-telegram/ayudante-whatsapp.py" >>"$HOME/claude-telegram/ayudante-whatsapp.log" 2>&1 &!
# Oculta la ventana de Terminal (el bot sigue corriendo). Cmd+Tab → Terminal para verla.
( sleep 5; osascript -e 'tell application "System Events" to set visible of process "Terminal" to false' ) >/dev/null 2>&1 &!
while true; do
  # caffeinate -di: la Mac y la pantalla no se duermen mientras Claude esté abierto.
  caffeinate -di claude "Sesión nueva: sigue las instrucciones OBLIGATORIAS de CLAUDE.md al iniciar (crea los crons que falten: resumen de la mañana y cierre del día). No mandes nada por Telegram a menos que haya mensajes pendientes." --model sonnet --effort low --chrome --add-dir "$HOME/.claude/channels/telegram/inbox" "$HOME/claude-telegram/entregas" --channels plugin:telegram@claude-plugins-official
  CODIGO=$?
  [ -f "$B/.no-revivir" ] && break
  echo "$(date) Claude se cerró (código $CODIGO), reiniciando en 10 s" >> "$LOG"
  pkill -f "bun server.ts"   # que no quede el servidor viejo de Telegram pegado
  sleep 10
  [ -f "$B/.no-revivir" ] && break
  avisar "Jefe, el bot se cerró solo y ya lo estoy volviendo a abrir. Dame un minuto."
done
