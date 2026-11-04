#!/usr/bin/env python3
"""
Bot d'alerte Telegram : prévient quand Karol G ou Adele/Adéla passe en direct sur NRJ.

Sources (dans l'ordre) :
  1. API du lecteur web NRJ (players.nrjaudio.fm) : titre en cours.
  2. Secours : métadonnées ICY (StreamTitle) lues dans le flux audio NRJ.

Uniquement la bibliothèque standard Python, aucune dépendance.

Variables d'environnement :
  TELEGRAM_BOT_TOKEN  (obligatoire)  token donné par @BotFather
  TELEGRAM_CHAT_ID    (obligatoire)  ton chat id
  ARTISTS             (optionnel)    ex. "Adele,Adela,Karol G"
  NRJ_ID              (optionnel)    id de la webradio NRJ (158 = NRJ France, le direct)
  STREAM_URL          (optionnel)    flux audio utilisé en secours
  STATE_FILE          (optionnel)    fichier mémorisant les titres déjà signalés
  LOOP_MINUTES        (optionnel)    si > 0, le script boucle pendant N minutes
  POLL_SECONDS        (optionnel)    intervalle entre deux vérifications (boucle)
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

DEFAULT_ARTISTS = "Adele,Adela,Karol G"
DEFAULT_NRJ_ID = "158"  # NRJ (le direct national)
NRJ_API = "https://players.nrjaudio.fm/wr_api/live/fr?act={act}&id_wr={id}&cp=utf8&fmt=json"
DEFAULT_STREAM = "https://streaming.nrjaudio.fm/oumvmk8fnozc"
REALERT_MINUTES = 20  # un même titre n'est re-signalé qu'après ce délai
UA = "Mozilla/5.0 (nrj-telegram-alert)"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def norm(s):
    """minuscules, sans accents, sans ponctuation : 'Adéla' -> 'adela', 'KAROL-G' -> 'karol g'."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def matches(artist_field, wanted):
    """Vrai si un des artistes voulus apparaît comme mot(s) entier(s) (gère les feat.)."""
    hay = f" {norm(artist_field)} "
    return [w for w in wanted if f" {norm(w)} " in hay]


def http_get(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


# ---------- Source 1 : API NRJ ----------
def fetch_nrj(station_id):
    tracks = []
    for act in ("get_cur", "get_plist"):
        with http_get(NRJ_API.format(act=act, id=station_id)) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        items = data.get("itms") or []
        if isinstance(items, dict):
            items = list(items.values())
        for it in items:
            artist, title = (it.get("art") or "").strip(), (it.get("tit") or "").strip()
            if artist or title:
                tracks.append({"artist": artist, "title": title})
        if tracks:
            break
    return tracks  # le plus récent en premier


# ---------- Source 2 : métadonnées ICY du flux ----------
def fetch_icy():
    url = os.environ.get("STREAM_URL") or DEFAULT_STREAM
    with http_get(url, timeout=20, headers={"Icy-MetaData": "1"}) as r:
        metaint = int(r.headers.get("icy-metaint") or 0)
        if not metaint:
            return []
        r.read(metaint)
        length = r.read(1)[0] * 16
        meta = r.read(length).decode("utf-8", "replace")
    m = re.search(r"StreamTitle='(.*?)';", meta)
    if not m or " - " not in m.group(1):
        return []
    artist, title = m.group(1).split(" - ", 1)
    return [{"artist": artist.strip(), "title": title.strip()}]


def get_tracks(station_id):
    try:
        t = fetch_nrj(station_id)
        if t:
            return t, "api-nrj"
    except Exception as e:
        log(f"API NRJ indisponible : {e}")
    try:
        return fetch_icy(), "icy"
    except Exception as e:
        log(f"flux ICY indisponible : {e}")
    return [], "aucune"


# ---------- Telegram ----------
def send_telegram(token, chat_id, text):
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data,
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        res = json.load(r)
    if not res.get("ok"):
        raise RuntimeError(res)


# ---------- État (anti-doublon) ----------
def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"seen": {}}


def save_state(path, state):
    cutoff = time.time() - 24 * 3600
    state["seen"] = {k: v for k, v in state.get("seen", {}).items() if v > cutoff}
    with open(path, "w") as f:
        json.dump(state, f, indent=1)


def check_once(cfg, state):
    now = time.time()
    seen = state.setdefault("seen", {})
    if not isinstance(seen, dict):
        seen = state["seen"] = {}
    tracks, source = get_tracks(cfg["station"])
    if not tracks:
        log("Aucun titre récupéré.")
        return
    log(f"({source}) en cours sur NRJ : {tracks[0]['artist']} - {tracks[0]['title']}")
    first_run = not state.get("initialized")
    # Titre en cours (+ le précédent si l'API le fournit, au cas où on l'aurait raté).
    for i, t in enumerate(tracks[:2]):
        if not matches(t["artist"], cfg["artists"]):
            continue
        key = f"{norm(t['artist'])}|{norm(t['title'])}"
        if now - seen.get(key, 0) < REALERT_MINUTES * 60:
            continue
        seen[key] = now
        if first_run and i > 0:
            continue
        label = "en direct sur NRJ" if i == 0 else "vient de passer sur NRJ"
        msg = f"🎵 {t['artist']} — {t['title']}\n📻 {label} !"
        log("ALERTE :", msg)
        send_telegram(cfg["token"], cfg["chat_id"], msg)
    state["initialized"] = True


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        sys.exit("TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID sont obligatoires.")
    cfg = {
        "token": token,
        "chat_id": chat_id,
        "artists": [a.strip() for a in (os.environ.get("ARTISTS") or DEFAULT_ARTISTS).split(",") if a.strip()],
        "station": (os.environ.get("NRJ_ID") or DEFAULT_NRJ_ID).strip(),
    }
    if "--test" in sys.argv:
        send_telegram(token, chat_id, "✅ Bot NRJ connecté ! Surveillance : " + ", ".join(cfg["artists"]))
        log("Message de test envoyé.")
        return

    state_file = os.environ.get("STATE_FILE", "state.json")
    loop_min = float(os.environ.get("LOOP_MINUTES") or 0)
    poll = float(os.environ.get("POLL_SECONDS") or 60)
    state = load_state(state_file)
    deadline = time.time() + loop_min * 60
    while True:
        try:
            check_once(cfg, state)
        except Exception as e:
            log("Erreur :", e)
        save_state(state_file, state)
        if time.time() + poll > deadline:
            break
        time.sleep(poll)


if __name__ == "__main__":
    main()
