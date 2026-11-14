#!/usr/bin/env python3
"""Mensajes programados de WhatsApp (sin Claude, cero tokens).

Lo arranca iniciar-bot.command desde Terminal (Terminal tiene el permiso para leer WhatsApp).
Cola: ~/claude-telegram/mensajes-programados.txt, una línea por mensaje:
    AAAA-MM-DD HH:MM | Nombre como sale en WhatsApp | texto del mensaje
Líneas que empiezan con "#prueba " se validan y se registran en el log, sin mandar ni avisar.
Cada 20 s revisa la cola. Avisa por Telegram cuando programa, cuando manda y si falla.
"""
import hashlib, json, os, sqlite3, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime

BASE = os.path.expanduser("~/claude-telegram")
COLA = os.path.join(BASE, "mensajes-programados.txt")
HECHOS = os.path.join(BASE, "mensajes-enviados.txt")
VISTOS = os.path.join(BASE, ".programados-vistos.json")
LOG = os.path.join(BASE, "programados.log")
DB = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram
TARDE_MAX = 30 * 60      # si la Mac estaba dormida y ya pasaron más de 30 min, no lo manda
EPOCH_2001 = 978307200   # fechas de WhatsApp (Core Data) cuentan desde 2001


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def token():
    for line in open(ENV):
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"')


def telegram(texto):
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texto}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token()}/sendMessage", data=data, timeout=20)
    except Exception as e:
        log(f"error Telegram: {e}")


def db():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)


def buscar_contacto(nombre):
    """Devuelve (session_pk, numero, nombre_real) o None. Solo chats individuales."""
    with db() as c:
        # WhatsApp nuevo usa IDs "@lid"; el número viene en ZCONTACTIDENTIFIER.
        filas = c.execute("select Z_PK, case when ZCONTACTIDENTIFIER like '%@s.whatsapp.net' then ZCONTACTIDENTIFIER "
                          "else ZCONTACTJID end, ZPARTNERNAME from ZWACHATSESSION where ZSESSIONTYPE=0 and "
                          "(ZCONTACTIDENTIFIER like '%@s.whatsapp.net' or ZCONTACTJID like '%@s.whatsapp.net')").fetchall()
    limpio = lambda t: (t or "").replace("\u200e", "").replace("\u200f", "").strip().lower()
    n = limpio(nombre)
    if n in ("yo", "mi", "mí", "a mi", "a mí", "mi chat", "tu", "tú"):
        n = "tú"   # chat personal de WhatsApp
    exactos = [f for f in filas if limpio(f[2]) == n]
    parecidos = [f for f in filas if n in limpio(f[2])]
    elegido = exactos[0] if exactos else (parecidos[0] if len(parecidos) == 1 else None)
    if not elegido:
        return None, [f[2] for f in parecidos[:5]]
    return (elegido[0], elegido[1].split("@")[0], elegido[2]), []


def ya_enviado(session_pk, texto, desde):
    with db() as c:
        f = c.execute("select count(*) from ZWAMESSAGE where ZCHATSESSION=? and ZISFROMME=1 "
                      "and ZMESSAGEDATE>=? and ZTEXT=?", (session_pk, desde - EPOCH_2001 - 5, texto)).fetchone()
    return f[0] > 0


def mandar(numero, texto):
    url = "whatsapp://send?" + urllib.parse.urlencode({"phone": numero, "text": texto}, quote_via=urllib.parse.quote)
    subprocess.run(["open", url], check=True)
    time.sleep(6)
    subprocess.run(["osascript",
                    "-e", 'tell application "WhatsApp" to activate',
                    "-e", "delay 1",
                    "-e", 'tell application "System Events" to tell process "WhatsApp" to key code 36'],
                   check=True, capture_output=True)


def leer_cola():
    if not os.path.exists(COLA):
        return []
    out = []
    for linea in open(COLA, encoding="utf-8"):
        linea = linea.rstrip("\n")
        if not linea.strip():
            continue
        prueba = linea.startswith("#prueba ")
        partes = [p.strip() for p in (linea[8:] if prueba else linea).split("|", 2)]
        out.append((linea, prueba, partes))
    return out


def quitar_de_cola(linea, resultado):
    lineas = [l for l in open(COLA, encoding="utf-8").read().split("\n") if l.strip() and l != linea]
    with open(COLA, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + ("\n" if lineas else ""))
    with open(HECHOS, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M} [{resultado}] {linea}\n")


