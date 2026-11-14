#!/usr/bin/env python3
"""Recordatorios por llamada (cero tokens).
  recordar.py "AAAA-MM-DD HH:MM" "texto"   -> programa una llamada
  recordar.py lista                        -> muestra los pendientes
  recordar.py borrar N                     -> cancela el número N
  recordar.py manana HH:MM | manana off    -> hora de la llamada diaria de la mañana
  recordar.py ahora "texto"                -> llama ya (prueba)"""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import DIR

ARCH = os.path.join(DIR, "recordatorios.json")
CONF = os.path.join(DIR, "config.json")


def cargar(p, defecto):
    return json.load(open(p)) if os.path.exists(p) else defecto


def guardar(p, d):
    json.dump(d, open(p, "w"), ensure_ascii=False, indent=1)


def main(a):
    rs = cargar(ARCH, {"siguiente": 1, "lista": []})
    if not a or a[0] == "lista":
        p = [r for r in rs["lista"] if r["estado"] == "pendiente"]
        print("\n".join(f"{r['n']}. {r['cuando']} — {r['texto']}" for r in p) or "Sin recordatorios por llamada.")
        c = cargar(CONF, {})
        print("Llamada de la mañana:", c.get("manana", "off"))
        return
    if a[0] == "borrar":
        for r in rs["lista"]:
            if str(r["n"]) == a[1] and r["estado"] == "pendiente":
                r["estado"] = "cancelado"
                guardar(ARCH, rs)
                print(f"Cancelado: {r['cuando']} — {r['texto']}")
                return
        print("No encontré ese número.")
        return
    if a[0] == "manana":
        c = cargar(CONF, {})
        if a[1] != "off":
            datetime.strptime(a[1], "%H:%M")
        c["manana"] = a[1]
        guardar(CONF, c)
        print("Llamada de la mañana:", a[1])
        return
    if a[0] == "ahora":
        cuando, texto = datetime.now().strftime("%Y-%m-%d %H:%M"), " ".join(a[1:])
    else:
        cuando, texto = a[0], " ".join(a[1:])
        datetime.strptime(cuando, "%Y-%m-%d %H:%M")
    if not texto.strip():
        sys.exit("Falta el texto del recordatorio.")
    r = {"n": rs["siguiente"], "cuando": cuando, "texto": texto.strip(), "estado": "pendiente"}
    rs["siguiente"] += 1
    rs["lista"].append(r)
    rs["lista"] = rs["lista"][-200:]
    guardar(ARCH, rs)
    print(f"Listo: te llamo el {cuando} para recordarte: {texto} (número {r['n']})")


if __name__ == "__main__":
    main(sys.argv[1:])
