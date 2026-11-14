#!/bin/zsh
# Controla Spotify de la Mac (sin gastar tokens extra).
# Uso:
#   spotify.sh play | pausa | siguiente | anterior | que-suena
#   spotify.sh volumen 0-100
#   spotify.sh playlist "nombre"      -> busca en playlists.txt (nombre | link) y la pone
#   spotify.sh link "https://open.spotify.com/playlist/..."  -> pone ese link (playlist, álbum o canción)
#   spotify.sh guardar "nombre" "link" -> guarda una playlist en playlists.txt
#   spotify.sh lista                  -> playlists guardadas
LISTA="$HOME/claude-telegram/playlists.txt"
touch "$LISTA"

abrir() {
  pgrep -x Spotify >/dev/null || { open -g -a Spotify; for i in {1..20}; do pgrep -x Spotify >/dev/null && break; sleep 0.5; done; sleep 2; }
}

a_uri() { # convierte link de open.spotify.com a spotify:tipo:id
  local l="$1"
  if [[ "$l" == spotify:* ]]; then echo "$l"; return; fi
  l="${l%%\?*}"; l="${l#*open.spotify.com/}"; l="${l#intl-*/}"
  local tipo="${l%%/*}" id="${l#*/}"; id="${id%%/*}"
  [ -n "$tipo" ] && [ -n "$id" ] && echo "spotify:$tipo:$id"
}

poner() {
  abrir
  osascript -e "tell application \"Spotify\" to play track \"$1\"" && sleep 1 && \
  osascript -e 'tell application "Spotify" to if player state is playing then return "Sonando: " & (name of current track) & " — " & (artist of current track)'
}

case "$1" in
  play)      abrir; osascript -e 'tell application "Spotify" to play'; echo "▶️ Play" ;;
  pausa)     osascript -e 'tell application "Spotify" to pause'; echo "⏸ Pausa" ;;
  siguiente) osascript -e 'tell application "Spotify" to next track'; sleep 1; "$0" que-suena ;;
  anterior)  osascript -e 'tell application "Spotify" to previous track'; sleep 1; "$0" que-suena ;;
  que-suena) osascript -e 'tell application "Spotify" to if player state is playing then return "Sonando: " & (name of current track) & " — " & (artist of current track)' -e 'return "No está sonando nada"' ;;
  volumen)   osascript -e "tell application \"Spotify\" to set sound volume to ${2:-50}"; echo "🔊 Volumen ${2:-50}" ;;
  link)      u=$(a_uri "$2"); [ -z "$u" ] && { echo "Link no válido"; exit 1; }; poner "$u" ;;
  guardar)   u=$(a_uri "$3"); [ -z "$u" ] && { echo "Link no válido"; exit 1; }
             grep -iv "^$2 |" "$LISTA" > "$LISTA.tmp"; mv "$LISTA.tmp" "$LISTA"
             echo "$2 | $u" >> "$LISTA"; echo "Guardada: $2" ;;
  lista)     [ -s "$LISTA" ] && cut -d'|' -f1 "$LISTA" || echo "No hay playlists guardadas" ;;
  playlist)
    q="${2:l}"
    linea=$(grep -i "^$q *|" "$LISTA" | head -1)
    [ -z "$linea" ] && linea=$(grep -i "$q" "$LISTA" | head -1)
    if [ -z "$linea" ]; then echo "NO_GUARDADA: no tengo la playlist \"$2\". Pídele el link (Spotify > ••• > Compartir > Copiar enlace)."; exit 2; fi
    poner "${linea##*| }" ;;
  *) echo "Uso: spotify.sh play|pausa|siguiente|anterior|que-suena|volumen N|playlist NOMBRE|link URL|guardar NOMBRE URL|lista"; exit 1 ;;
esac
