#!/usr/bin/env python3
"""Lo corre el LaunchAgent com.claude-telegram.recordatorios cada minuto (cero tokens).
Hace las llamadas de recordatorio que ya tocan y la llamada diaria de la mañana."""
import fcntl, json, os, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import DIR, E, NOMBRE, decir, hoy_texto, log, pendientes, telegram, twilio

ARCH = os.path.join(DIR, "recordatorios.json")
CONF = os.path.join(DIR, "config.json")
ULTIMA = os.path.join(DIR, ".manana-ultima")
TARDE = timedelta(minutes=30)  # si la compu estaba apagada más de esto, no llama tarde


def llamar(twiml):
    r = twilio("Calls.json", {"To": E["MI_CEL"], "From": E["TWILIO_NUMERO"], "Twiml": twiml,
                              "Timeout": "40", "TimeLimit": "180"})
    return r.get("sid"), r.get("message", "")


def recordatorios(ahora):
    if not os.path.exists(ARCH):
        return
    rs = json.load(open(ARCH))
    cambio = False
    for r in rs["lista"]:
        if r["estado"] != "pendiente":
            continue
        cuando = datetime.strptime(r["cuando"], "%Y-%m-%d %H:%M")
        if cuando > ahora:
            continue
        cambio = True
        if ahora - cuando > TARDE:
            r["estado"] = "perdido"
            telegram(f"⚠️ No pude llamarte a las {cuando:%H:%M} (la compu estaba apagada o dormida).\n"
                     f"Era para recordarte: {r['texto']}")
            continue
        tw = (f"<Response><Pause length=\"1\"/>{decir(f'Hola {NOMBRE}, te llamo para recordarte: ' + r['texto'])}"
              f"<Pause length=\"1\"/>{decir('Repito: ' + r['texto'])}{decir('Adiós.')}</Response>")
        sid, err = llamar(tw)
        r["estado"] = "llamado" if sid else "error"
        log(f"recordatorio {r['n']} -> {sid or err}")
        if sid:
            telegram(f"📞 Te llamé para recordarte: {r['texto']}")
        else:
            telegram(f"⚠️ No pude hacer la llamada para recordarte: {r['texto']}\n({err})")
    if cambio:
        json.dump(rs, open(ARCH, "w"), ensure_ascii=False, indent=1)


def manana(ahora):
    c = json.load(open(CONF)) if os.path.exists(CONF) else {}
    h = c.get("manana", "off")
    if h == "off":
        return
    hoy = ahora.strftime("%Y-%m-%d")
    if os.path.exists(ULTIMA) and open(ULTIMA).read().strip() == hoy:
        return
    cuando = datetime.strptime(hoy + " " + h, "%Y-%m-%d %H:%M")
    if not (cuando <= ahora <= cuando + TARDE):
        return
    open(ULTIMA, "w").write(hoy)
    ps = pendientes(6)
    if ps:
        lista = " ".join(f"{i}: {p}." for i, p in enumerate(ps, 1))
        cuerpo = f"Tienes {len(ps)} pendientes. {lista}"
    else:
        cuerpo = "No tienes pendientes anotados. Día libre."
    tw = (f"<Response><Pause length=\"1\"/>{decir(f'Buenos días {NOMBRE}. Hoy es {hoy_texto(ahora)}.')}"
          f"<Pause length=\"1\"/>{decir(cuerpo)}<Pause length=\"1\"/>"
          f"{decir('El resumen completo te lo mandé por Telegram. Que tengas un buen día.')}</Response>")
    sid, err = llamar(tw)
    log(f"llamada mañana -> {sid or err}")


def main():
    lock = open(os.path.join(DIR, ".lock-revisar"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    ahora = datetime.now().replace(second=0, microsecond=0)
    for f in (recordatorios, manana):
        try:
            f(ahora)
        except Exception as e:
            log(f"error {f.__name__}: {e}")


if __name__ == "__main__":
    main()
