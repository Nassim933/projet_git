# 🎵 Bot Alerte Énergie → Telegram

Reçois un message Telegram dès qu'un titre d'**Adele** ou de **Karol G** passe sur **Énergie**.
100 % gratuit : le bot tourne sur **GitHub Actions** (toutes les 5 minutes), sans serveur.

## Comment ça marche
- `bot.py` interroge l'API publique « now playing » de Triton Digital (le diffuseur des radios Énergie).
  Elle donne les ~10 derniers titres, donc même si GitHub retarde une exécution, aucun passage n'est raté.
- En secours, le bot lit le titre directement dans le flux audio (métadonnées ICY).
- Les titres déjà signalés sont mémorisés (`state.json` dans le cache GitHub) → pas de doublons.

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
Onglet **Actions → Alerte Énergie → Run workflow**, coche **« Envoyer un message de test »** → tu dois recevoir
« ✅ Bot Énergie connecté ! ». Ensuite le bot tourne tout seul toutes les 5 minutes.

## Personnaliser (optionnel)
Dans **Settings → Secrets and variables → Actions → onglet Variables** :

| Variable | Exemple | Rôle |
|---|---|---|
| `ARTISTS` | `Adele,Karol G,Charlotte Cardin` | artistes à surveiller (accents/majuscules ignorés, les « feat. » sont détectés) |
| `MOUNTS` | `CKMFFM` | station(s) Énergie à surveiller (code Triton, séparés par des virgules) |

Par défaut : `CKMFFM` = **Énergie 94.3 Montréal**. Pour une autre ville, trouve le code de la station
(il apparaît dans l'URL du flux `playerservices.streamtheworld.com/.../XXXXFM...` quand tu écoutes Énergie
dans le navigateur, onglet Réseau des outils développeur) et mets-le dans `MOUNTS`.

## Gratuit ?
- **Dépôt public** : minutes GitHub Actions illimitées → gratuit.
- **Dépôt privé** : 2 000 min/mois offertes ; une exécution toutes les 5 min en consomme ~8 600.
  Rends le dépôt public (le token reste caché dans les secrets) ou passe le cron à `*/30 * * * *`
  dans `.github/workflows/energie-alert.yml` (l'historique de 10 titres couvre ~30–40 min de radio).

## Lancer en local
```bash
export TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy
python3 bot.py --test          # message de test
LOOP_MINUTES=600 python3 bot.py  # surveille en continu pendant 10 h
```
