#!/usr/bin/env python3
"""Ayudante de WhatsApp (sin Claude, cero tokens). Lo arranca iniciar-bot.command desde Terminal
(Terminal tiene permiso de leer WhatsApp y de Accesibilidad; Claude no).

1) MODO FUERA (idea 49)
   - Activar:   touch ~/claude-telegram/.modo-fuera
   - Apagar:    rm ~/claude-telegram/.modo-fuera   (manda resumen por Telegram)
   Mientras está activo, a cada chat individual que escriba le contesta UNA vez:
   "Estoy fuera, en un rato te contesto con calma."  Se apaga solo a las 12 h.
   La compu tiene que estar DESBLOQUEADA para poder mandar.

2) BUSCAR EN WHATSAPP (idea 48)
   ~/claude-telegram/buscar-whatsapp.sh "palabra" ["contacto"]
"""
import json, os, sqlite3, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime

BASE = os.path.expanduser("~/claude-telegram")
LOG = os.path.join(BASE, "ayudante-whatsapp.log")
DB = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram
EPOCH_2001 = 978307200
FLAG = os.path.join(BASE, ".modo-fuera")
ESTADO = os.path.join(BASE, ".modo-fuera-estado.json")
BUSCAR = os.path.join(BASE, ".buscar-wa")
BUSCAR_RES = os.path.join(BASE, ".buscar-wa-resultado")
TEXTO = "Estoy fuera, en un rato te contesto con calma."
MAX_HORAS = 12


def log(m):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {m}\n")


def telegram(texto):
    try:
        tok = next(l.split("=", 1)[1].strip().strip('"') for l in open(ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
        data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texto}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)
    except Exception as e:
        log(f"error Telegram: {e}")


def db():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)


def limpio(t):
    return (t or "").replace("‎", "").replace("‏", "").strip()


# ---------------- MODO FUERA ----------------
def nuevos_desde(inicio):
    with db() as c:
        return c.execute("""
            select s.Z_PK, s.ZPARTNERNAME, s.ZCONTACTIDENTIFIER, count(*), max(m.ZMESSAGEDATE)
            from ZWAMESSAGE m join ZWACHATSESSION s on s.Z_PK = m.ZCHATSESSION
            where m.ZISFROMME = 0 and s.ZSESSIONTYPE = 0 and m.ZMESSAGEDATE > ?
              and coalesce(m.ZMESSAGETYPE,0) not in (6,10)
              and coalesce(s.ZREMOVED,0) = 0 and coalesce(s.ZHIDDEN,0) = 0
            group by s.Z_PK""", (inicio - EPOCH_2001,)).fetchall()


def ya_enviado(pk, desde):
    with db() as c:
        return c.execute("select count(*) from ZWAMESSAGE where ZCHATSESSION=? and ZISFROMME=1 and ZMESSAGEDATE>=? and ZTEXT=?",
                         (pk, desde - EPOCH_2001 - 5, TEXTO)).fetchone()[0] > 0


def mandar(numero):
    url = "whatsapp://send?" + urllib.parse.urlencode({"phone": numero, "text": TEXTO}, quote_via=urllib.parse.quote)
    subprocess.run(["open", url], check=True)
    time.sleep(6)
    subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate', "-e", "delay 1",
                    "-e", 'tell application "System Events" to tell process "WhatsApp" to key code 36'],
                   check=True, capture_output=True, timeout=30)


def guardar(est):
    json.dump(est, open(ESTADO, "w"), ensure_ascii=False)


