"""Gestion des styles CSS."""

import os


def get_css_path() -> str:
    """Retourne le chemin du fichier CSS."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "static",
        "styles.css",
    )


def load_css() -> str:
    """Charge le contenu du fichier CSS.
    
    Returns:
        Contenu CSS avec balises <style>.
    """
    css_path = get_css_path()
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        return f"<style>\n{css_content}\n</style>"
    except FileNotFoundError:
        # Fallback: CSS minimal si le fichier n'existe pas
        return """
        <style>
            .hero { padding: 18px; margin-bottom: 14px; }
            .hero .title { font-size: 28px; font-weight: 700; }
            .hero .subtitle { color: #aaa; font-size: 14px; }
        </style>
        """


def get_hero_html() -> str:
    """Retourne le HTML du banner hero."""
    return """
    <div class="wp-notch-top"></div>
    <div class="wp-notch-bottom"></div>
    <div class="hero">
        <div class="title">OpenSpartan Graphs</div>
        <div class="subtitle">Analyse tes parties Halo Infinite depuis la DB OpenSpartan Workshop — filtres, séries temporelles, amis, maps.</div>
    </div>
    """


def get_notches_html() -> str:
    """Retourne le HTML des découpes haut/bas."""
    return """
    <div class="wp-notch-top"></div>
    <div class="wp-notch-bottom"></div>
    """
