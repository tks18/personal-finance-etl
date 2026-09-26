import base64
import json
import os
import posixpath
from importlib.resources import files

import markdown  # type: ignore[import-untyped]

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

    @staticmethod
    def _load_mermaid_js() -> str:
        """Load the bundled Mermaid runtime."""

        try:
            asset = (
                files("personal_finance_etl.frontend.commons.docs")
                .joinpath("assets")
                .joinpath("mermaid")
                .joinpath("mermaid.min.js")
            )
            return asset.read_text(encoding="utf-8")

        except (FileNotFoundError, OSError):
            print("Bundled Mermaid runtime could not be loaded.")
            return ""

    def build_html_app(self) -> str:
        """Read all markdown docs and compile them into a single HTML web app string."""
        docs_to_render: dict[str, dict[str, str]] = {}
        path_to_title: dict[str, str] = {}

        docs_dir = self.catalog.docs_dir
        mermaid_js = self._load_mermaid_js()

        for entry in self.catalog.get_all_docs():
            full_path = os.path.normpath(os.path.join(docs_dir, entry.path))
            # Canonical document identity is repository/package-root relative.
            # Manifest entries are relative to docs/, so prefix with docs/ first:
            #   ../README.md -> README.md
            #   README.md    -> docs/README.md
            #   finance/x.md -> docs/finance/x.md
            manifest_path = entry.path.replace("\\", "/")
            norm_path = posixpath.normpath(posixpath.join("docs", manifest_path))

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

                    docs_to_render[display_name] = {"path": norm_path, "raw_md": content}
                    path_to_title[norm_path] = display_name

        # Convert to HTML and build JS data structure
        html_sections: dict[str, dict[str, str]] = {}
        for title, doc_data in docs_to_render.items():
            md_content = doc_data["raw_md"]
            md_content = md_content.replace("> [!IMPORTANT]", "> **IMPORTANT:**")
            md_content = md_content.replace("> [!NOTE]", "> **NOTE:**")
            md_content = md_content.replace("> [!WARNING]", "> **WARNING:**")
            md_content = md_content.replace("> [!CAUTION]", "> **CAUTION:**")
            md_content = md_content.replace("> [!TIP]", "> **TIP:**")

            html = markdown.markdown(
                md_content, extensions=["fenced_code", "tables", "nl2br", "sane_lists"]
            )
            html_sections[title] = {
                "path": doc_data["path"],
                "html": html.replace("`", "\\`").replace("$", "\\$"),
            }

        # Build Left Sidebar UI
        sidebar_links = ""
        first_title: str | None = None

        sections = self.catalog.get_sections()
        for section_name, entries in sections.items():
            sidebar_links += '<details class="section-group" open>\n'
            sidebar_links += f'  <summary class="section-title">{section_name}</summary>\n'
            sidebar_links += '  <div class="section-links">\n'
            for entry in entries:
                display_name = (
                    f"{entry.section} - {entry.title}" if entry.section != "Root" else entry.title
                )
                if display_name not in html_sections:
                    continue
                if first_title is None:
                    first_title = display_name
                # Escape for HTML attributes
                safe_title = display_name.replace("'", "\\'")
                sidebar_links += f'    <a href="#" onclick="loadDoc(\'{safe_title}\', this)" class="nav-link" data-title="{display_name}">{entry.title}</a>\n'
            sidebar_links += "  </div>\n</details>\n"

        js_dict_entries = ",\n".join(
            [
                f"'{title}': {{ path: '{data['path']}', html: `{data['html']}` }}"
                for title, data in html_sections.items()
            ]
        )
        js_docs_data = f"const docsData = {{\n{js_dict_entries}\n}};"
        js_path_map = f"const pathToTitle = {json.dumps(path_to_title)};"

        template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Guides & About</title>
            <script>
              {mermaid_js}
            </script>
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
                    flex-direction: column;
                    height: 100vh;
                    overflow: hidden;
                }}
                
                /* Top Header */
                #topbar {{
                    height: 50px;
                    background-color: var(--bg-sidebar);
                    border-bottom: 1px solid var(--border);
                    display: flex;
                    align-items: center;
                    padding: 0 20px;
                    flex-shrink: 0;
                }}
                .app-title {{
                    font-size: 1.2rem;
                    font-weight: bold;
                    color: #F8FAFC;
                    letter-spacing: 0.05em;
                }}
                
                #app-container {{
                    display: flex;
                    flex: 1;
                    overflow: hidden;
                }}
                
                /* Sidebar (Left & Right) */
                #sidebar, #right-sidebar {{
                    width: 250px;
                    background-color: var(--bg-sidebar);
                    display: flex;
                    flex-direction: column;
                    overflow-y: auto;
                    flex-shrink: 0;
                }}
                #sidebar {{ border-right: 1px solid var(--border); width: 260px; }}
                #right-sidebar {{ border-left: 1px solid var(--border); width: 280px; }}

                /* Custom Scrollbar for modern look */
                ::-webkit-scrollbar {{
                    width: 8px;
                    height: 8px;
                }}
                ::-webkit-scrollbar-track {{
                    background: transparent;
                }}
                ::-webkit-scrollbar-thumb {{
                    background: #334155;
                    border-radius: 4px;
                }}
                ::-webkit-scrollbar-thumb:hover {{
                    background: #475569;
                }}
                
                .sidebar-header {{
                    padding: 20px;
                    font-size: 1.2rem;
                    font-weight: bold;
                    border-bottom: 1px solid var(--border);
                    color: #7DD3FC;
                }}
                
                /* Left Sidebar Collapsible Sections */
                .section-group {{
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }}
                .section-title {{
                    padding: 12px 20px;
                    font-size: 0.95em;
                    font-weight: bold;
                    color: #94A3B8;
                    cursor: pointer;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    user-select: none;
                }}
                .section-title:hover {{ color: #E2E8F0; }}
                
                .nav-link {{
                    display: block;
                    padding: 8px 20px 8px 30px;
                    color: var(--text-dim);
                    text-decoration: none;
                    transition: all 0.2s;
                    cursor: pointer;
                    font-size: 0.95em;
                }}
                .nav-link:hover {{
                    background-color: rgba(255,255,255,0.05);
                    color: var(--text-main);
                }}
                .nav-link.active {{
                    background-color: rgba(37, 99, 235, 0.2);
                    color: #60A5FA;
                    border-left: 3px solid #60A5FA;
                    padding-left: 27px; /* compensate for border */
                }}
                
                /* Right Sidebar TOC */
                details.toc-group > summary {{
                    list-style: none;
                }}
                details.toc-group > summary::-webkit-details-marker {{
                    display: none;
                }}
                details.toc-group > summary {{
                    position: relative;
                    cursor: pointer;
                }}
                details.toc-group > summary::before {{
                    content: '▶';
                    position: absolute;
                    left: 6px;
                    top: 10px;
                    font-size: 0.65em;
                    color: var(--text-dim);
                    transition: transform 0.2s;
                }}
                details.toc-group[open] > summary::before {{
                    transform: rotate(90deg);
                }}
                
                .toc-link {{
                    display: block;
                    padding: 6px 20px;
                    color: var(--text-dim);
                    text-decoration: none;
                    font-size: 0.85em;
                    transition: all 0.2s;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    border-left: 2px solid transparent;
                }}
                .toc-link:hover {{ 
                    color: var(--text-main); 
                    background-color: rgba(255,255,255,0.05);
                }}
                .toc-h1 {{ 
                    padding-left: 22px; 
                    font-weight: bold; 
                    padding-top: 8px; 
                    padding-bottom: 8px;
                    color: #E2E8F0; 
                    font-size: 0.95em;
                }}
                .toc-h1:hover {{ background-color: transparent; }}
                .toc-h2 {{ padding-left: 22px; }}
                .toc-h3 {{ padding-left: 40px; font-size: 0.8em; opacity: 0.8; }}
                
                #toc-container {{
                    padding-bottom: 20px;
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
            <div id="topbar">
                <div class="app-title">📊 Shan's Personal Finance ETL</div>
            </div>
            <div id="app-container">
                <div id="sidebar">
                    {sidebar_links}
                </div>
                <div id="main-content">
                    <div id="content-container"></div>
                </div>
                <div id="right-sidebar">
                    <div class="sidebar-header">📑 On This Page</div>
                    <div id="toc-container"></div>
                </div>
            </div>

            <script>
                const mermaidAvailable = typeof window.mermaid !== 'undefined';

                if (mermaidAvailable) {{
                  mermaid.initialize({{
                      startOnLoad: false,
                      theme: 'dark',
                      securityLevel: 'strict'
                  }});
                }} else {{
                  console.warn(
                      'Bundled Mermaid runtime unavailable; '
                      + 'diagram source will remain visible.'
                  );
                }}

                {js_docs_data}
                {js_path_map}
                
                let currentDocPath = "";

                function loadDoc(title, element) {{
                    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
                    if (element) {{
                        element.classList.add('active');
                        // Expand the parent details if collapsed
                        let details = element.closest('details');
                        if (details) details.setAttribute('open', '');
                    }} else {{
                        // Fallback: try to find it by attribute
                        let link = document.querySelector(`.nav-link[data-title="${{title}}"]`);
                        if (link) {{
                            link.classList.add('active');
                            let details = link.closest('details');
                            if (details) details.setAttribute('open', '');
                        }}
                    }}

                    const doc = docsData[title];
                    if (!doc) return;
                    currentDocPath = doc.path;

                    const container = document.getElementById('content-container');
                    container.innerHTML = doc.html;
                    document.getElementById('main-content').scrollTop = 0;

                    if (mermaidAvailable) {{
                        const mermaidCodes = document.querySelectorAll('code.language-mermaid');
                        mermaidCodes.forEach(codeBlock => {{
                            const pre = codeBlock.parentElement;
                            const div = document.createElement('div');
                            div.className = 'mermaid';
                            div.textContent = codeBlock.textContent;
                            pre.replaceWith(div);
                        }});
                    }}
                    
                    // Fix links
                    container.querySelectorAll('a').forEach(a => {{
                        let href = a.getAttribute('href');
                        if (href && href.endsWith('.md')) {{
                            try {{
                                // Use a fake base URL to resolve the relative path
                                let url = new URL(href, 'http://local/' + currentDocPath);
                                let resolvedPath = url.pathname.substring(1);
                                if (pathToTitle[resolvedPath]) {{
                                    a.href = "#";
                                    a.onclick = (e) => {{
                                        e.preventDefault();
                                        loadDoc(pathToTitle[resolvedPath], document.querySelector(`.nav-link[data-title="${{pathToTitle[resolvedPath]}}"]`));
                                    }};
                                }}
                            }} catch (e) {{ console.error(e); }}
                        }} else if (href && !href.startsWith('#')) {{
                            a.setAttribute('target', '_blank');
                        }}
                    }});
                    
                    if (mermaidAvailable) {{
                        mermaid.run().catch(err => console.error('Mermaid render failed:', err));
                    }}
                    buildTableOfContents();
                }}

                function buildTableOfContents() {{
                    const tocContainer = document.getElementById('toc-container');
                    tocContainer.innerHTML = '';
                    
                    const headings = document.getElementById('content-container').querySelectorAll('h1, h2, h3');
                    if (headings.length === 0) {{
                        tocContainer.innerHTML = '<div style="padding: 20px; color: #94A3B8; font-size: 0.9em; font-style: italic;">No headings found</div>';
                        return;
                    }}
                    
                    let currentH1Details = null;
                    let currentH2Details = null;
                    
                    headings.forEach((heading, index) => {{
                        if (!heading.id) {{
                            heading.id = 'heading-' + index;
                        }}
                        
                        const level = parseInt(heading.tagName.substring(1));
                        const text = heading.textContent;
                        
                        const a = document.createElement('a');
                        a.className = 'toc-link toc-h' + level;
                        a.href = '#' + heading.id;
                        a.textContent = text;
                        a.onclick = (e) => {{
                            e.preventDefault();
                            e.stopPropagation(); // prevent toggling the details
                            document.getElementById('main-content').scrollTo({{
                                top: heading.offsetTop - 60,
                                behavior: 'smooth'
                            }});
                        }};
                        
                        if (level === 1) {{
                            currentH1Details = document.createElement('details');
                            currentH1Details.className = 'toc-group';
                            currentH1Details.open = true;
                            
                            const summary = document.createElement('summary');
                            summary.appendChild(a);
                            currentH1Details.appendChild(summary);
                            
                            tocContainer.appendChild(currentH1Details);
                            currentH2Details = null;
                        }} else if (level === 2) {{
                            if (!currentH1Details) {{
                                tocContainer.appendChild(a);
                            }} else {{
                                currentH2Details = document.createElement('details');
                                currentH2Details.className = 'toc-group';
                                currentH2Details.open = true;
                                
                                const summary = document.createElement('summary');
                                summary.appendChild(a);
                                currentH2Details.appendChild(summary);
                                
                                currentH1Details.appendChild(currentH2Details);
                            }}
                        }} else if (level === 3) {{
                            if (currentH2Details) {{
                                currentH2Details.appendChild(a);
                            }} else if (currentH1Details) {{
                                currentH1Details.appendChild(a);
                            }} else {{
                                tocContainer.appendChild(a);
                            }}
                        }}
                    }});
                }}

                document.addEventListener("DOMContentLoaded", () => {{
                    loadDoc('{first_title}', null);
                }});
            </script>
        </body>
        </html>
        """
        return template
