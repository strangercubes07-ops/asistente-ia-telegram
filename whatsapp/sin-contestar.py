#!/usr/bin/env python3
"""Aviso de mensajes de WhatsApp sin contestar (sin Claude, sin abrir la app, cero tokens).

Lo arranca iniciar-bot.command desde Terminal (Terminal tiene permiso de leer WhatsApp).
Revisa a las 9:13, 12:13, 15:13, 18:13 y 21:13. Avisa por Telegram de los chats individuales
donde lo último es de la otra persona y lleva más de 1 hora (de los últimos 2 días).
Si sigue sin contestar, vuelve a avisar en la siguiente revisión.
Además mantiene WhatsApp abierto pero OCULTO para que siga recibiendo mensajes.
Revisar en este momento: touch ~/claude-telegram/.revisar-ahora (lo detecta en menos de 1 min).
"""
import os, sqlite3, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime

BASE = os.path.expanduser("~/claude-telegram")
LOG = os.path.join(BASE, "sin-contestar.log")
DB = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram
HORAS = {9, 12, 15, 18, 21}
MINUTO = 13
EPOCH_2001 = 978307200
UNA_HORA, DOS_DIAS = 3600, 2 * 86400


def log(m):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {m}\n")


def telegram(texto):
    tok = next(l.split("=", 1)[1].strip().strip('"') for l in open(ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texto}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)


def whatsapp_oculto():
    """Si WhatsApp no está corriendo, lo abre oculto (sin ventana al frente)."""
    if subprocess.run(["pgrep", "-x", "WhatsApp"], capture_output=True).returncode != 0:
        subprocess.run(["open", "-g", "-j", "-a", "WhatsApp"])
        log("WhatsApp estaba cerrado; lo abrí oculto")


def limpio(t):
    return (t or "").replace("‎", "").replace("‏", "").strip()


def pendientes():
    ahora = time.time()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    filas = con.execute("""
        select s.ZPARTNERNAME, s.ZUNREADCOUNT, m.ZMESSAGEDATE, m.ZTEXT
        from ZWACHATSESSION s join ZWAMESSAGE m on m.Z_PK = s.ZLASTMESSAGE
        where s.ZSESSIONTYPE = 0 and coalesce(s.ZARCHIVED,0) = 0 and coalesce(s.ZREMOVED,0) = 0
          and coalesce(s.ZHIDDEN,0) = 0 and m.ZISFROMME = 0
          and coalesce(m.ZMESSAGETYPE,0) not in (6,10)
        order by m.ZMESSAGEDATE desc""").fetchall()
    con.close()
    out = []
    ign = set()
    try:
        ign = {l.strip() for l in open(os.path.join(BASE, "sin-contestar-ignorados.txt"))}
    except OSError:
        pass
    for nombre, no_leidos, fecha, texto in filas:
        nombre = limpio(nombre)
        if f"{nombre}|{int(fecha)}" in ign:
            continue  # ignorado hasta que escriba un mensaje nuevo
        if not nombre or nombre.lower() == "tú":
            continue
        espera = ahora - (fecha + EPOCH_2001)
        if UNA_HORA <= espera <= DOS_DIAS:
            out.append((nombre, espera, no_leidos or 0, (texto or "(foto/audio/sticker)").replace("\n", " ")[:60]))
    return out


def hace(seg):
    h = int(seg // 3600)
    return f"{h} h" if h < 24 else f"{h // 24} día{'s' if h >= 48 else ''}"


def revisar():
    whatsapp_oculto()
    ps = pendientes()
    log(f"revisión: {len(ps)} sin contestar")
    if not ps:
        return
    lineas = [f"• {n} — hace {hace(e)}{' (no leído)' if u else ''}: {t}" for n, e, u, t in ps[:15]]
    extra = f"\n…y {len(ps) - 15} más" if len(ps) > 15 else ""
    telegram("Jefe, tienes gente en visto, qué poca. Contéstales:\n" + "\n".join(lineas) + extra)


def una_sola_copia():
    import fcntl
    global _LOCK
    _LOCK = open(os.path.join(BASE, ".lock-sin-contestar"), "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)  # ya hay otra copia corriendo


def main():
    una_sola_copia()
    if len(sys.argv) > 1 and sys.argv[1] == "ignorar":
        ahora = time.time()
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
        filas = con.execute("select s.ZPARTNERNAME, m.ZMESSAGEDATE from ZWACHATSESSION s join ZWAMESSAGE m on m.Z_PK = s.ZLASTMESSAGE where s.ZSESSIONTYPE = 0 and m.ZISFROMME = 0").fetchall()
        con.close()
        with open(os.path.join(BASE, "sin-contestar-ignorados.txt"), "a") as f:
            for n, d in filas:
                f.write(f"{limpio(n)}|{int(d)}\n")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "ahora":
        revisar(); return
    log("aviso sin contestar iniciado")
    marca = os.path.join(BASE, ".sin-contestar-ultimo")
    ultimo = open(marca).read().strip() if os.path.exists(marca) else None
    while True:
        try:
            whatsapp_oculto()
            t = datetime.now()
            clave = t.strftime("%Y-%m-%d %H")
            gatillo = os.path.join(BASE, ".revisar-ahora")
            if os.path.exists(gatillo):
                os.remove(gatillo)
                revisar()
            elif t.hour in HORAS and t.minute >= MINUTO and clave != ultimo:
                ultimo = clave
                open(marca, "w").write(clave)
                revisar()
        except Exception as e:
            log(f"error: {e}")
        time.sleep(60)


if __name__ == "__main__":
    main()
