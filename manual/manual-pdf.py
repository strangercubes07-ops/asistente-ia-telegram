#!/usr/bin/env python3
"""Convierte MANUAL.md en ~/claude-telegram/Manual del bot.pdf (con Chrome, sin tokens).
Uso: python3 manual-pdf.py [enviar]   -> con "enviar" también lo manda por Telegram."""
import html, os, re, subprocess, sys, tempfile

BASE = os.path.expanduser("~/claude-telegram")
PDF = os.path.join(BASE, "Manual del bot.pdf")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # tu chat de Telegram
COLORES = ["#5b5bd6", "#e5484d", "#30a46c", "#12a594", "#f76b15", "#8e4ec6", "#0090ff", "#d6409f"]


def fmt(t):
    t = html.escape(t)
    t = re.sub(r"&quot;(.+?)&quot;", r"<q>\1</q>", t)
    return t


def seccion(texto, i):
    lineas = texto.strip().split("\n")
    titulo, cuerpo = lineas[0], lineas[1:]
    out, lista = [], False
    for l in cuerpo:
        s = l.strip()
        if not s:
            continue
        if s.startswith("→"):
            out.append(f'<div class="ej">{fmt(s[1:].strip())}</div>')
        elif s.startswith("•"):
            out.append(f'<div class="item">{fmt(s[1:].strip())}</div>')
        elif s.startswith("- "):
            out.append(f'<div class="sub">{fmt(s[2:])}</div>')
        elif s.startswith("⚠️"):
            out.append(f'<div class="aviso">{fmt(s)}</div>')
        else:
            out.append(f'<div class="nota">{fmt(s)}</div>')
    c = COLORES[i % len(COLORES)]
    return f'<section style="--c:{c}"><h2>{fmt(titulo)}</h2>{"".join(out)}</section>'


def main():
    partes = [p for p in open(os.path.join(BASE, "MANUAL.md"), encoding="utf-8").read().split("=====") if p.strip()]
    intro = partes[0].strip().split("\n")
    portada = f'''<header><div class="logo">🤖</div><h1>Manual del bot</h1>
      <p class="sub1">@TuBot · todo lo que puedo hacer por ti</p>
      {"".join(f"<p>{fmt(l)}</p>" for l in intro[1:] if l.strip())}</header>'''
    cuerpo = "".join(seccion(p, i) for i, p in enumerate(partes[1:]))
    doc = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
@page {{ size: Letter; margin: 14mm 14mm 16mm; }}
* {{ box-sizing: border-box; }}
body {{ font: 11.5pt -apple-system, "Helvetica Neue", sans-serif; color:#1c2024; margin:0; }}
header {{ background: linear-gradient(135deg,#5b5bd6,#8e4ec6); color:#fff; border-radius:16px; padding:22px 26px; margin-bottom:16px; }}
header h1 {{ margin:4px 0 2px; font-size:26pt; }}
header .logo {{ font-size:30pt; }}
header .sub1 {{ opacity:.9; font-weight:600; margin:0 0 10px; }}
header p {{ margin:4px 0; }}
section {{ border:1.5px solid color-mix(in srgb, var(--c) 30%, white); border-left:6px solid var(--c);
  border-radius:12px; padding:12px 16px 10px; margin:0 0 12px; break-inside: avoid; }}
h2 {{ margin:0 0 8px; font-size:15pt; color: var(--c); }}
.item {{ font-weight:600; margin:9px 0 3px; }}
.item:first-of-type {{ margin-top:0; }}
.ej {{ margin:2px 0 2px 14px; color:#3b4046; font-size:10.5pt; }}
.ej::before {{ content:"💬 "; }}
.sub {{ margin:2px 0 2px 14px; font-size:10.5pt; }}
.sub::before {{ content:"– "; color: var(--c); }}
.nota {{ margin:2px 0 2px 14px; font-size:10.5pt; color:#3b4046; }}
.aviso {{ margin:4px 0 2px 14px; font-size:10.5pt; background:#fff4d6; border-radius:6px; padding:3px 8px; display:inline-block; }}
q {{ quotes: "“" "”"; font-style: italic; }}
footer {{ text-align:center; color:#80838d; font-size:9pt; margin-top:6px; }}
</style></head><body>{portada}{cuerpo}<footer>Pídele al bot “mándame el manual” para recibir la versión más nueva.</footer></body></html>'''
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        tmp = f.name
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={PDF}", "file://" + tmp], check=True, capture_output=True, timeout=90)
    os.remove(tmp)
    print("PDF listo:", PDF)
    if len(sys.argv) > 1 and sys.argv[1] == "enviar":
        tok = next(l.split("=", 1)[1].strip().strip('"') for l in open(ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
        r = subprocess.run(["curl", "-s", "-F", f"chat_id={CHAT_ID}", "-F", f"document=@{PDF}",
                            "-F", "caption=📖 Manual del bot: todas mis funciones, separadas por uso.",
                            f"https://api.telegram.org/bot{tok}/sendDocument"], capture_output=True, text=True)
        print("Enviado" if '"ok":true' in r.stdout else "ERROR al enviar: " + r.stdout[:200])


if __name__ == "__main__":
    main()
