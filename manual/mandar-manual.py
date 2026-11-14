#!/usr/bin/env python3
"""Manda MANUAL.md por Telegram, una sección por mensaje (cero tokens)."""
import os, time, urllib.parse, urllib.request

BASE = os.path.expanduser("~/claude-telegram")
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram

tok = next(l.split("=", 1)[1].strip().strip('"') for l in open(ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
partes = [p.strip() for p in open(os.path.join(BASE, "MANUAL.md"), encoding="utf-8").read().split("=====") if p.strip()]
for p in partes:
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": p}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)
    time.sleep(0.7)
print(f"Manual enviado ({len(partes)} mensajes)")
