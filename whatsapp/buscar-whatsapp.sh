#!/bin/zsh
# Busca mensajes de WhatsApp. Uso: buscar-whatsapp.sh "palabra" ["contacto o grupo"]
B="$HOME/claude-telegram"
[ -z "$1" ] && { echo 'Uso: buscar-whatsapp.sh "palabra" ["contacto"]'; exit 1; }
rm -f "$B/.buscar-wa-resultado"
printf '%s\n%s\n' "$1" "$2" > "$B/.buscar-wa"
for i in {1..30}; do [ -f "$B/.buscar-wa-resultado" ] && { cat "$B/.buscar-wa-resultado"; rm -f "$B/.buscar-wa-resultado"; exit 0; }; sleep 1; done
echo "ERROR el ayudante de WhatsApp no respondió"; exit 1
