#!/usr/bin/env python3
"""
Bot d'alerte Telegram : prévient quand Adele ou Karol G passe sur Énergie.

Sources (dans l'ordre) :
  1. API publique "now playing" de Triton Digital (StreamTheWorld), qui diffuse
     les radios Énergie de Bell Media. Elle renvoie les ~10 derniers titres,
     donc aucun passage n'est manqué entre deux exécutions.
  2. Secours : métadonnées ICY (StreamTitle) lues dans le flux audio.

Uniquement la bibliothèque standard Python, aucune dépendance.

Variables d'environnement :
  TELEGRAM_BOT_TOKEN  (obligatoire)  token donné par @BotFather
  TELEGRAM_CHAT_ID    (obligatoire)  ton chat id
  ARTISTS             (optionnel)    ex. "Adele,Karol G"
  MOUNTS              (optionnel)    points de montage Triton, ex. "CKMFFM"
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
import xml.etree.ElementTree as ET

DEFAULT_ARTISTS = "Adele,Karol G"
# CKMF-FM = Énergie 94.3 Montréal. Ajoute d'autres stations séparées par des virgules.
DEFAULT_MOUNTS = "CKMFFM"
DEFAULT_STREAM = "https://playerservices.streamtheworld.com/api/livestream-redirect/{mount}.mp3"
TRITON_URL = "https://np.tritondigital.com/public/nowplaying"
UA = "energie-telegram-alert/1.0"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def norm(s):
    """minuscules, sans accents, sans ponctuation : 'Adèle' -> 'adele', 'KAROL-G' -> 'karol g'."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def matches(artist_field, wanted):
    """Vrai si un des artistes voulus apparaît comme mot(s) entier(s) (gère les feat.)."""
    hay = f" {norm(artist_field)} "
    return [w for w in wanted if f" {norm(w)} " in hay]


def http_get(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


# ---------- Source 1 : Triton now playing ----------
def fetch_triton(mount, n=10):
    q = urllib.parse.urlencode({"mountName": mount, "numberToFetch": n, "eventType": "track"})
    with http_get(f"{TRITON_URL}?{q}") as r:
        root = ET.fromstring(r.read())
    tracks = []
    for item in root.iter("nowplaying-info"):
        props = {p.get("name"): (p.text or "").strip() for p in item.iter("property")}
        artist = props.get("track_artist_name", "")
        title = props.get("cue_title", "")
        start = props.get("cue_time_start") or item.get("timestamp") or ""
        if artist or title:
            tracks.append({"artist": artist, "title": title, "start": start})
    return tracks


# ---------- Source 2 : métadonnées ICY du flux ----------
def fetch_icy(mount):
    url = os.environ.get("STREAM_URL") or DEFAULT_STREAM.format(mount=mount)
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
    # pas d'heure de début : on utilise un créneau de 10 min pour dédoublonner
    return [{"artist": artist.strip(), "title": title.strip(), "start": f"icy-{int(time.time() // 600)}"}]


def get_tracks(mount):
    try:
        t = fetch_triton(mount)
        if t:
            return t, "triton"
    except Exception as e:
        log(f"[{mount}] Triton indisponible : {e}")
    try:
        return fetch_icy(mount), "icy"
    except Exception as e:
        log(f"[{mount}] flux ICY indisponible : {e}")
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
        return {"seen": []}


def save_state(path, state):
    state["seen"] = state["seen"][-300:]
    with open(path, "w") as f:
        json.dump(state, f, indent=1)


def check_once(cfg, state):
    first_run = not state.get("initialized")
    for mount in cfg["mounts"]:
        tracks, source = get_tracks(mount)
        if tracks:
            log(f"[{mount}] ({source}) dernier titre : {tracks[0]['artist']} - {tracks[0]['title']}")
        for t in reversed(tracks):  # du plus ancien au plus récent
            hit = matches(t["artist"], cfg["artists"])
            if not hit:
                continue
            key = f"{mount}|{norm(t['artist'])}|{norm(t['title'])}|{t['start']}"
            if key in state["seen"]:
                continue
            state["seen"].append(key)
            # Au tout premier lancement on ne renvoie pas l'historique, sauf le titre en cours.
            if first_run and t is not tracks[0]:
                continue
            msg = f"🎵 Sur Énergie maintenant : {t['artist']} — {t['title']}"
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
        "mounts": [m.strip() for m in (os.environ.get("MOUNTS") or DEFAULT_MOUNTS).split(",") if m.strip()],
    }
    if "--test" in sys.argv:
        send_telegram(token, chat_id, "✅ Bot Énergie connecté ! Surveillance : " + ", ".join(cfg["artists"]))
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
