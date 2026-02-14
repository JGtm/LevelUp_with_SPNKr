FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --- Étape 1 : Dépendances (cache Docker maximisé) ---
# On copie pyproject.toml + requirements.txt en premier pour ne pas
# réinstaller à chaque changement de code source.
COPY pyproject.toml requirements.txt /app/
# setup.py stub minimal pour que pip install -e fonctionne sans le code src/
RUN mkdir -p /app/src && touch /app/src/__init__.py

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e ".[spnkr]"

# --- Étape 2 : Code et assets ---
COPY src /app/src
COPY static /app/static
COPY scripts /app/scripts
COPY streamlit_app.py openspartan_launcher.py /app/

# Données de référence embarquées (petits fichiers nécessaires à l'UI)
COPY data/Playlist_modes_translations.json /app/data/
COPY data/wiki /app/data/wiki

# Fichiers de config par défaut (écrasés au runtime par les volumes)
# On utilise un RUN shell pour être robuste si un fichier manque au build.
COPY db_profiles.json /app/db_profiles.json
RUN if [ ! -f /app/app_settings.json ]; then echo '{}' > /app/app_settings.json; fi \
    && if [ ! -f /app/data/xuid_aliases.json ]; then echo '{}' > /app/data/xuid_aliases.json; fi

# Dossiers attendus par le runtime
RUN mkdir -p /app/data/players /app/data/warehouse

# --- Étape 3 : Utilisateur non-root ---
RUN adduser --disabled-password --gecos "" --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

# Variables d'environnement par défaut
# OPENSPARTAN_DB : optionnel, force un chemin DB précis
# OPENSPARTAN_ROOT : indique la racine du projet au runtime
ENV OPENSPARTAN_DB="" \
    OPENSPARTAN_ROOT=/app

# Healthcheck Streamlit (endpoint officiel /_stcore/health)
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health').read()"]

CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