def diagnostico(nombre):
    with db() as c:
        cols = [r[1] for r in c.execute("pragma table_info(ZWACHATSESSION)")]
        log("DIAG columnas ZWACHATSESSION: " + ", ".join(cols))
        sufijos = c.execute("select substr(ZCONTACTJID, instr(ZCONTACTJID,'@')), ZSESSIONTYPE, count(*) "
                            "from ZWACHATSESSION group by 1,2").fetchall()
        log(f"DIAG sufijos: {sufijos}")
        for r in c.execute("select * from ZWACHATSESSION where ZPARTNERNAME like ?", (f"%{nombre}%",)):
            fila = {k: v for k, v in zip(cols, r) if v not in (None, 0, "")}
            if "ZCONTACTJID" in fila:
                j = str(fila["ZCONTACTJID"]); fila["ZCONTACTJID"] = j[:3] + "…" + j[-18:]
            log(f"DIAG fila: {fila}")
        tablas = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
        log("DIAG tablas: " + ", ".join(tablas))


def ciclo(vistos):
    ahora = time.time()
    for linea, prueba, partes in leer_cola():
        if linea.startswith("#nombres "):
            pats = [x.strip() for x in linea[9:].split(",") if x.strip()]
            with db() as c:
                for pat in pats:
                    rs = c.execute("select ZPARTNERNAME, ZSESSIONTYPE, ZCONTACTIDENTIFIER like '%@s.whatsapp.net' "
                                   "from ZWACHATSESSION where ZPARTNERNAME like ?", (f"%{pat}%",)).fetchall()
                    log(f"NOMBRES '{pat}': {rs}")
            quitar_de_cola(linea, "nombres")
            continue
        if linea.startswith("#diag "):
            try:
                diagnostico(linea[6:].strip())
            except Exception as e:
                log(f"DIAG error: {e}")
            quitar_de_cola(linea, "diag")
            continue
        clave = hashlib.sha1(linea.encode()).hexdigest()
        if len(partes) != 3 or not all(partes):
            log(f"línea mal escrita: {linea}")
            if not prueba:
                telegram(f"Jefe, no entendí este mensaje programado y lo quité:\n{linea}")
            quitar_de_cola(linea, "mal escrito")
            continue
        cuando_txt, nombre, texto = partes
        try:
            cuando = datetime.strptime(cuando_txt, "%Y-%m-%d %H:%M").timestamp()
        except ValueError:
            log(f"fecha inválida: {linea}")
            if not prueba:
                telegram(f"Jefe, la fecha de este mensaje programado está mal y lo quité:\n{linea}")
            quitar_de_cola(linea, "fecha inválida")
            continue
        contacto, sugerencias = buscar_contacto(nombre)
        if not contacto:
            extra = f" ¿Será alguno de estos? {', '.join(sugerencias)}" if sugerencias else ""
            log(f"no encontré contacto '{nombre}'{extra}")
            if not prueba:
                telegram(f"Jefe, no encontré a \"{nombre}\" en tus chats de WhatsApp, no programé el mensaje.{extra}")
            quitar_de_cola(linea, "contacto no encontrado")
            continue
        pk, numero, real = contacto
        if prueba:
            log(f"PRUEBA ok: '{nombre}' → {real} (…{numero[-4:]}), {cuando_txt}")
            quitar_de_cola(linea, "prueba")
            continue
        if clave not in vistos:
            vistos[clave] = ahora
            json.dump(vistos, open(VISTOS, "w"))
            log(f"programado: {real} {cuando_txt}")
            telegram(f"📅 Programado: a {real}, el {cuando_txt}:\n\"{texto}\"")
        if ahora < cuando:
            continue
        if ahora - cuando > TARDE_MAX:
            log(f"muy tarde, no enviado: {linea}")
            telegram(f"Jefe, no mandé el mensaje a {real} de las {cuando_txt}: la compu estaba dormida y ya era muy tarde. Dime si lo mando ahora.")
            quitar_de_cola(linea, "no enviado (tarde)")
            continue
        inicio = time.time()
        try:
            mandar(numero, texto)
            time.sleep(4)
            ok = ya_enviado(pk, texto, inicio)
        except Exception as e:
            log(f"error al mandar: {e}")
            ok = False
        if ok:
            log(f"enviado a {real}")
            telegram(f"✅ Ya le mandé a {real}: \"{texto}\"")
            quitar_de_cola(linea, "enviado")
        else:
            log(f"no pude confirmar envío a {real}")
            telegram(f"⚠️ Intenté mandarle a {real} pero no pude confirmar que se envió. Revisa WhatsApp.")
            quitar_de_cola(linea, "sin confirmar")


def una_sola_copia():
    import fcntl
    global _LOCK
    _LOCK = open(os.path.join(BASE, ".lock-programados"), "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)  # ya hay otra copia corriendo


def main():
    una_sola_copia()
    log("programados iniciado")
    vistos = json.load(open(VISTOS)) if os.path.exists(VISTOS) else {}
    while True:
        try:
            ciclo(vistos)
        except Exception as e:
            log(f"error: {e}")
        time.sleep(20)


if __name__ == "__main__":
    main()
