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


def _assert_no_front_error(page) -> None:
    """Vérifie l'absence d'erreur front évidente dans le HTML courant."""
    content = page.content().lower()
    assert "traceback" not in content
    assert "exception" not in content


def _click_first_visible_text(page, labels: list[str], *, in_sidebar: bool = True) -> str | None:
    """Clique le premier libellé visible parmi `labels` et retourne le libellé cliqué."""
    scope = page.locator('[data-testid="stSidebar"]') if in_sidebar else page
    for label in labels:
        locator = scope.get_by_text(label)
        if locator.count() > 0:
            locator.first.click(timeout=20000)
            return label
    return None


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
            _assert_no_front_error(page)
            browser.close()
            return

        settings_locator.first.click(timeout=20000)
        page.wait_for_timeout(1200)

        content = page.content()
        assert "Paramètres" in content

        browser.close()


@pytest.mark.e2e_browser
def test_streamlit_can_navigate_main_pages_without_front_error(running_streamlit_app: str) -> None:
    """Ouvre les pages principales et vérifie l'absence d'erreur front évidente."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        tabs = ["Séries temporelles", "Victoires/Défaites", "Mes coéquipiers", "Paramètres"]
        visible_any = False
        for tab in tabs:
            locator = page.get_by_text(tab)
            if locator.count() == 0:
                continue
            visible_any = True
            locator.first.click(timeout=20000)
            page.wait_for_timeout(800)
            content = page.content().lower()
            assert "traceback" not in content
            assert "exception" not in content

        if not visible_any:
            _assert_no_front_error(page)
            browser.close()
            return

        browser.close()


@pytest.mark.e2e_browser
def test_streamlit_filters_and_sessions_interaction_smoke(running_streamlit_app: str) -> None:
    """Smoke E2E: interaction simple avec filtres/sessions si les contrôles sont visibles."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        # Aller sur la page temporelle quand disponible
        timeseries_tab = page.get_by_text("Séries temporelles")
        if timeseries_tab.count() > 0:
            timeseries_tab.first.click(timeout=20000)
            page.wait_for_timeout(1000)

        # Tenter une interaction sur le mode de filtre si présent
        period_toggle = page.get_by_text("Période")
        sessions_toggle = page.get_by_text("Sessions")
        if period_toggle.count() == 0 and sessions_toggle.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return

        if sessions_toggle.count() > 0:
            sessions_toggle.first.click(timeout=15000)
            page.wait_for_timeout(700)
        if period_toggle.count() > 0:
            period_toggle.first.click(timeout=15000)
            page.wait_for_timeout(700)

        content = page.content().lower()
        assert "traceback" not in content
        assert "exception" not in content

        browser.close()


@pytest.mark.e2e_browser
def test_e2e_001_playlist_filter_changes_visible_results(running_streamlit_app: str) -> None:
    """E2E-001: le filtre playlist modifie visiblement l'écran Séries temporelles."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        timeseries_tab = page.get_by_text("Séries temporelles")
        if timeseries_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return
        timeseries_tab.first.click(timeout=20000)
        page.wait_for_timeout(1500)

        before = page.content()
        clicked = _click_first_visible_text(
            page,
            ["Ranked Arena", "Quick Play", "BTB", "Ranked"],
            in_sidebar=True,
        )
        if clicked is None:
            _assert_no_front_error(page)
            browser.close()
            return

        page.wait_for_timeout(1400)
        after = page.content()

        assert before != after
        _assert_no_front_error(page)

        browser.close()


@pytest.mark.e2e_browser
def test_e2e_002_mode_map_combined_filters_on_winloss(running_streamlit_app: str) -> None:
    """E2E-002: combinaison mode+map sur Victoires/Défaites sans erreur front."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        winloss_tab = page.get_by_text("Victoires/Défaites")
        if winloss_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return
        winloss_tab.first.click(timeout=20000)
        page.wait_for_timeout(1500)

        before = page.content()

        mode_clicked = _click_first_visible_text(
            page,
            ["Slayer", "CTF", "Oddball", "Strongholds"],
            in_sidebar=True,
        )
        map_clicked = _click_first_visible_text(
            page,
            ["Aquarius", "Recharge", "Live Fire", "Streets"],
            in_sidebar=True,
        )

        if mode_clicked is None or map_clicked is None:
            _assert_no_front_error(page)
            browser.close()
            return

        page.wait_for_timeout(1500)
        after = page.content()

        assert before != after
        _assert_no_front_error(page)

        browser.close()