def modo_fuera():
    est = json.load(open(ESTADO)) if os.path.exists(ESTADO) else None
    if not os.path.exists(FLAG):
        if est:  # se acaba de apagar → resumen
            esc = est.get("escribieron", {})
            if esc:
                lineas = [f"• {n} ({k} msj){' ✅ le contesté' if n in est['contestados'].values() else ''}" for n, k in esc.items()]
                telegram("🏠 Modo fuera apagado. Mientras no estabas te escribieron:\n" + "\n".join(lineas))
            else:
                telegram("🏠 Modo fuera apagado. Nadie te escribió por WhatsApp mientras no estabas.")
            if est.get("fallos"):
                telegram("⚠️ A estos no les pude mandar la respuesta automática (¿compu bloqueada?): " + ", ".join(est["fallos"]))
            os.remove(ESTADO)
            log("modo fuera apagado")
        return
    if not est:
        est = {"inicio": os.path.getmtime(FLAG), "contestados": {}, "escribieron": {}, "fallos": []}
        guardar(est)
        log("modo fuera activado")
    if time.time() - est["inicio"] > MAX_HORAS * 3600:
        os.remove(FLAG)
        telegram(f"⏰ Ya pasaron {MAX_HORAS} h, apagué el modo fuera solo.")
        return
    subprocess.run(["open", "-g", "-j", "-a", "WhatsApp"]) if subprocess.run(["pgrep", "-x", "WhatsApp"], capture_output=True).returncode else None
    for pk, nombre, ident, cuantos, _ in nuevos_desde(est["inicio"]):
        nombre = limpio(nombre) or "?"
        if nombre.lower() == "tú":
            continue
        est["escribieron"][nombre] = cuantos
        if str(pk) in est["contestados"] or nombre in est["fallos"]:
            continue
        if not ident or "@s.whatsapp.net" not in ident:
            log(f"sin número para {nombre}, no contesto")
            est["fallos"].append(nombre)
            continue
        inicio = time.time()
        try:
            mandar(ident.split("@")[0])
            time.sleep(4)
            ok = ya_enviado(pk, inicio)
        except Exception as e:
            log(f"error al mandar a {nombre}: {e}")
            ok = False
        if ok:
            est["contestados"][str(pk)] = nombre
            log(f"contesté automático a {nombre}")
        else:
            est["fallos"].append(nombre)
            log(f"no pude contestar a {nombre}")
    guardar(est)


# ---------------- BUSCAR ----------------
def buscar(palabra, contacto):
    q = """select m.ZMESSAGEDATE, s.ZPARTNERNAME, s.ZSESSIONTYPE, m.ZISFROMME, m.ZPUSHNAME, m.ZTEXT
           from ZWAMESSAGE m join ZWACHATSESSION s on s.Z_PK = m.ZCHATSESSION
           where m.ZTEXT like ? """
    args = [f"%{palabra}%"]
    if contacto:
        q += " and s.ZPARTNERNAME like ?"
        args.append(f"%{contacto}%")
    q += " order by m.ZMESSAGEDATE desc limit 40"
    with db() as c:
        filas = c.execute(q, args).fetchall()
    out = []
    for fecha, chat, tipo, mio, push, texto in filas:
        f = datetime.fromtimestamp(fecha + EPOCH_2001).strftime("%Y-%m-%d %H:%M")
        quien = "yo" if mio else (limpio(push) or limpio(chat)) if tipo == 1 else ("yo" if mio else limpio(chat))
        out.append(f"{f} | {limpio(chat)}{' (grupo)' if tipo == 1 else ''} | {quien}: {(texto or '').replace(chr(10), ' ')[:300]}")
    return "\n".join(out) or "SIN RESULTADOS"


def una_sola_copia():
    import fcntl
    global _LOCK
    _LOCK = open(os.path.join(BASE, ".lock-ayudante-whatsapp"), "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)


def main():
    una_sola_copia()
    log("ayudante iniciado")
    n = 0
    while True:
        try:
            if os.path.exists(BUSCAR):
                partes = (open(BUSCAR).read().strip().split("\n") + [""])[:2]
                os.remove(BUSCAR)
                open(BUSCAR_RES, "w").write(buscar(partes[0].strip(), partes[1].strip()) + "\n")
            if n % 10 == 0:  # modo fuera cada ~20 s
                modo_fuera()
        except Exception as e:
            log(f"error: {e}")
        n += 1
        time.sleep(2)


if __name__ == "__main__":
    main()
