#!/bin/zsh
# Reinicia solo la sesión de Claude del bot (el ciclo de iniciar-bot.command la vuelve a abrir con el CLAUDE.md nuevo).
pkill -f "channels plugin:telegram"
