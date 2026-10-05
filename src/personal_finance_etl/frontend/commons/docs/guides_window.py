"""
Unified pywebview window for rendering Markdown documentation and Guides.
Used by both the CustomTkinter GUI and the Rich CLI.
"""

import os
import tempfile

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

    # WebView2's NavigateToString() has a hard ~1.5 MB limit on the HTML string.
    # Writing to a temp file and using url= bypasses this entirely.
    tmp_html = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        encoding="utf-8",
        delete=False,
        prefix="pf_etl_docs_",
    )
    try:
        tmp_html.write(html)
        tmp_html.flush()
        tmp_html.close()

        url = f"file:///{tmp_html.name.replace(os.sep, '/')}"

        webview.create_window(  # pyright: ignore[reportUnknownMemberType]
            "Shan's Personal Finance ETL - Guides & About",
            url=url,
            width=1280,
            height=850,
            background_color="#0D1117",
        )

        if os.path.exists(icon_path):
            webview.start(icon=icon_path)
        else:
            webview.start()
    finally:
        # Clean up the temp file after the window closes
        if os.path.exists(tmp_html.name):
            os.remove(tmp_html.name)
