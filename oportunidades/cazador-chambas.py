#!/usr/bin/env python3
"""Cazador de chambas de IA (idea 57) — parte automática, sin Claude, cero tokens.
LaunchAgent com.claude-telegram.chambas lo corre cada 2 h. Busca en LinkedIn (vacantes públicas)
chambas de IA/automatización de medio tiempo, freelance o prácticas en México/remoto, y avisa por Telegram.
Workana/Fiverr/Reddit los revisa el bot (cron de Claude) porque bloquean scripts.
Todas las chambas quedan numeradas en ~/claude-telegram/chambas.json (el bot las usa para propuestas)."""
import html, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime

BASE = os.path.expanduser("~/claude-telegram")
DATA = os.path.join(BASE, "chambas.json")
LOG = os.path.join(BASE, "mantenimiento", "cazador-chambas.log")
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
BUSQUEDAS = [
    "inteligencia artificial medio tiempo", "inteligencia artificial freelance", "becario inteligencia artificial",
    "practicante IA", "chatbot freelance", "automatización freelance", "prompt", "AI trainer spanish",
    "asistente IA medio tiempo", "ChatGPT",
]
NO = re.compile(r"\b(senior|sr\.?|semi ?senior|ssr|lead|l[ií]der|manager|gerente|director|head|architect|arquitect[oa]|"
                r"principal|staff|scientist|cient[ií]fic[oa]|ingenier[oa] de datos|data engineer|sap|java|\.net|devops|"
                r"ventas|sales|vendedor|ejecutiv[oa] de cuenta|abogad[oa]|m[eé]dic[oa]|enfermer[oa]|contador)\b", re.I)
SI = re.compile(r"(\bia\b|i\.a\.|inteligencia artificial|\bai\b|chatbot|gpt|prompt|automatiza|llm|machine learning|bot\b|no-?code|n8n|zapier)", re.I)
MAX_AVISO = 6


def log(m):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {m}\n")


def telegram(texto):
    tok = next(l.split("=", 1)[1].strip().strip('"') for l in open(ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texto, "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)


def linkedin(q):
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(
        {"keywords": q, "location": "Mexico", "f_TPR": "r86400"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9"})
    s = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
    out = []
    for c in s.split("<li>")[1:]:
        g = lambda p: (lambda m: html.unescape(m.group(1)).strip() if m else "")(re.search(p, c, re.S))
        titulo = g(r'base-search-card__title">\s*(.*?)\s*<')
        link = g(r'href="(https://[a-z]+\.linkedin\.com/jobs/view/[^"?]+)')
        if titulo and link:
            out.append({"titulo": titulo, "empresa": g(r'base-search-card__subtitle">.*?>\s*(.*?)\s*<'),
                        "lugar": g(r'job-search-card__location">\s*(.*?)\s*<'), "link": link, "fuente": "LinkedIn"})
    return out


def main():
    d = json.load(open(DATA)) if os.path.exists(DATA) else {"siguiente": 1, "chambas": [], "pendientes_aviso": []}
    vistos = {c["link"] for c in d["chambas"]}
    nuevas = []
    for q in BUSQUEDAS:
        try:
            for c in linkedin(q):
                if c["link"] in vistos or NO.search(c["titulo"]) or not SI.search(c["titulo"] + " " + q):
                    continue
                if not SI.search(c["titulo"]):  # el título debe ser de IA/automatización
                    continue
                vistos.add(c["link"])
                c.update(n=d["siguiente"], fecha=datetime.now().strftime("%Y-%m-%d %H:%M"), estado="nueva")
                d["siguiente"] += 1
                d["chambas"].append(c)
                nuevas.append(c["n"])
        except Exception as e:
            log(f"error '{q}': {e}")
        time.sleep(3)
    d["pendientes_aviso"] += nuevas
    hora = datetime.now().hour
    if d["pendientes_aviso"] and 8 <= hora < 23:
        por_n = {c["n"]: c for c in d["chambas"]}
        lista = [por_n[n] for n in d["pendientes_aviso"] if n in por_n][:MAX_AVISO]
        extra = len(d["pendientes_aviso"]) - len(lista)
        txt = "💸 OPORTUNIDAD DE GENERAR CACHETE — chambas de IA nuevas:\n\n" + "\n\n".join(
            f"{c['n']}. {c['titulo']} — {c['empresa']} ({c['lugar']})\n{c['link']}" for c in lista)
        if extra > 0:
            txt += f"\n\n…y {extra} más (pídeme \"chambas pendientes\")."
        txt += "\n\nDime \"propuesta para la N\" o \"aplícame a la N\"."
        try:
            telegram(txt)
            d["pendientes_aviso"] = []
        except Exception as e:
            log(f"error Telegram: {e}")
    d["chambas"] = d["chambas"][-300:]
    json.dump(d, open(DATA, "w"), ensure_ascii=False, indent=1)
    log(f"revisión: {len(nuevas)} nuevas")


if __name__ == "__main__":
    main()
