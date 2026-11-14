#!/usr/bin/env python3
"""Idea 56: el bot llama POR el usuario. SOLO correrlo después de que el usuario dijo "sí".
  llamar.py --numero "+525512345678" --nombre "Pizzería X" --objetivo "preguntar a qué hora cierran hoy"
            [--datos "datos que sí puede dar, p. ej. reservación a nombre del usuario, 4 personas"]
El resumen llega solo por Telegram cuando termina la llamada."""
import argparse, json, os, re, sys, time, urllib.request, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import DIR, E, NOMBRE, NOMBRE_COMPLETO, claude, log, twilio, url_publica

TAREAS = os.path.join(DIR, "tareas")
MAX_DIA = 15
PROHIBIDOS = {"911", "089", "060", "065", "066", "080"}


def normalizar(n):
    d = re.sub(r"[^\d+]", "", n)
    if d.startswith("+"):
        pass
    elif len(d) == 10:
        d = "+52" + d
    elif d.startswith("52") and len(d) == 12:
        d = "+" + d
    elif d.startswith("1") and len(d) == 11:
        d = "+" + d
    if not re.fullmatch(r"\+(52\d{10}|1\d{10})", d):
        sys.exit(f"Número no válido o fuera de México/EE. UU.: {n}")
    return d


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--numero", required=True)
    a.add_argument("--nombre", required=True)
    a.add_argument("--objetivo", required=True)
    a.add_argument("--datos", default="")
    o = a.parse_args()
    if re.sub(r"\D", "", o.numero) in PROHIBIDOS:
        sys.exit("No hago llamadas a números de emergencia.")
    num = normalizar(o.numero)
    os.makedirs(TAREAS, exist_ok=True)
    hoy = datetime.now().strftime("%Y-%m-%d")
    if sum(1 for f in os.listdir(TAREAS) if f.startswith(hoy)) >= MAX_DIA:
        sys.exit(f"Ya van {MAX_DIA} llamadas hoy; es el límite.")
    url = url_publica()
    try:
        # se revisa en local: la Mac a veces guarda en caché que el dominio nuevo del túnel "no existe"
        assert url and urllib.request.urlopen("http://127.0.0.1:8787/salud", timeout=10).read() == b"ok"
    except Exception:
        sys.exit("El servidor de llamadas no está listo (revisa llamadas/llamadas.log).")
    h = datetime.now().hour
    saludo_h = "Buenos días" if h < 12 else "Buenas tardes" if h < 19 else "Buenas noches"
    saludo = claude(
        f"Eres el asistente virtual de {NOMBRE_COMPLETO} y vas a hablar por teléfono. Escribe SOLO tu primera frase "
        f"al contestar la otra persona: empieza con '{saludo_h}', di que eres el asistente virtual de {NOMBRE} y "
        f"plantea el objetivo en una o dos frases cortas y naturales. Sin comillas ni emojis.",
        f"Llamas a: {o.nombre}. Objetivo: {o.objetivo}") or \
        f"{saludo_h}, le llamo como asistente virtual de {NOMBRE}. Quería {o.objetivo}."
    tid = f"{hoy}-{uuid.uuid4().hex[:8]}"
    t = {"id": tid, "numero": num, "nombre": o.nombre, "objetivo": o.objetivo, "datos": o.datos,
         "saludo": saludo.strip().strip('"'), "creada": datetime.now().isoformat(timespec="seconds")}
    json.dump(t, open(os.path.join(TAREAS, tid + ".json"), "w"), ensure_ascii=False, indent=1)
    r = twilio("Calls.json", {
        "To": num, "From": E["TWILIO_NUMERO"], "Url": f"{url}/inicio?id={tid}", "Method": "POST",
        "StatusCallback": f"{url}/estado?id={tid}", "StatusCallbackMethod": "POST",
        "Timeout": "30", "TimeLimit": "420"})
    if not r.get("sid"):
        sys.exit("Twilio no aceptó la llamada: " + r.get("message", str(r)))
    log(f"saliente {tid} a {o.nombre} {num}: {r['sid']}")
    print(f"📞 Llamando a {o.nombre} ({num}). Primera frase: \"{t['saludo']}\". "
          f"El resumen llegará solo por Telegram al colgar.")


if __name__ == "__main__":
    main()
