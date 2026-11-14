#!/usr/bin/env python3
"""Idea 66: arma el CV en PDF (español e inglés) desde cv.md y cv-en.md, con Chrome (cero tokens).
Uso: python3 cv.py [enviar]   -> con "enviar" manda los dos PDFs por Telegram.
Formato de los .md: '# Nombre', 2 líneas de subtítulo/contacto, '## Sección', '### Título | Fecha', '- punto', texto suelto."""
import html, os, re, subprocess, sys, tempfile

DIR = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram
CSS = """
@page { size: Letter; margin: 15mm 16mm; }
* { box-sizing: border-box; }
body { font: 10.5pt -apple-system, "Helvetica Neue", sans-serif; color: #1c2024; margin: 0; line-height: 1.4; }
h1 { font-size: 24pt; margin: 0; color: #1e2a78; letter-spacing: -.5px; }
.sub { font-weight: 600; color: #3b4fd8; margin: 2px 0; font-size: 11.5pt; }
.contacto { color: #555; font-size: 9.5pt; margin: 2px 0 10px; }
hr { border: 0; border-top: 2.5px solid #3b4fd8; margin: 4px 0 6px; }
h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: 1.2px; color: #1e2a78; margin: 14px 0 4px;
     border-bottom: 1px solid #d6dbf5; padding-bottom: 2px; }
.item { display: flex; justify-content: space-between; font-weight: 700; margin: 7px 0 2px; }
.item span { font-weight: 500; color: #666; white-space: nowrap; margin-left: 12px; }
ul { margin: 2px 0 4px 0; padding-left: 16px; }
li { margin: 1.5px 0; }
p { margin: 3px 0; }
section { break-inside: avoid; }
"""


def esc(t):
    t = html.escape(t)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def a_html(md):
    ls = [l.rstrip() for l in open(md, encoding="utf-8")]
    out, lista, cab = [], False, 0
    for l in ls:
        if not l.strip():
            continue
        if not l.startswith("- ") and lista:
            out.append("</ul>")
            lista = False
        if l.startswith("# "):
            out.append(f"<h1>{esc(l[2:])}</h1>")
            cab = 1
        elif cab in (1, 2) and not l.startswith("#"):
            out.append(f'<div class="{"sub" if cab == 1 else "contacto"}">{esc(l)}</div>')
            cab += 1
            if cab == 3:
                out.append("<hr>")
        elif l.startswith("## "):
            cab = 0
            out.append(f"<h2>{esc(l[3:])}</h2>")
        elif l.startswith("### "):
            t, _, f = l[4:].partition("|")
            out.append(f'<div class="item">{esc(t.strip())}<span>{esc(f.strip())}</span></div>')
        elif l.startswith("- "):
            if not lista:
                out.append("<ul>")
                lista = True
            out.append(f"<li>{esc(l[2:])}</li>")
        else:
            out.append(f"<p>{esc(l)}</p>")
    if lista:
        out.append("</ul>")
    return "".join(out)


def pdf(md, salida):
    doc = f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{a_html(md)}</body></html>'
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={salida}", "file://" + f.name], check=True, capture_output=True, timeout=90)
    os.remove(f.name)
    return salida


def main():
    hechos = [pdf(os.path.join(DIR, "cv.md"), os.path.join(DIR, "CV.pdf")),
              pdf(os.path.join(DIR, "cv-en.md"), os.path.join(DIR, "CV (English).pdf"))]
    print("PDFs listos:", *hechos, sep="\n  ")
    if sys.argv[1:] == ["enviar"]:
        tok = next(l.split("=", 1)[1].strip().strip('"') for l in open(ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
        for p, cap in zip(hechos, ["📄 Tu CV en español", "📄 Your CV in English"]):
            r = subprocess.run(["curl", "-s", "-F", f"chat_id={CHAT_ID}", "-F", f"document=@{p}",
                                "--form-string", f"caption={cap}",
                                f"https://api.telegram.org/bot{tok}/sendDocument"], capture_output=True, text=True)
            print("Enviado" if '"ok":true' in r.stdout else "ERROR: " + r.stdout[:200])


if __name__ == "__main__":
    main()
