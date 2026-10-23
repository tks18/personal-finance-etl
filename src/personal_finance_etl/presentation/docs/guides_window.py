"""Pywebview documentation viewer window for guides and architecture reference.

Owns
----
- show_guides_window: Compiles docs catalog and displays it inside an embedded native webview window.
- Temporary HTML caching and automatic cleanup upon window dismissal.

Does not own
-------------
- HTML string construction or syntax highlighting (owned by presentation.docs.renderer).
- Manifest parsing (owned by presentation.docs.manifest).
"""

from __future__ import annotations

import os
import tempfile

import webview

from personal_finance_etl.infrastructure.filesystem.paths import resource_path
from personal_finance_etl.presentation.docs.manifest import DocsCatalog
from personal_finance_etl.presentation.docs.renderer import DocsRenderer

__all__ = ["show_guides_window"]


def show_guides_window() -> None:
    """Create and display the pywebview documentation and guides window."""
    docs_dir = resource_path("docs")
    catalog = DocsCatalog(docs_dir)
    renderer = DocsRenderer(catalog)

    html = renderer.build_html_app()
    icon_path = resource_path("logo.ico")

    # WebView2 NavigateToString has a hard ~1.5 MB string limit.
    # Writing to a temp file and passing file:/// URL bypasses this completely.
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        encoding="utf-8",
        delete=False,
        prefix="pf_etl_docs_",
    ) as tmp_html:
        tmp_html.write(html)
        tmp_html.flush()
        tmp_name = tmp_html.name

    try:
        url = f"file:///{tmp_name.replace(os.sep, '/')}"

        # Exception TYP-005 [THIRD_PARTY_TYPING_GAP]: pywebview window builder lacks static stubs
        webview.create_window(  # pyright: ignore[reportUnknownMemberType]
            "Personal Finance ETL · Guides & About",
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
        # Clean up temporary file after webview window is closed
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass
