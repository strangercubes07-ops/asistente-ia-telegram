#!/usr/bin/env python3
"""Servidor de llamadas con IA (ideas 56 y "llámame").
Lo mantiene vivo el LaunchAgent com.claude-telegram.llamadas.
- Abre un túnel de Cloudflare (cloudflared) para que Twilio llegue a esta compu.
- /inicio  : llamada saliente que hace el bot por el usuario (llamar.py).
- /entrante: alguien marca al número. Solo platica si es el cel del usuario.
Cada turno: Twilio reconoce la voz -> Claude (haiku, sin herramientas) responde -> Twilio lo dice.
Todas las peticiones se validan con la firma de Twilio."""
import json, os, re, subprocess, sys, threading, time, urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun
from comun import (DIR, E, NOMBRE, NOMBRE_COMPLETO, URL_FILE, VOZ, claude, decir, firma_valida, hoy_texto, log,
                   pendientes, telegram, twilio, x)

PUERTO = 8787
TAREAS = os.path.join(DIR, "tareas")
REGISTRO = os.path.join(DIR, "registro")
CF = os.path.join(DIR, "bin", "cloudflared")
SES = {}  # CallSid -> sesión
LOCK = threading.Lock()

REGLAS = """Hablas por teléfono: tu respuesta se convierte en voz. Reglas:
- Responde SOLO con lo que vas a decir, en español de México natural, 1 o 2 frases cortas. Sin emojis, sin listas, sin markdown.
- Si no entendiste algo, pide que lo repitan.
- Cuando la conversación termine (ya lograste el objetivo, o se despidieron, o no se puede), despídete y escribe [COLGAR] al final."""


def sistema_saliente(t):
    return f"""Eres el asistente virtual de {NOMBRE_COMPLETO}. Estás llamando por teléfono a: {t['nombre']}.
Objetivo de la llamada: {t['objetivo']}
Datos que SÍ puedes dar si te los piden: {t.get('datos') or 'solo el nombre ' + NOMBRE_COMPLETO}.
Fecha y hora actual: {hoy_texto()} {datetime.now():%H:%M}.
- Preséntate como asistente virtual de {NOMBRE}. Nunca digas que eres {NOMBRE} ni que eres humano.
- Limítate al objetivo: no hagas preguntas extra que no te encargaron.
- No inventes datos. Si te preguntan algo que no sabes, di que {NOMBRE} se comunicará después.
- No des datos personales extra (dirección, correo, documentos, tarjetas), no aceptes pagos ni compromisos de dinero.
- Si contesta un buzón de voz o una grabadora, deja un mensaje de una frase con el objetivo y [COLGAR].
{REGLAS}"""


def sistema_usuario():
    ps = pendientes(10)
    return f"""Eres el bot asistente de {NOMBRE} (le hablas de tú, tono amigable). {NOMBRE} te llamó por teléfono.
Fecha y hora actual: {hoy_texto()} {datetime.now():%Y-%m-%d %H:%M}.
Sus pendientes: {'; '.join(ps) if ps else 'ninguno'}.
Puedes hacer estas acciones escribiendo la etiqueta en tu respuesta (él no la oye):
- Anotar un pendiente: [PENDIENTE: texto]
- Programar una llamada de recordatorio: [RECORDATORIO: AAAA-MM-DD HH:MM | texto]
- Algo que necesita la compu o internet (WhatsApp, Classroom, buscar, mandar mensajes): dile que se lo dejas por Telegram y escribe [TELEGRAM: lo que pidió]
Confirma en voz lo que anotaste. No inventes información que no tienes.
{REGLAS}"""


def guardar_registro(s):
    os.makedirs(REGISTRO, exist_ok=True)
    json.dump(s, open(os.path.join(REGISTRO, f"{s['inicio'][:10]}-{s['sid']}.json"), "w"),
              ensure_ascii=False, indent=1)


def transcripcion(s):
    otro = comun.NOMBRE if s["tipo"] == "usuario" else "Persona"
    return "\n".join(f"{'Bot' if q == 'bot' else otro}: {t}" for q, t in s["turnos"])


def acciones(s, texto):
    for p in re.findall(r"\[PENDIENTE:\s*(.+?)\]", texto):
        with open(os.path.join(comun.BASE, "mis-pendientes.md"), "a") as f:
            f.write(f"- [ ] {p.strip()}\n")
        s["acciones"].append(f"📝 Anoté: {p.strip()}")
    for cuando, t in re.findall(r"\[RECORDATORIO:\s*(\d{4}-\d\d-\d\d \d\d:\d\d)\s*\|\s*(.+?)\]", texto):
        r = subprocess.run([sys.executable, os.path.join(DIR, "recordar.py"), cuando, t.strip()],
                           capture_output=True, text=True)
        s["acciones"].append("⏰ " + (r.stdout.strip() or r.stderr.strip()))
    for p in re.findall(r"\[TELEGRAM:\s*(.+?)\]", texto):
        s["acciones"].append(f"📲 Me pediste: {p.strip()}  (reenvíamelo aquí para hacerlo)")
    return re.sub(r"\[(PENDIENTE|RECORDATORIO|TELEGRAM):.*?\]", "", texto)


def pensar(s):
    """Corre en un hilo: genera la siguiente frase del bot."""
    try:
        sis = sistema_usuario() if s["tipo"] == "usuario" else sistema_saliente(s["tarea"])
        msg = f"Conversación hasta ahora:\n{transcripcion(s)}\n\nTu siguiente frase:"
        r = claude(sis, msg)
    except Exception as e:
        log(f"error claude {s['sid']}: {e}")
        r = ""
    if not r:
        r = "Perdón, tuve un problema. Luego nos comunicamos. Hasta luego. [COLGAR]"
    r = r.strip().strip('"')
    colgar = "[COLGAR]" in r
    r = acciones(s, r.replace("[COLGAR]", "")).strip()
    s["turnos"].append(("bot", r))
    s["respuesta"], s["colgar"] = r, colgar


def escuchar(sid, antes=""):
    return (f'<Response>{antes}<Gather input="speech" language="es-MX" speechTimeout="auto" timeout="6" '
            f'action="/turno?sid={sid}" method="POST" actionOnEmptyResult="true"></Gather>'
            f'<Redirect method="POST">/silencio?sid={sid}</Redirect></Response>')


def esperar(sid, n):
    extra = decir("Mmm, un momento.") if n == 4 else ""
    return f'<Response>{extra}<Pause length="1"/><Redirect method="POST">/espera?sid={sid}&amp;n={n}</Redirect></Response>'


def fin_llamada(s, estado, dur):
    if s.get("avisado"):
        return
    s["avisado"] = True
    s["estado"], s["duracion"] = estado, dur
    guardar_registro(s)
    tr = transcripcion(s)
    if s["tipo"] == "usuario":
        txt = f"📞 Hablamos por teléfono ({dur} s)."
        if s["acciones"]:
            txt += "\n\n" + "\n".join(s["acciones"])
        if tr:
            txt += f"\n\nConversación:\n{tr}"
        telegram(txt)
        return
    t = s["tarea"]
    if not s["turnos"] or estado in ("no-answer", "busy", "failed", "canceled"):
        motivo = {"no-answer": "nadie contestó", "busy": "estaba ocupado", "failed": "falló la llamada",
                  "canceled": "se canceló"}.get(estado, "no hubo conversación")
        telegram(f"📞 Llamada a {t['nombre']}: {motivo}. ¿Quieres que vuelva a intentar?")
        return
    try:
        res = claude("Resume llamadas telefónicas en español, para el usuario que las encargó. 2 a 4 líneas: "
                     "qué se logró, datos importantes (horas, precios, nombres) y si falta algo. Sin markdown.",
                     f"Objetivo: {t['objetivo']}\n\nConversación:\n{tr}", timeout=60)
    except Exception:
        res = ""
    telegram(f"📞 Llamada a {t['nombre']} terminada ({dur} s).\n\n{res or 'Abajo va la conversación.'}"
             f"\n\nConversación:\n{tr}")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, cuerpo, tipo="text/xml"):
        b = cuerpo.encode()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/salud":
            return self.responder("ok", "text/plain")
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        p = dict(urllib.parse.parse_qsl(self.rfile.read(largo).decode(), keep_blank_values=True))
        url = comun.url_publica() + self.path
        if not firma_valida(url, p, self.headers.get("X-Twilio-Signature")):
            log(f"firma inválida {self.path}")
            self.send_response(403)
            self.end_headers()
            return
        ruta, _, qs = self.path.partition("?")
        q = dict(urllib.parse.parse_qsl(qs))
        try:
            self.responder(self.manejar(ruta, q, p))
        except Exception as e:
            log(f"error {ruta}: {e}")
            self.responder(f"<Response>{decir('Perdón, tuve un problema. Hasta luego.')}<Hangup/></Response>")

    def manejar(self, ruta, q, p):
        sid = p.get("CallSid", "")
        if ruta == "/inicio":
            t = json.load(open(os.path.join(TAREAS, os.path.basename(q["id"]) + ".json")))
            s = {"sid": sid, "tipo": "saliente", "tarea": t, "turnos": [("bot", t["saludo"])], "acciones": [],
                 "inicio": datetime.now().isoformat(timespec="seconds")}
            with LOCK:
                SES[sid] = s
            return escuchar(sid, '<Pause length="1"/>' + decir(t["saludo"]))
        if ruta == "/entrante":
            if p.get("From") != E["MI_CEL"]:
                log(f"entrante rechazada de {p.get('From')}")
                return f"<Response>{decir('Este número no recibe llamadas. Adiós.')}<Hangup/></Response>"
            hola = f"Hola {NOMBRE}, aquí tu bot. ¿Qué necesitas?"
            s = {"sid": sid, "tipo": "usuario", "turnos": [("bot", hola)], "acciones": [],
                 "inicio": datetime.now().isoformat(timespec="seconds")}
            with LOCK:
                SES[sid] = s
            return escuchar(sid, decir(hola))
        s = SES.get(q.get("sid", sid))
        if ruta == "/estado":
            s = SES.get(sid)
            if s is None and q.get("id"):  # nadie contestó: nunca pasó por /inicio
                t = json.load(open(os.path.join(TAREAS, os.path.basename(q["id"]) + ".json")))
                s = {"sid": sid, "tipo": "saliente", "tarea": t, "turnos": [], "acciones": [],
                     "inicio": datetime.now().isoformat(timespec="seconds")}
            if s:
                threading.Thread(target=fin_llamada, args=(s, p.get("CallStatus"), p.get("CallDuration", "0")),
                                 daemon=True).start()
            return "<Response/>"
        if s is None:
            return f"<Response>{decir('Perdón, se perdió la llamada. Hasta luego.')}<Hangup/></Response>"
        if ruta == "/turno":
            dicho = p.get("SpeechResult", "").strip()
            if not dicho:
                return self.manejar("/silencio", q, p)
            s["silencios"] = 0
            s["turnos"].append(("otro", dicho))
            s["respuesta"] = None
            threading.Thread(target=pensar, args=(s,), daemon=True).start()
            return esperar(s["sid"], 1)
        if ruta == "/espera":
            n = int(q.get("n", "1"))
            if s.get("respuesta") is None:
                if n > 25:
                    return f"<Response>{decir('Perdón, tengo problemas. Hasta luego.')}<Hangup/></Response>"
                return esperar(s["sid"], n + 1)
            r = s["respuesta"]
            if s.get("colgar"):
                return f"<Response>{decir(r)}<Hangup/></Response>"
            return escuchar(s["sid"], decir(r))
        if ruta == "/silencio":
            s["silencios"] = s.get("silencios", 0) + 1
            if s["silencios"] >= 3:
                return f"<Response>{decir('Parece que no se escucha. Hasta luego.')}<Hangup/></Response>"
            return escuchar(s["sid"], decir("¿Bueno? ¿Me escucha?"))
        return "<Response/>"


def tunel():
    """Arranca cloudflared y regresa (proceso, url pública)."""
    pr = subprocess.Popen([CF, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PUERTO}"],
                          stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    fin = time.time() + 60
    while time.time() < fin:
        l = pr.stderr.readline()
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", l)
        if m:
            threading.Thread(target=lambda: [None for _ in pr.stderr], daemon=True).start()
            return pr, m.group(0)
    pr.kill()
    raise RuntimeError("cloudflared no dio URL")


def main():
    os.makedirs(TAREAS, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PUERTO), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pr, url = tunel()
    open(URL_FILE, "w").write(url)
    r = twilio(f"IncomingPhoneNumbers/{E['TWILIO_NUMERO_SID']}.json",
               {"VoiceUrl": url + "/entrante", "VoiceMethod": "POST",
                "StatusCallback": url + "/estado", "StatusCallbackMethod": "POST"})
    log(f"servidor listo {url} (número actualizado: {bool(r.get('voice_url'))})")
    while pr.poll() is None:
        time.sleep(5)
    log("cloudflared se cayó; reinicio")
    try:
        os.remove(URL_FILE)
    except FileNotFoundError:
        pass
    sys.exit(1)  # launchd lo vuelve a arrancar


if __name__ == "__main__":
    main()
