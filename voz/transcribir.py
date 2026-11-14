#!/usr/bin/env python3
"""Transcribe un audio (nota de voz de Telegram, mp3, m4a, etc.) a texto.

Uso: ~/claude-telegram/transcribir.sh ARCHIVO_DE_AUDIO
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")

from faster_whisper import WhisperModel

if len(sys.argv) != 2 or not os.path.isfile(sys.argv[1]):
    sys.exit("Uso: transcribir.sh ARCHIVO_DE_AUDIO")

here = os.path.dirname(os.path.abspath(__file__))
model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8",
    download_root=os.path.join(here, ".whisper-models"),
)
segments, info = model.transcribe(sys.argv[1], beam_size=5, vad_filter=True)
print(" ".join(s.text.strip() for s in segments).strip())
