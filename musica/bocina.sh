#!/bin/zsh
# Uso: ~/claude-telegram/bocina.sh lista | conectar "Nombre" | salida "Nombre" | desconectar "Nombre"
# Corre Bocina.app (tiene su propio permiso de Bluetooth). Sale con 1 si falló.
OUT=$(mktemp -t bocina)
/usr/bin/open -W -n --stdout "$OUT" --stderr "$OUT" "$HOME/claude-telegram/Bocina.app" --args "$@"
cat "$OUT"
grep -qE "^(No pude|No encontré|Se conectó .* pero)" "$OUT"; r=$?
rm -f "$OUT"
[ $r -eq 0 ] && exit 1 || exit 0
