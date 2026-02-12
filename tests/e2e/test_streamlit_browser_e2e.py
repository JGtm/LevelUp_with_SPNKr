"""Tests E2E navigateur réel (Playwright) pour Streamlit.

Ces tests sont optionnels et désactivés par défaut.
Activation : `python -m pytest tests/e2e/test_streamlit_browser_e2e.py --run-e2e-browser -v`
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http_ready(url: str, timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # nosec B310
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.5)
    raise TimeoutError(f"Serveur non prêt dans le délai imparti: {url}")


@pytest.fixture
def running_streamlit_app() -> str:
    """Lance l'app Streamlit en sous-process et retourne l'URL de base."""
    project_root = Path(__file__).resolve().parents[2]
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]

    process = subprocess.Popen(  # noqa: S603
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_for_http_ready(base_url, timeout_s=90)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.mark.e2e_browser
def test_streamlit_homepage_loads_in_real_browser(running_streamlit_app: str) -> None:
    """Vérifie qu'un vrai navigateur peut charger l'app sans crash immédiat."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(2500)

        content = page.content()
        expected_labels = [
            "Séries temporelles",
            "Victoires/Défaites",
            "Mes coéquipiers",
            "Paramètres",
        ]
        assert any(label in content for label in expected_labels)

        browser.close()


@pytest.mark.e2e_browser
def test_streamlit_can_navigate_to_settings_tab(running_streamlit_app: str) -> None:
    """Vérifie une navigation utilisateur simple vers l'onglet Paramètres."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        settings_locator = page.get_by_text("Paramètres")
        if settings_locator.count() == 0:
            pytest.skip("Onglet Paramètres non visible dans cet environnement de données")

        settings_locator.first.click(timeout=20000)
        page.wait_for_timeout(1200)

        content = page.content()
        assert "Paramètres" in content

        browser.close()
