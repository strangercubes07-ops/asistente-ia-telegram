#!/usr/bin/env python3
"""Memoria total (idea 48): guarda TODO lo que se dijo por Telegram (tú y el bot) en
~/claude-telegram/memoria/telegram-AAAA-MM.md, para poder buscarlo aunque Claude borre sesiones viejas.
Corre cada noche (respaldo.sh) y el bot lo puede correr antes de buscar. Sin tokens."""
import glob, hashlib, json, os, re
from datetime import datetime, timezone

BASE = os.path.expanduser("~/claude-telegram")
DIR = os.path.join(BASE, "memoria")
VISTOS = os.path.join(DIR, ".vistos.json")
PROY = os.path.expanduser("~/.claude/projects/" + os.path.expanduser("~/claude-telegram").replace("/", "-"))
TAG = re.compile(r'<channel source="[^"]*telegram"[^>]*?message_id="(\d+)"[^>]*?ts="([^"]+)"[^>]*>\n?(.*?)\n?</channel>', re.S)


def local(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")


def main():
    os.makedirs(DIR, exist_ok=True)
    vistos = set(json.load(open(VISTOS))) if os.path.exists(VISTOS) else set()
    nuevos = []
    for f in glob.glob(os.path.join(PROY, "*.jsonl")):
        for linea in open(f, encoding="utf-8", errors="ignore"):
            if "telegram" not in linea:
                continue
            try:
                d = json.loads(linea)
            except Exception:
                continue
            if isinstance(d.get("content"), str):  # mensajes en cola
                for mid, ts, cuerpo in TAG.findall(d["content"]):
                    if "u" + mid not in vistos:
                        vistos.add("u" + mid)
                        nuevos.append((local(ts), "Yo", cuerpo.strip()))
            msg = d.get("message")
            if not isinstance(msg, dict):
                continue
            c = msg.get("content")
            partes = [c] if isinstance(c, str) else [x for x in (c or []) if isinstance(x, dict)]
            for p in partes:
                if isinstance(p, str) or p.get("type") == "text":
                    texto = p if isinstance(p, str) else p.get("text", "")
                    if d.get("type") != "user":
                        continue
                    for mid, ts, cuerpo in TAG.findall(texto):
                        clave = "u" + mid
                        if clave not in vistos:
                            vistos.add(clave)
                            nuevos.append((local(ts), "Yo", cuerpo.strip()))
                elif p.get("type") == "tool_use" and p.get("name", "").endswith("telegram__reply"):
                    t = (p.get("input") or {}).get("text", "")
                    clave = "b" + hashlib.sha1((p.get("id", "") + t).encode()).hexdigest()[:16]
                    if t and clave not in vistos:
                        vistos.add(clave)
                        ts = d.get("timestamp") or datetime.now(timezone.utc).isoformat()
                        nuevos.append((local(ts), "Bot", t.strip()))
    nuevos.sort()
    for fecha, quien, texto in nuevos:
        with open(os.path.join(DIR, f"telegram-{fecha[:7]}.md"), "a", encoding="utf-8") as out:
            out.write(f"[{fecha}] {quien}: {texto}\n")
    json.dump(sorted(vistos), open(VISTOS, "w"))
    print(f"{len(nuevos)} mensajes nuevos guardados en memoria/")


if __name__ == "__main__":
    main()
