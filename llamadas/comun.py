"""Cosas compartidas de las llamadas (Twilio + Telegram + Claude). Solo librería estándar."""
import base64, hashlib, hmac, json, os, re, subprocess, urllib.parse, urllib.request
from datetime import datetime
from xml.sax.saxutils import escape

BASE = os.path.expanduser("~/claude-telegram")
DIR = os.path.join(BASE, "llamadas")
LOG = os.path.join(DIR, "llamadas.log")
URL_FILE = os.path.join(DIR, ".url")
TG_ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram
NOMBRE = os.environ.get("BOT_NOMBRE", "Usuario")
NOMBRE_COMPLETO = os.environ.get("BOT_NOMBRE_COMPLETO", NOMBRE)
VOZ = 'language="es-MX" voice="Polly.Mia"'
CLAUDE = os.path.expanduser("~/.local/bin/claude")
VACIO = os.path.join(DIR, "vacio")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def env():
    d = {}
    for l in open(os.path.join(BASE, ".twilio.env")):
        if "=" in l:
            k, v = l.strip().split("=", 1)
            d[k] = v
    return d


E = env()


def log(m):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {m}\n")


def twilio(ruta, datos=None, metodo=None):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{E['TWILIO_ACCOUNT_SID']}/{ruta}"
    body = urllib.parse.urlencode(datos).encode() if datos else None
    req = urllib.request.Request(url, data=body, method=metodo)
    tok = base64.b64encode(f"{E['TWILIO_ACCOUNT_SID']}:{E['TWILIO_AUTH_TOKEN']}".encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def telegram(texto):
    tok = next(l.split("=", 1)[1].strip().strip('"') for l in open(TG_ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
    for i in range(0, len(texto), 3900):
        data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texto[i:i + 3900],
                                       "disable_web_page_preview": "true"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)


def firma_valida(url, params, firma):
    s = url + "".join(k + params[k] for k in sorted(params))
    calc = base64.b64encode(hmac.new(E["TWILIO_AUTH_TOKEN"].encode(), s.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(calc, firma or "")


def claude(sistema, mensaje, modelo="haiku", timeout=40):
    os.makedirs(VACIO, exist_ok=True)
    r = subprocess.run([CLAUDE, "-p", "--model", modelo, "--tools", "", "--strict-mcp-config",
                        "--no-session-persistence", "--system-prompt", sistema, mensaje],
                       cwd=VACIO, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


def x(t):
    return escape(t, {'"': "&quot;"})


def decir(t):
    return f"<Say {VOZ}>{x(t)}</Say>"


def hoy_texto(d=None):
    d = d or datetime.now()
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def pendientes(maximo=8):
    try:
        ls = [re.sub(r"^\s*-\s*\[ \]\s*", "", l).strip() for l in open(os.path.join(BASE, "mis-pendientes.md"))
              if re.match(r"^\s*-\s*\[ \]", l)]
    except FileNotFoundError:
        ls = []
    return ls[:maximo]


def url_publica():
    try:
        return open(URL_FILE).read().strip()
    except FileNotFoundError:
        return ""
