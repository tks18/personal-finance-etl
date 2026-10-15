"""Documentation catalog and manifest parser.

Owns
----
- DocEntry: Data model representing a single documentation article or guide.
- DocsCatalog: Reads and validates the manifest.json file from the documentation tree.
- Ordering and grouping articles by logical topic section.

Does not own
-------------
- Markdown parsing or HTML rendering (owned by presentation.docs.renderer).
- Window creation or pywebview lifecycle (owned by presentation.docs.guides_window).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

__all__ = ["DocEntry", "DocsCatalog"]


@dataclass
class DocEntry:
    """Metadata entry for a single documentation page in the manifest."""

    section: str
    title: str
    path: str
    order: int


class DocsCatalog:
    """Parses and organizes the documentation manifest.json catalog.

    Parameters
    ----------
    docs_dir : str
        Root path to the documentation folder containing manifest.json.
    """

    def __init__(self, docs_dir: str) -> None:
        self.docs_dir = docs_dir
        self.manifest_path = os.path.join(docs_dir, "manifest.json")
        self.catalog: list[DocEntry] = self._build_catalog()

    def _build_catalog(self) -> list[DocEntry]:
        """Read manifest.json and construct the ordered list of DocEntries."""
        catalog: list[DocEntry] = []
        if not os.path.exists(self.manifest_path):
            return catalog

        with open(self.manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)

        for section_data in manifest_data.get("sections", []):
            section_title = str(section_data.get("title", ""))
            for page in section_data.get("pages", []):
                catalog.append(
                    DocEntry(
                        section=section_title,
                        title=str(page.get("title", "")),
                        path=str(page.get("path", "")),
                        order=int(page.get("order", 9999)),
                    )
                )

        return sorted(catalog, key=lambda x: (x.order, x.title))

    def get_all_docs(self) -> list[DocEntry]:
        """Return all cataloged documentation entries ordered by weight and title."""
        return self.catalog

    def get_sections(self) -> dict[str, list[DocEntry]]:
        """Return documentation entries grouped by section title."""
        sections: dict[str, list[DocEntry]] = {}
        for entry in self.catalog:
            sections.setdefault(entry.section, []).append(entry)
        return sections
