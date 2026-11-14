#!/bin/zsh
# Vigila mensajes nuevos de WhatsApp SOLO de los contactos en contactos-vigilados.txt
# (un nombre por línea, como aparece en WhatsApp), leyendo la base local
# (sin Claude, cero tokens) y avisa por Telegram directo con la API del bot.
# Si la lista está vacía, no avisa nada. Lo arranca iniciar-bot.command. Log: vigilar-whatsapp.log
DB="$HOME/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite"
CHAT_ID=${TELEGRAM_CHAT_ID}
TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$HOME/.claude/channels/telegram/.env" | cut -d= -f2- | tr -d '"')
STATE="$HOME/claude-telegram/vigilancia-whatsapp.last"
LISTA="$HOME/claude-telegram/contactos-vigilados.txt"
BASE="m.ZISFROMME=0 and s.ZSESSIONTYPE=0 and coalesce(m.ZMESSAGETYPE,0) not in (6,10)"
FILTRO="$BASE"

echo "$(date) vigilante de WhatsApp iniciado"
[ -s "$STATE" ] || sqlite3 -readonly "$DB" "select coalesce(max(m.Z_PK),0) from ZWAMESSAGE m join ZWACHATSESSION s on m.ZCHATSESSION=s.Z_PK where $BASE;" > "$STATE"

while true; do
  # Formato de cada línea: "Nombre" (sin límite) o "Nombre | AAAA-MM-DD HH:MM" (hasta esa fecha).
  NOMBRES=""; QUEDAN=""; VENCIDOS=""; AHORA=$(date +%s)
  [ -f "$LISTA" ] && while IFS= read -r linea || [ -n "$linea" ]; do
    [ -z "${linea//[[:space:]]/}" ] && continue
    n="${linea%%|*}"; n="${n## }"; n="${n%% }"
    hasta=""; [[ "$linea" == *"|"* ]] && { hasta="${linea#*|}"; hasta="${hasta## }"; hasta="${hasta%% }"; }
    if [ -n "$hasta" ]; then
      fin=$(date -j -f "%Y-%m-%d %H:%M" "$hasta" +%s 2>/dev/null)
      if [ -n "$fin" ] && [ "$fin" -le "$AHORA" ]; then VENCIDOS="${VENCIDOS:+$VENCIDOS, }$n"; continue; fi
    fi
    QUEDAN="${QUEDAN}${linea}"$'\n'
    q="'"; n="${n//$q/$q$q}"
    [ -n "$n" ] && NOMBRES="${NOMBRES:+$NOMBRES,}lower('$n')"
  done < "$LISTA"
  if [ -n "$VENCIDOS" ]; then
    printf '%s' "$QUEDAN" > "$LISTA.tmp" && mv "$LISTA.tmp" "$LISTA"
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${CHAT_ID}" --data-urlencode "text=Jefe, ya se acabó el tiempo: dejé de vigilar a ${VENCIDOS}." >/dev/null
    echo "$(date) vencidos: $VENCIDOS"
  fi
  if [ -z "$NOMBRES" ]; then FILTRO="$BASE and 0"; else FILTRO="$BASE and lower(s.ZPARTNERNAME) in ($NOMBRES)"; fi
  LAST=$(cat "$STATE")
  MAX=$(sqlite3 -readonly "$DB" "select coalesce(max(m.Z_PK),0) from ZWAMESSAGE m join ZWACHATSESSION s on m.ZCHATSESSION=s.Z_PK where $BASE;")
  if [ -n "$MAX" ] && [ "$MAX" -gt "${LAST:-0}" ]; then
    NUEVOS=$(sqlite3 -readonly "$DB" "select '• ' || coalesce(s.ZPARTNERNAME,'Alguien') || ': ' || substr(replace(coalesce(m.ZTEXT,'(foto/audio/sticker)'),char(10),' '),1,200) from ZWAMESSAGE m join ZWACHATSESSION s on m.ZCHATSESSION=s.Z_PK where $FILTRO and m.Z_PK > ${LAST:-0} and m.Z_PK <= $MAX order by m.ZMESSAGEDATE limit 15;")
    if [ -n "$NUEVOS" ]; then
      TXT="Jefe, te escribieron en WhatsApp, ponte vivo y contesta:
$NUEVOS"
      curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${CHAT_ID}" --data-urlencode "text=${TXT:0:3900}" >/dev/null
    fi
    echo "$MAX" > "$STATE"
  fi
  sleep 120
done
