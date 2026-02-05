#!/usr/bin/env python3
"""
Script d'installation des dépendances avec gestion des problèmes SSL MSYS2.
"""

import importlib.util
import os
import platform
import subprocess
import sys

# Configurer l'encodage pour éviter les problèmes avec MSYS2
if sys.platform == "win32" or "MSYS" in platform.system():
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def run_command(cmd, check=True):
    """Exécute une commande et affiche la sortie."""
    print(f"\n{'='*60}")
    print(f"Exécution: {cmd}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, shell=True, check=check)
    return result.returncode == 0


def is_msys2():
    """Détecte si on est dans un environnement MSYS2."""
    return "MSYS" in platform.system() or "MINGW" in platform.system()


def install_msys2_dependencies():
    """Installe les dépendances système MSYS2 nécessaires."""
    print("\n[INFO] Installation des dependances systeme MSYS2...")
    print("Si vous n'avez pas pacman, installez manuellement:")
    print("  - cmake")
    print("  - ninja")
    print("  - gcc")
    print("  - python-pip")

    try:
        # Essayer d'installer via pacman
        run_command("pacman -S --needed --noconfirm cmake ninja gcc", check=False)
    except Exception as e:
        print(f"[WARN] Impossible d'installer via pacman: {e}")
        print("Installez manuellement les dependances systeme.")


def install_python_dependencies():
    """Installe les dépendances Python."""
    print("\n[INFO] Installation des dependances Python...")

    # Détecter l'environnement
    if is_msys2():
        print("[WARN] Environnement MSYS2 detecte.")
        print("   Pour eviter les problemes SSL, utilisez un Python Windows natif si possible.")
        print("   Sinon, installez d'abord cmake et ninja via pacman.")

        # Configurer les certificats SSL si possible
        cert_file = "/etc/ssl/certs/ca-certificates.crt"
        if os.path.exists(cert_file):
            os.environ["SSL_CERT_FILE"] = cert_file
            print(f"[OK] Certificats SSL configures: {cert_file}")
        else:
            print("[WARN] Fichier de certificats SSL non trouve.")

    # Installer pip si nécessaire
    if importlib.util.find_spec("pip") is None:
        print("[INFO] Installation de pip...")
        run_command(f"{sys.executable} -m ensurepip --upgrade", check=False)

    # Mettre à jour pip
    print("[INFO] Mise a jour de pip...")
    run_command(f"{sys.executable} -m pip install --upgrade pip", check=False)

    # Installer les dépendances
    print("\n[INFO] Installation des dependances depuis requirements.txt...")

    # Options pour MSYS2
    pip_options = []
    if is_msys2():
        pip_options.extend(
            [
                "--trusted-host",
                "pypi.org",
                "--trusted-host",
                "pypi.python.org",
                "--trusted-host",
                "files.pythonhosted.org",
            ]
        )

    cmd = [sys.executable, "-m", "pip", "install"] + pip_options + ["-r", "requirements.txt"]

    success = run_command(" ".join(cmd), check=False)

    if not success:
        print("\n[ERREUR] Echec de l'installation.")
        print("\n[INFO] Solutions alternatives:")
        print("1. Utilisez un Python Windows natif (recommandé)")
        print("2. Installez cmake et ninja via MSYS2:")
        print("   pacman -S cmake ninja")
        print("3. Utilisez des wheels pre-compilees:")
        print("   pip install --only-binary :all: -r requirements.txt")
        return False

    print("\n[OK] Installation terminee avec succes!")
    return True


def verify_installation():
    """Vérifie que les dépendances principales sont installées."""
    print("\n[INFO] Verification de l'installation...")

    required_modules = ["streamlit", "plotly", "pandas", "numpy", "duckdb", "polars", "pydantic"]

    missing = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"  [OK] {module}")
        except ImportError:
            print(f"  [MANQUANT] {module}")
            missing.append(module)

    if missing:
        print(f"\n[WARN] Modules manquants: {', '.join(missing)}")
        return False

    print("\n[OK] Toutes les dependances sont installees!")
    return True


def main():
    """Fonction principale."""
    print("=" * 60)
    print("Installation des dependances - LevelUp")
    print("=" * 60)

    # Changer vers le répertoire du projet
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    print(f"\n[INFO] Repertoire de travail: {project_dir}")

    # Vérifier que requirements.txt existe
    if not os.path.exists("requirements.txt"):
        print("[ERREUR] Fichier requirements.txt introuvable!")
        sys.exit(1)

    # Installation
    if is_msys2():
        install_msys2_dependencies()

    if not install_python_dependencies():
        sys.exit(1)

    # Vérification
    if not verify_installation():
        print("\n[WARN] Certaines dependances sont manquantes.")
        print("   Relancez ce script ou installez-les manuellement.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("[OK] Installation terminee avec succes!")
    print("=" * 60)
    print("\n[INFO] Prochaines etapes:")
    print("   1. Configurez .env.local (copiez .env.example)")
    print("   2. Ajoutez votre gamertag dans db_profiles.json")
    print("   3. Lancez: streamlit run streamlit_app.py")


if __name__ == "__main__":
    main()
