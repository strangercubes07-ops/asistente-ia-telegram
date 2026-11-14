#!/usr/bin/env python3
"""Spotify Connect desde el bot (API oficial, requiere Premium).

Uso: ~/claude-telegram/spotify-connect.sh COMANDO
  auth CLIENT_ID            -> autorizar una sola vez (abre el navegador)
  dispositivos              -> lista Echo, celular, compu... donde puede sonar
  a "Nombre"                -> pasa lo que está sonando a ese dispositivo (ej. "Echo")
  playlist "nombre" ["Dispositivo"] -> busca en TUS playlists y la pone (opcional en un dispositivo)
  buscar "texto" ["Dispositivo"]    -> busca canción/playlist en Spotify y la pone
  play | pausa | siguiente | anterior | que-suena | volumen N
"""
import base64, hashlib, http.server, json, os, secrets, sys, threading, time, unicodedata
import urllib.parse, urllib.request, webbrowser

BASE = os.path.expanduser("~/claude-telegram")
CRED = os.path.join(BASE, ".spotify-token.json")
REDIRECT = "http://127.0.0.1:8888/callback"
SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative"


def norm(s):
    s = unicodedata.normalize("NFD", s or "").lower()
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def guardar(d):
    with open(CRED, "w") as f:
        json.dump(d, f)
    os.chmod(CRED, 0o600)


def post_token(data):
    req = urllib.request.Request("https://accounts.spotify.com/api/token",
                                 data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.load(urllib.request.urlopen(req, timeout=20))


def auth(client_id):
    verifier = secrets.token_urlsafe(64)[:100]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": REDIRECT,
        "code_challenge_method": "S256", "code_challenge": challenge, "scope": SCOPES, "state": state})
    res = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state:
                res["code"] = q.get("code", [None])[0]
                res["error"] = q.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "Listo, ya puedes cerrar esta pestaña y volver al chat." if res.get("code") else "No se autorizó."
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 8888), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("Abriendo el navegador para autorizar…")
    webbrowser.open(url)
    for _ in range(300):
        if res:
            break
        time.sleep(1)
    srv.shutdown()
    if not res.get("code"):
        sys.exit(f"No se autorizó ({res.get('error') or 'tiempo agotado'})")
    tok = post_token({"grant_type": "authorization_code", "code": res["code"], "redirect_uri": REDIRECT,
                      "client_id": client_id, "code_verifier": verifier})
    guardar({"client_id": client_id, "refresh_token": tok["refresh_token"],
             "access_token": tok["access_token"], "expires": time.time() + tok["expires_in"] - 60})
    print("✅ Spotify autorizado")


def token():
    if not os.path.exists(CRED):
        sys.exit("Falta autorizar: spotify-connect.sh auth CLIENT_ID")
    d = json.load(open(CRED))
    if time.time() < d.get("expires", 0):
        return d["access_token"]
    t = post_token({"grant_type": "refresh_token", "refresh_token": d["refresh_token"], "client_id": d["client_id"]})
    d["access_token"] = t["access_token"]
    d["expires"] = time.time() + t["expires_in"] - 60
    if t.get("refresh_token"):
        d["refresh_token"] = t["refresh_token"]
    guardar(d)
    return d["access_token"]


def api(method, path, body=None, params=None):
    url = "https://api.spotify.com/v1" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=20)
        txt = r.read()
        return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="ignore")[:300]
        if e.code == 404 and "device" in msg.lower():
            sys.exit("No encontré un dispositivo activo. Abre Spotify en algún lado o di en cuál ponerlo.")
        if e.code == 403:
            sys.exit("Spotify no dejó hacer eso (¿Premium activo?): " + msg)
        sys.exit(f"Error de Spotify {e.code}: {msg}")


def dispositivos():
    return api("GET", "/me/player/devices").get("devices", [])


