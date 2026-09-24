import json
import os
from dataclasses import dataclass


@dataclass
class DocEntry:
    section: str
    title: str
    path: str
    order: int


class DocsCatalog:
    def __init__(self, docs_dir: str):
        self.docs_dir = docs_dir
        self.manifest_path = os.path.join(docs_dir, "manifest.json")
        self.catalog: list[DocEntry] = self._build_catalog()

    def _build_catalog(self) -> list[DocEntry]:
        catalog: list[DocEntry] = []
        if not os.path.exists(self.manifest_path):
            return catalog

        with open(self.manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)

        for section_data in manifest_data.get("sections", []):
            section_title = section_data.get("title", "")
            for page in section_data.get("pages", []):
                catalog.append(
                    DocEntry(
                        section=section_title,
                        title=page.get("title", ""),
                        path=page.get("path", ""),
                        order=page.get("order", 9999),
                    )
                )

        return sorted(catalog, key=lambda x: (x.order, x.title))

    def get_all_docs(self) -> list[DocEntry]:
        return self.catalog

    def get_sections(self) -> dict[str, list[DocEntry]]:
        sections: dict[str, list[DocEntry]] = {}
        for entry in self.catalog:
            sections.setdefault(entry.section, []).append(entry)
        return sections
