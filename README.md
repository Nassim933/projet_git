# 🎵 Bot Alerte NRJ → Telegram

Reçois un message Telegram dès qu'un titre de **Karol G** ou **Adele / Adéla** passe **en direct sur NRJ**.
100 % gratuit : le bot tourne sur **GitHub Actions**, sans serveur.

Exemple d'alerte :
```
🎵 KAROL G — Si Antes Te Hubiera Conocido
📻 en direct sur NRJ !
```

## Comment ça marche
- `bot.py` interroge l'API du lecteur web NRJ (`players.nrjaudio.fm`) **chaque minute** pour connaître le titre en cours.
- Chaque exécution GitHub surveille pendant 55 min puis **se relance elle-même** → surveillance 24h/24.
  (Le minuteur `cron` de GitHub n'est qu'un filet de sécurité : GitHub l'espace souvent à 1 lancement par heure ou moins.)
- Pour **arrêter** le bot : Actions → Alerte NRJ → « ··· » → **Disable workflow**.
- En secours, il lit le titre directement dans le flux audio NRJ (métadonnées ICY).
- Accents, majuscules et « feat. » sont gérés (`ADÈLE`, `Karol G & Shakira`… sont détectés).
- Un même titre n'est signalé qu'une fois par passage (mémoire dans le cache GitHub).

## Installation (5 minutes)

### 1. Récupère ton `chat_id` Telegram
1. Envoie n'importe quel message à ton bot sur Telegram.
2. Ouvre dans ton navigateur : `https://api.telegram.org/bot<TON_TOKEN>/getUpdates`
3. Repère `"chat":{"id": 123456789 ...}` → ce nombre est ton `chat_id`.

### 2. Ajoute les secrets dans GitHub
Dépôt → **Settings → Secrets and variables → Actions → New repository secret** :

| Nom | Valeur |
|---|---|
| `TELEGRAM_BOT_TOKEN` | le token donné par @BotFather |
| `TELEGRAM_CHAT_ID` | ton chat id |

⚠️ Ne mets **jamais** le token directement dans le code.

### 3. Teste
Onglet **Actions → Alerte NRJ → Run workflow**, coche **« Envoyer un message de test »** →
tu dois recevoir « ✅ Bot NRJ connecté ! ». Ensuite le bot tourne tout seul.

Pour vérifier qu'il lit bien NRJ : ouvre une exécution dans l'onglet **Actions**, le journal affiche
`en cours sur NRJ : <artiste> - <titre>` chaque minute.

## Changer les artistes (optionnel)
**Settings → Secrets and variables → Actions → onglet Variables → New variable** :
`ARTISTS` = `Karol G,Adele,Aya Nakamura` (séparés par des virgules).

## Gratuit ?
- **Dépôt public** : minutes GitHub Actions illimitées → **gratuit**, surveillance quasi continue.
  (Le token reste caché dans les secrets, personne ne peut le voir.)
- **Dépôt privé** : seulement 2 000 min/mois offertes, insuffisant pour une surveillance chaque minute.
  Supprime alors l'étape « Relancer la surveillance » et mets `LOOP_MINUTES` à `1` dans
  `.github/workflows/nrj-alert.yml` (beaucoup moins réactif, des passages seront ratés).

## Lancer en local
```bash
export TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy
python3 bot.py --test             # message de test
LOOP_MINUTES=600 python3 bot.py   # surveille NRJ en continu pendant 10 h
```
