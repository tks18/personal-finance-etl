"""
Unified pywebview window for rendering Markdown documentation and Guides.
Used by both the CustomTkinter GUI and the Rich CLI.
"""

import os

import webview

from personal_finance_etl.backend.utils.helpers import resource_path
from personal_finance_etl.frontend.commons.docs.manifest import DocsCatalog
from personal_finance_etl.frontend.commons.docs.renderer import DocsRenderer


def show_guides_window() -> None:
    """Create and show the pywebview documentation window."""
    docs_dir = resource_path("docs")
    catalog = DocsCatalog(docs_dir)
    renderer = DocsRenderer(catalog)

    html = renderer.build_html_app()
    icon_path = resource_path("logo.ico")

    webview.create_window(  # pyright: ignore[reportUnknownMemberType]
        "Shan's Personal Finance ETL - Guides & About",
        html=html,
        width=1280,
        height=850,
        background_color="#0D1117",
    )

    if os.path.exists(icon_path):
        webview.start(icon=icon_path)
    else:
        webview.start()
