import base64
import os

import markdown

from personal_finance_etl.backend.utils.helpers import resource_path
from personal_finance_etl.frontend.commons.docs.manifest import DocsCatalog


class DocsRenderer:
    def __init__(self, catalog: DocsCatalog):
        self.catalog = catalog

    def _inject_logo(self, text: str, src_pattern: str) -> str:
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_f:
                b64_logo = base64.b64encode(img_f.read()).decode("utf-8")
                return text.replace(src_pattern, f'src="data:image/png;base64,{b64_logo}"')
        return text

    def build_html_app(self) -> str:
        """Read all markdown docs and compile them into a single HTML web app string."""
        docs_to_render: dict[str, str] = {}

        # Fallback root processing if present in catalog as README.md
        docs_dir = self.catalog.docs_dir

        for entry in self.catalog.get_all_docs():
            full_path = os.path.join(docs_dir, entry.path)
            if os.path.exists(full_path):
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()

                    if "README.md" in entry.path:
                        content = self._inject_logo(content, 'src="logo.png"')
                    elif "about" in entry.path.lower():
                        content = self._inject_logo(content, 'src="../logo.png"')

                    display_name = (
                        f"{entry.section} - {entry.title}"
                        if entry.section != "Root"
                        else entry.title
                    )
                    docs_to_render[display_name] = content

        # 2. Convert to HTML and build JS data structure
        html_sections: dict[str, str] = {}
        for title, md_content in docs_to_render.items():
            # Clean up github alerts to blockquotes for rendering
            md_content = md_content.replace("> [!IMPORTANT]", "> **IMPORTANT:**")
            md_content = md_content.replace("> [!NOTE]", "> **NOTE:**")
            md_content = md_content.replace("> [!WARNING]", "> **WARNING:**")
            md_content = md_content.replace("> [!CAUTION]", "> **CAUTION:**")
            md_content = md_content.replace("> [!TIP]", "> **TIP:**")

            html = markdown.markdown(
                md_content, extensions=["fenced_code", "tables", "nl2br", "sane_lists"]
            )
            html_sections[title] = html.replace("`", "\\`").replace("$", "\\$")

        # 3. Build the UI HTML
        sidebar_links = ""
        first_title: str | None = None
        for title in html_sections.keys():
            if first_title is None:
                first_title = title
            sidebar_links += (
                f'<a href="#" onclick="loadDoc(\'{title}\', this)" class="nav-link">{title}</a>\n'
            )

        js_dict_entries = ",\n".join(
            [f"'{title}': `{html}`" for title, html in html_sections.items()]
        )
        js_docs_data = f"const docsData = {{\n{js_dict_entries}\n}};"

        template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Guides & About</title>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <style>
                :root {{
                    --bg-main: #0D1117;
                    --bg-sidebar: #080C14;
                    --text-main: #E2E8F0;
                    --text-dim: #94A3B8;
                    --accent: #2563EB;
                    --accent-hover: #3B82F6;
                    --border: #1E293B;
                    --code-bg: #1E293B;
                }}
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                    background-color: var(--bg-main);
                    color: var(--text-main);
                    display: flex;
                    height: 100vh;
                    overflow: hidden;
                }}
                /* Sidebar */
                #sidebar {{
                    width: 250px;
                    background-color: var(--bg-sidebar);
                    border-right: 1px solid var(--border);
                    display: flex;
                    flex-direction: column;
                    overflow-y: auto;
                }}
                .sidebar-header {{
                    padding: 20px;
                    font-size: 1.2rem;
                    font-weight: bold;
                    border-bottom: 1px solid var(--border);
                    color: #7DD3FC;
                }}
                .nav-link {{
                    padding: 12px 20px;
                    color: var(--text-dim);
                    text-decoration: none;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                    transition: all 0.2s;
                    cursor: pointer;
                }}
                .nav-link:hover {{
                    background-color: rgba(255,255,255,0.05);
                    color: var(--text-main);
                }}
                .nav-link.active {{
                    background-color: rgba(37, 99, 235, 0.2);
                    color: #60A5FA;
                    border-left: 3px solid #60A5FA;
                }}
                /* Main Content */
                #main-content {{
                    flex: 1;
                    overflow-y: auto;
                    padding: 40px;
                    line-height: 1.6;
                }}
                #content-container {{
                    max-width: 900px;
                    margin: 0 auto;
                }}
                /* Markdown Styling */
                h1, h2, h3, h4 {{
                    color: #F8FAFC;
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                    border-bottom: 1px solid var(--border);
                    padding-bottom: 0.3em;
                }}
                a {{ color: #60A5FA; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                code {{
                    background-color: var(--code-bg);
                    padding: 0.2em 0.4em;
                    border-radius: 4px;
                    font-family: Consolas, monospace;
                    font-size: 0.9em;
                }}
                pre {{
                    background-color: var(--code-bg);
                    padding: 16px;
                    border-radius: 6px;
                    overflow-x: auto;
                    border: 1px solid var(--border);
                }}
                pre code {{ background-color: transparent; padding: 0; }}
                blockquote {{
                    border-left: 4px solid var(--accent);
                    margin: 0;
                    padding-left: 16px;
                    color: var(--text-dim);
                    background-color: rgba(37, 99, 235, 0.1);
                    padding: 10px 16px;
                    border-radius: 0 4px 4px 0;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 1em 0;
                }}
                th, td {{
                    border: 1px solid var(--border);
                    padding: 8px 12px;
                    text-align: left;
                }}
                th {{ background-color: var(--bg-sidebar); }}
                img {{ max-width: 100%; height: auto; }}
                hr {{ border: 0; border-top: 1px solid var(--border); margin: 2em 0; }}
            </style>
        </head>
        <body>
            <div id="sidebar">
                <div class="sidebar-header">📚 Documentation</div>
                {sidebar_links}
            </div>
            <div id="main-content">
                <div id="content-container"></div>
            </div>

            <script>
                mermaid.initialize({{ startOnLoad: false, theme: 'dark' }});

                {js_docs_data}

                function loadDoc(title, element) {{
                    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
                    if (element) {{
                        element.classList.add('active');
                    }} else {{
                        let firstLink = document.querySelector('.nav-link');
                        if (firstLink) firstLink.classList.add('active');
                    }}

                    const container = document.getElementById('content-container');
                    container.innerHTML = docsData[title] || "<h1>Document not found</h1>";
                    document.getElementById('main-content').scrollTop = 0;

                    const mermaidCodes = document.querySelectorAll('code.language-mermaid');
                    mermaidCodes.forEach(codeBlock => {{
                        const pre = codeBlock.parentElement;
                        const div = document.createElement('div');
                        div.className = 'mermaid';
                        div.textContent = codeBlock.textContent;
                        pre.replaceWith(div);
                    }});
                    
                    container.querySelectorAll('a').forEach(a => {{
                        a.setAttribute('target', '_blank');
                    }});
                    
                    mermaid.run();
                }}

                document.addEventListener("DOMContentLoaded", () => {{
                    loadDoc('{first_title}', document.querySelector('.nav-link'));
                }});
            </script>
        </body>
        </html>
        """
        return template
