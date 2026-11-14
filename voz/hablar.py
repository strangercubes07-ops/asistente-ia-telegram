#!/usr/bin/env python3
"""Manda una nota de voz por Telegram con voz de IA local (Piper, es_ES-davefx).

Uso: ~/claude-telegram/hablar.sh CHAT_ID "Texto que se va a decir"
Opcional: VOZ=nombre_modelo (archivo en ~/claude-telegram/voces/NOMBRE.onnx)
"""
import os
import subprocess
import sys
import tempfile

import av

BASE = os.path.expanduser("~/claude-telegram")
VOZ = os.environ.get("VOZ", "es_ES-davefx-medium")
MODELO = os.path.join(BASE, "voces", VOZ + ".onnx")
PIPER = os.path.join(BASE, ".whisper", "bin", "piper")
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")

if len(sys.argv) != 3 or not sys.argv[2].strip():
    sys.exit('Uso: hablar.sh CHAT_ID "texto"')
chat_id, texto = sys.argv[1], sys.argv[2]

token = None
with open(ENV) as f:
    for line in f:
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip()
if not token:
    sys.exit("No encontré TELEGRAM_BOT_TOKEN")

with tempfile.TemporaryDirectory() as tmp:
    wav = os.path.join(tmp, "voz.wav")
    oga = os.path.join(tmp, "voz.ogg")
    subprocess.run([PIPER, "-m", MODELO, "-f", wav], input=texto, text=True,
                   check=True, capture_output=True)

    src = av.open(wav)
    dst = av.open(oga, "w", format="ogg")
    stream = dst.add_stream("libopus", rate=48000)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
    for frame in src.decode(audio=0):
        for f2 in resampler.resample(frame):
            for pkt in stream.encode(f2):
                dst.mux(pkt)
    for pkt in stream.encode(None):
        dst.mux(pkt)
    dst.close()
    src.close()

    r = subprocess.run(
        ["curl", "-s", "-F", f"chat_id={chat_id}", "-F", f"voice=@{oga}",
         f"https://api.telegram.org/bot{token}/sendVoice"],
        capture_output=True, text=True,
    )
    ok = '"ok":true' in r.stdout
    print("nota de voz enviada" if ok else "error al enviar: " + r.stdout[:200])
    sys.exit(0 if ok else 1)
