# Guide d'installation du Watcher Thumbnails

Ce guide explique comment configurer le service de génération automatique de thumbnails GIF pour les vidéos de gameplay Halo Infinite.

## Prérequis

- **FFmpeg** installé et accessible dans le PATH
- **Python 3.10+** avec les dépendances du projet
- Dossier vidéos accessible (local ou montage réseau)

## Installation des dépendances

```bash
# Installer watchdog pour la surveillance temps réel
pip install watchdog
```

## Modes d'utilisation

### Mode 1 : Exécution manuelle (ponctuel)

```bash
# Scanner et générer les thumbnails manquants
python scripts/generate_thumbnails.py --videos-dir /chemin/vers/videos

# Forcer la régénération de tous les thumbnails
python scripts/generate_thumbnails.py --videos-dir /chemin/vers/videos --force
```

### Mode 2 : Mode watch avec polling (simple)

```bash
# Surveille le dossier toutes les 30 secondes
python scripts/generate_thumbnails.py --videos-dir /chemin/vers/videos --watch

# Intervalle personnalisé (60 secondes)
python scripts/generate_thumbnails.py --videos-dir /chemin/vers/videos --watch --interval 60
```

### Mode 3 : Mode daemon avec watchdog (temps réel)

```bash
# Surveillance temps réel avec inotify/watchdog
python scripts/generate_thumbnails.py --videos-dir /chemin/vers/videos --daemon
```

## Installation sur Synology NAS

### Option A : Via Task Scheduler (simple)

1. Ouvrir **Control Panel** → **Task Scheduler**
2. Créer une **Triggered Task** → **User-defined script**
3. Configuration :
   - **Event** : Boot-up
   - **User** : votre utilisateur
   - **Command** :

```bash
/usr/local/bin/python3 /volume1/docker/levelup/scripts/generate_thumbnails.py \
    --videos-dir /volume1/video/Xbox \
    --daemon
```

4. Cocher "Send run details by email" pour le debug

### Option B : Via systemd (recommandé)

1. Créer le fichier de service :

```bash
sudo nano /etc/systemd/system/thumbnails-watcher.service
```

2. Contenu du fichier :

```ini
[Unit]
Description=LevelUp Thumbnails Watcher
After=network.target

[Service]
Type=simple
User=votre_user
Group=users
WorkingDirectory=/volume1/docker/levelup
ExecStart=/usr/local/bin/python3 scripts/generate_thumbnails.py --videos-dir /volume1/video/Xbox --daemon
Restart=always
RestartSec=10

# Logs
StandardOutput=append:/var/log/thumbnails-watcher.log
StandardError=append:/var/log/thumbnails-watcher.log

[Install]
WantedBy=multi-user.target
```

3. Activer et démarrer le service :

```bash
sudo systemctl daemon-reload
sudo systemctl enable thumbnails-watcher
sudo systemctl start thumbnails-watcher

# Vérifier le statut
sudo systemctl status thumbnails-watcher

# Voir les logs
tail -f /var/log/thumbnails-watcher.log
```

### Option C : Via Docker (portable)

1. Utiliser le fichier `docker-compose.thumbnails.yml` :

```yaml
version: '3.8'

services:
  thumbnails-watcher:
    build: .
    container_name: levelup-thumbnails
    restart: unless-stopped
    volumes:
      - /volume1/video/Xbox:/videos:ro
      - /volume1/video/Xbox/thumbs:/videos/thumbs:rw
    command: python scripts/generate_thumbnails.py --videos-dir /videos --daemon
    environment:
      - TZ=Europe/Paris
```

2. Lancer :

```bash
docker-compose -f docker-compose.thumbnails.yml up -d
```

## Configuration

### Variables d'environnement (optionnel)

```bash
# Dossier vidéos par défaut
export LEVELUP_VIDEOS_DIR=/volume1/video/Xbox

# Largeur des GIFs (défaut: 320)
export LEVELUP_GIF_WIDTH=320

# Durée des GIFs en secondes (défaut: 4)
export LEVELUP_GIF_DURATION=4

# FPS des GIFs (défaut: 10)
export LEVELUP_GIF_FPS=10
```

### Via app_settings.json

Le script lit aussi `app_settings.json` s'il existe :

```json
{
  "media_videos_dir": "/volume1/video/Xbox"
}
```

## Structure des fichiers

```
/volume1/video/Xbox/
├── Clip1.mp4
├── Clip2.mp4
├── Match_2024-01-15.mp4
└── thumbs/                    # Créé automatiquement
    ├── Clip1_abc123def456.gif
    ├── Clip2_789xyz012abc.gif
    └── Match_2024-01-15_def456abc789.gif
```

## Dépannage

### FFmpeg introuvable

```bash
# Synology - installer via Entware
opkg install ffmpeg

# Ou télécharger le binaire statique
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar xf ffmpeg-release-amd64-static.tar.xz
sudo cp ffmpeg-*-static/ffmpeg /usr/local/bin/
```

### Permissions

```bash
# S'assurer que l'utilisateur a les droits
chmod 755 /volume1/video/Xbox/thumbs
chown -R votre_user:users /volume1/video/Xbox/thumbs
```

### Watchdog ne détecte pas les fichiers réseau

Sur les montages NFS/SMB, inotify ne fonctionne pas. Utiliser le mode polling :

```bash
python scripts/generate_thumbnails.py --videos-dir /mnt/share --watch --interval 30
```

## Logs

Le daemon affiche les logs sur stdout. Pour les capturer :

```bash
# Rediriger vers un fichier
python scripts/generate_thumbnails.py --daemon 2>&1 | tee /var/log/thumbs.log

# Avec rotation
python scripts/generate_thumbnails.py --daemon 2>&1 | rotatelogs /var/log/thumbs.%Y%m%d.log 86400
```

## Performance

- Un GIF de 4 secondes (320px) prend ~5-10 secondes à générer
- Le watcher traite un fichier à la fois (pas de surcharge CPU)
- Sur Synology DS920+, ~500 thumbnails/heure possibles
