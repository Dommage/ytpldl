# Téléchargeur de playlist YouTube (yt-dlp)

Application CLI pour Ubuntu (via SSH) permettant de télécharger l'ensemble d'une playlist YouTube avec `yt-dlp`, avec reprise automatique, gestion des cookies et journalisation locale.

## Arborescence du projet
```
.
├── config/
│   └── config.json (généré automatiquement)
├── logs/
│   └── app.log
│   └── download_archive.txt (créé automatiquement pour éviter les doublons)
├── yt_playlist_downloader/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── downloader.py
│   └── logger.py
├── main.py
└── requirements.txt
```

## Installation sur Ubuntu (via SSH)
```bash
# 1) Mettre à jour le système et Python 3
sudo apt update && sudo apt install -y python3 python3-venv python3-pip

# 2) Créer et activer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# 3) Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# (Optionnel mais recommandé) Installer un runtime JavaScript (ex. Node.js) pour résoudre les challenges YouTube (EJS) si yt-dlp l'exige.
```

## Lancement de l'application
```bash
source .venv/bin/activate
python main.py
```

## Menu CLI
```
=== Téléchargeur de playlist YouTube ===
1) Lancer le téléchargement
2) Configuration
3) Quitter
```

### Option 1 : Lancer le téléchargement
L'application vous demande :
1. **URL de la playlist**
2. **Utilisation d'un fichier cookies.txt** (chemin optionnel)
3. **Nombre des dernières vidéos à télécharger** (`0` = télécharger toute la playlist). Les vidéos sont téléchargées en commençant par les plus récentes.
4. **Qualité maximale** (hauteur en pixels, `0` = meilleure disponible)
5. **Dossier de téléchargement** (créé automatiquement si absent)

La progression, l'estimation du temps restant et les erreurs sont affichées dans le terminal. Les logs détaillés sont dans `logs/app.log`.
Les vidéos déjà référencées dans `logs/download_archive.txt` sont automatiquement ignorées afin de ne pas retélécharger ce qui existe déjà. Supprimez ce fichier si vous souhaitez forcer un nouveau téléchargement complet.

### Option 2 : Configuration
- Définit le dossier de téléchargement par défaut
- Définit le chemin du `cookies.txt` (YouTube)
- Définit la **qualité maximale** désirée (hauteur en pixels)

Les valeurs sont sauvegardées dans `config/config.json`.

## Résilience et reprise
- `yt-dlp` est configuré avec des reprises automatiques (`continuedl`), plusieurs tentatives (`retries`, `fragment_retries`) et un délai d'attente (`socket_timeout`).
- Les fragments déjà téléchargés ne sont pas perdus.
- Les erreurs sont journalisées avec date/heure dans `logs/app.log`.
- Les vidéos déjà téléchargées sont suivies dans `logs/download_archive.txt` pour éviter les doublons.
- Les erreurs de challenge YouTube (EJS) sont signalées clairement ; installez un runtime JavaScript (ex. Node.js) et le solveur EJS pour les résoudre.

## Exemple d'exécution
```
=== Téléchargeur de playlist YouTube ===
1) Lancer le téléchargement
2) Configuration
3) Quitter
Choix: 1

--- Lancer le téléchargement ---
URL de la playlist YouTube: https://www.youtube.com/playlist?list=XXXXXXXXX
Utiliser un fichier cookies.txt? (o/N) [N]: o
Chemin vers cookies.txt (YouTube): /home/user/cookies.txt
Nombre des dernières vidéos à télécharger (0 = toute la playlist) [0]: 5
Qualité maximale désirée (hauteur en pixels, 0 pour la meilleure disponible) [1080]: 720
Dossier de téléchargement [downloads]: /srv/videos
[DOWNLOADING] Titre de la vidéo ... | 12.3% at 1.5MiB/s | ETA 1m23s
...
Completed: 001-Video-title.mp4
All downloads attempted. Review logs for details.
```

Interruption forcée : `Ctrl+C` arrête proprement l'application, ferme le menu et journalise l'événement.

## Mise à jour automatique de yt-dlp
Ajoutez une tâche cron pour mettre à jour `yt-dlp` chaque nuit :
```bash
# Ouvrir la crontab
crontab -e
# Ajouter la ligne suivante (mise à jour à 3h du matin)
0 3 * * * /bin/bash -c 'cd /chemin/vers/le/projet && source .venv/bin/activate && pip install --upgrade yt-dlp >> logs/app.log 2>&1'
```

## Notes
- Assurez-vous que `cookies.txt` est exporté depuis un navigateur connecté à votre compte YouTube si la playlist est privée.
- Le dossier de téléchargement est créé automatiquement si nécessaire.
- La commande doit être lancée dans un terminal SSH (pas d'interface graphique requise).
