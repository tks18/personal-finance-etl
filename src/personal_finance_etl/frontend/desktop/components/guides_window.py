"""
Unified pywebview window for rendering Markdown documentation and Guides.
Used by both the CustomTkinter GUI and the Rich CLI.
"""

import base64
import glob
import os
from pathlib import Path

import markdown
import webview

from personal_finance_etl.backend.utils.helpers import resource_path


def build_docs_html() -> str:
    """Read all markdown docs and compile them into a single HTML web app string."""

    # 1. Discover docs
    docs_to_render = {}

    def inject_logo(text: str, src_pattern: str) -> str:
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_f:
                b64_logo = base64.b64encode(img_f.read()).decode("utf-8")
                return text.replace(src_pattern, f'src="data:image/png;base64,{b64_logo}"')
        return text

    # 1. README first
    readme_path = resource_path("README.md")
    if os.path.exists(readme_path):
        with open(readme_path, encoding="utf-8") as f:
            docs_to_render["Readme"] = inject_logo(f.read(), 'src="logo.png"')

    # 2. Read docs folder
    docs_dir = resource_path("docs")
    about_text = ""

    if os.path.exists(docs_dir) and os.path.isdir(docs_dir):
        # Sort files alphabetically
        files = sorted(glob.glob(os.path.join(docs_dir, "*.md")))
        for file in files:
            name = Path(file).stem.replace("_", " ")
            with open(file, encoding="utf-8") as f:
                if name.lower() == "about":
                    about_text = f.read()
                else:
                    docs_to_render[name] = f.read()

    # 3. Process About.md and append it as the last item
    if about_text:
        docs_to_render["About"] = inject_logo(about_text, 'src="../logo.png"')

    # 2. Convert to HTML and build JS data structure
    html_sections = {}
    for title, md_content in docs_to_render.items():
        # Clean up github alerts to blockquotes for rendering
        md_content = md_content.replace("> [!IMPORTANT]", "> **IMPORTANT:**")
        md_content = md_content.replace("> [!NOTE]", "> **NOTE:**")
        md_content = md_content.replace("> [!WARNING]", "> **WARNING:**")
        md_content = md_content.replace("> [!CAUTION]", "> **CAUTION:**")
        md_content = md_content.replace("> [!TIP]", "> **TIP:**")

        # Convert markdown to HTML
        html = markdown.markdown(md_content, extensions=["tables", "fenced_code", "sane_lists"])
        # Escape for JS injection
        html_sections[title] = html.replace("`", "\\`").replace("$", "\\$")

    # 3. Build the UI HTML
    # Generate sidebar links
    sidebar_links = ""
    first_title = None
    for title in html_sections.keys():
        if first_title is None:
            first_title = title
        sidebar_links += (
            f'<a href="#" onclick="loadDoc(\'{title}\', this)" class="nav-link">{title}</a>\n'
        )

    # Generate JS dictionary
    js_dict_entries = ",\n".join([f"'{title}': `{html}`" for title, html in html_sections.items()])
    js_docs_data = f"const docsData = {{\n{js_dict_entries}\n}};"

    # Full HTML Template
    template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Guides & About</title>
        <!-- Mermaid for diagrams -->
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
            // Initialize Mermaid
            mermaid.initialize({{ startOnLoad: false, theme: 'dark' }});

            {js_docs_data}

            function loadDoc(title, element) {{
                // Update active state
                document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
                if (element) {{
                    element.classList.add('active');
                }} else {{
                    // Fallback to finding the first link
                    let firstLink = document.querySelector('.nav-link');
                    if (firstLink) firstLink.classList.add('active');
                }}

                // Inject HTML
                const container = document.getElementById('content-container');
                container.innerHTML = docsData[title] || "<h1>Document not found</h1>";
                
                // Scroll to top
                document.getElementById('main-content').scrollTop = 0;

                // Render Mermaid diagrams
                // Markdown library usually renders fenced code blocks as <pre><code class="mermaid">
                // We need to convert them to <div class="mermaid"> for Mermaid to process
                const mermaidCodes = document.querySelectorAll('code.language-mermaid');
                mermaidCodes.forEach(codeBlock => {{
                    const pre = codeBlock.parentElement;
                    const div = document.createElement('div');
                    div.className = 'mermaid';
                    div.textContent = codeBlock.textContent;
                    pre.replaceWith(div);
                }});
                
                // Open links externally
                container.querySelectorAll('a').forEach(a => {{
                    a.setAttribute('target', '_blank');
                }});
                
                // Run mermaid
                mermaid.run();
            }}

            // Load first doc on startup
            document.addEventListener("DOMContentLoaded", () => {{
                loadDoc('{first_title}', document.querySelector('.nav-link'));
            }});
        </script>
    </body>
    </html>
    """
    return template


def show_guides_window() -> None:
    """Create and show the pywebview documentation window."""
    html = build_docs_html()
    icon_path = resource_path("logo.ico")

    webview.create_window(
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