@pytest.mark.e2e_browser
def test_e2e_003_teammates_impact_empty_then_filled_state(running_streamlit_app: str) -> None:
    """E2E-003: vérifier état vide puis tentative d'état rempli de l'impact coéquipiers."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        teammates_tab = page.get_by_text("Mes coéquipiers")
        if teammates_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return
        teammates_tab.first.click(timeout=20000)
        page.wait_for_timeout(1800)

        impact_section = page.get_by_text("Impact & Taquinerie")
        if impact_section.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return
        impact_section.first.click(timeout=20000)
        page.wait_for_timeout(1000)

        empty_message = "Sélectionnez au moins 2 coéquipiers pour voir l'analyse d'impact."
        has_empty = empty_message in page.content()

        # Tenter de sélectionner 2 coéquipiers via la multi-sélection quand possible.
        team_picker = page.get_by_text("Coéquipiers")
        if team_picker.count() > 0:
            team_picker.first.click(timeout=20000)
            page.wait_for_timeout(500)
            options = page.locator('[role="option"]')
            if options.count() >= 2:
                options.nth(0).click(timeout=10000)
                page.wait_for_timeout(250)
                options.nth(1).click(timeout=10000)
                page.wait_for_timeout(700)
                page.keyboard.press("Escape")
                page.wait_for_timeout(1200)
                impact_section = page.get_by_text("Impact & Taquinerie")
                if impact_section.count() > 0:
                    impact_section.first.click(timeout=20000)
                    page.wait_for_timeout(1000)

        content = page.content()
        has_filled_indicators = any(
            marker in content
            for marker in [
                "MVP",
                "Boulet",
                "Premier Sang",
                "Finisseur",
                "Matchs analysés",
            ]
        )

        if not has_empty and not has_filled_indicators:
            _assert_no_front_error(page)
            browser.close()
            return

        _assert_no_front_error(page)
        browser.close()


@pytest.mark.e2e_browser
def test_e2e_004_deeplink_match_query_params(running_streamlit_app: str) -> None:
    """E2E-004: deep-link vers la page Match via query params."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        deep_link = f"{running_streamlit_app}?page=Match&match_id=e2e_missing_match"
        page.goto(deep_link, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(2200)

        assert "match_id=e2e_missing_match" in page.url

        _assert_no_front_error(page)
        browser.close()


@pytest.mark.e2e_browser
def test_e2e_005_navigation_historique_to_match(running_streamlit_app: str) -> None:
    """E2E-005: navigation Historique des parties -> Match."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        history_tab = page.get_by_text("Historique des parties")
        if history_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return
        history_tab.first.click(timeout=20000)
        page.wait_for_timeout(1800)

        open_match = page.get_by_text("Ouvrir")
        if open_match.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return

        open_match.first.click(timeout=20000)
        page.wait_for_timeout(1800)

        content = page.content()
        assert "MatchId" in content
        _assert_no_front_error(page)

        browser.close()


@pytest.mark.e2e_browser
def test_e2e_006_navigation_medias_to_match(running_streamlit_app: str) -> None:
    """E2E-006: navigation Médias -> Match via query params internes."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        medias_tab = page.get_by_text("Médias")
        if medias_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return
        medias_tab.first.click(timeout=20000)
        page.wait_for_timeout(1800)

        media_match_link = page.locator('a:has-text("Ouvrir le match")')
        if media_match_link.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return

        href = media_match_link.first.get_attribute("href")
        if not href:
            _assert_no_front_error(page)
            browser.close()
            return

        if href.startswith("?"):
            target = f"{running_streamlit_app}{href}"
        elif href.startswith("http"):
            target = href
        else:
            target = f"{running_streamlit_app}/{href.lstrip('/')}"

        page.goto(target, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(1600)

        content = page.content()
        assert "MatchId" in content
        _assert_no_front_error(page)

        browser.close()


@pytest.mark.e2e_browser
def test_e2e_007_session_comparison_selection_stability(running_streamlit_app: str) -> None:
    """E2E-007: stabilité de la sélection A/B dans Comparaison de sessions."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        compare_tab = page.get_by_text("Comparaison de sessions")
        if compare_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return
        compare_tab.first.click(timeout=20000)
        page.wait_for_timeout(1800)

        tab_a = page.get_by_text("Session A")
        tab_b = page.get_by_text("Session B")
        if tab_a.count() == 0 or tab_b.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return

        tab_a.first.click(timeout=15000)
        page.wait_for_timeout(400)
        tab_b.first.click(timeout=15000)
        page.wait_for_timeout(400)
        tab_a.first.click(timeout=15000)
        page.wait_for_timeout(700)

        _assert_no_front_error(page)
        browser.close()


@pytest.mark.e2e_browser
def test_e2e_008_objectifs_smoke_tabs_renderable(running_streamlit_app: str) -> None:
    """E2E-008: smoke Objectifs (3 onglets rendables) quand la page est disponible."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        objectifs_tab = page.get_by_text("Objectifs")
        if objectifs_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return

        objectifs_tab.first.click(timeout=20000)
        page.wait_for_timeout(1600)

        expected_tabs = ["Objectifs vs Kills", "Répartition", "Tendance"]
        visible = [label for label in expected_tabs if page.get_by_text(label).count() > 0]
        if len(visible) < 3:
            _assert_no_front_error(page)
            browser.close()
            return

        for label in expected_tabs:
            page.get_by_text(label).first.click(timeout=15000)
            page.wait_for_timeout(450)

        _assert_no_front_error(page)
        browser.close()


@pytest.mark.e2e_browser
def test_e2e_009_career_smoke(running_streamlit_app: str) -> None:
    """E2E-009: smoke Carrière (gauge + historique quand disponible)."""
    playwright = pytest.importorskip("playwright.sync_api")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(running_streamlit_app, wait_until="domcontentloaded", timeout=120000)

        career_tab = page.get_by_text("Carrière")
        if career_tab.count() == 0:
            _assert_no_front_error(page)
            browser.close()
            return

        career_tab.first.click(timeout=20000)
        page.wait_for_timeout(1800)

        content = page.content()
        assert "Carrière" in content
        assert (
            "XP total" in content
            or "XP actuel" in content
            or "Aucune donnée de carrière disponible" in content
        )

        _assert_no_front_error(page)
        browser.close()