def buscar_disp(nombre):
    ds = dispositivos()
    n = norm(nombre)
    alias = {"alexa": "echo", "bocina del cuarto": "echo", "compu": "macbook", "mac": "macbook", "cel": "iphone"}
    n2 = alias.get(n, n)
    for cand in (n, n2):
        for d in ds:
            if norm(d["name"]) == cand:
                return d
        for d in ds:
            if cand in norm(d["name"]) or cand in norm(d["type"]):
                return d
    lista = ", ".join(d["name"] for d in ds) or "ninguno"
    sys.exit(f"No encontré \"{nombre}\". Dispositivos disponibles: {lista}. (El Echo debe estar prendido y con Spotify vinculado en la app Alexa.)")


def que_suena():
    p = api("GET", "/me/player")
    if not p or not p.get("item"):
        return "No está sonando nada"
    it = p["item"]
    artistas = ", ".join(a["name"] for a in it.get("artists", []))
    estado = "▶️" if p.get("is_playing") else "⏸"
    return f"{estado} {it['name']} — {artistas} (en {p['device']['name']})"


def poner(uri, disp=None):
    params = {"device_id": disp["id"]} if disp else None
    body = {"uris": [uri]} if ":track:" in uri else {"context_uri": uri}
    api("PUT", "/me/player/play", body, params)
    time.sleep(1.5)
    print(que_suena())


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd, resto = a[0], a[1:]
    if cmd == "auth":
        auth(resto[0])
    elif cmd == "dispositivos":
        for d in dispositivos():
            print(f"- {d['name']} ({d['type']}){' ← activo' if d['is_active'] else ''}")
    elif cmd == "a":
        d = buscar_disp(" ".join(resto))
        api("PUT", "/me/player", {"device_ids": [d["id"]], "play": True})
        time.sleep(1.5)
        print(f"🔊 Ahora en {d['name']}. " + que_suena())
    elif cmd == "playlist":
        q = norm(resto[0])
        disp = buscar_disp(resto[1]) if len(resto) > 1 else None
        encontrada, off = None, 0
        while not encontrada:
            r = api("GET", "/me/playlists", params={"limit": 50, "offset": off})
            items = [p for p in r.get("items", []) if p]
            encontrada = next((p for p in items if norm(p["name"]) == q), None) or \
                         next((p for p in items if q in norm(p["name"])), None)
            if not r.get("next"):
                break
            off += 50
        if not encontrada:
            sys.exit(f"NO_ENCONTRADA: no tienes una playlist llamada \"{resto[0]}\". Usa buscar para buscarla en Spotify.")
        poner(encontrada["uri"], disp)
    elif cmd == "buscar":
        disp = buscar_disp(resto[1]) if len(resto) > 1 else None
        r = api("GET", "/search", params={"q": resto[0], "type": "track,playlist", "limit": 5})
        pls = [p for p in r.get("playlists", {}).get("items", []) if p]
        trs = r.get("tracks", {}).get("items", [])
        q = norm(resto[0])
        pl = next((p for p in pls if q in norm(p["name"])), None)
        uri = pl["uri"] if pl else (trs[0]["uri"] if trs else (pls[0]["uri"] if pls else None))
        if not uri:
            sys.exit("No encontré nada con eso.")
        poner(uri, disp)
    elif cmd == "play":
        api("PUT", "/me/player/play"); print(que_suena())
    elif cmd == "pausa":
        api("PUT", "/me/player/pause"); print("⏸ Pausa")
    elif cmd == "siguiente":
        api("POST", "/me/player/next"); time.sleep(1); print(que_suena())
    elif cmd == "anterior":
        api("POST", "/me/player/previous"); time.sleep(1); print(que_suena())
    elif cmd == "volumen":
        api("PUT", "/me/player/volume", params={"volume_percent": int(resto[0])}); print(f"🔊 Volumen {resto[0]}")
    elif cmd == "que-suena":
        print(que_suena())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
