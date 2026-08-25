#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "pdf" / "article.pdf.md"
FRAMES = ROOT / "assets" / "frames"
HTML_OUT = ROOT / "pdf" / "article.html"
PDF_OUT = ROOT / "pdf" / "the-cpu-explainer.pdf"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def resolve_frames(stem, spec):
    files = sorted(FRAMES.glob(f"{stem}-*.png"))
    if not files:
        return []
    if spec == "last":
        return [files[-1]]
    if spec == "first":
        return [files[0]]
    if spec == "all":
        return files
    picks = []
    for token in spec.split(","):
        n = int(token.strip())
        if 1 <= n <= len(files):
            picks.append(files[n - 1])
    return picks


def expand(match):
    tag = match.group(0)
    spec = re.search(r'pdf-frames="([^"]+)"', tag).group(1)
    stem = re.search(r'src="\./assets/final/([^"]+)\.gif"', tag).group(1)
    alt_match = re.search(r'alt="([^"]*)"', tag)
    cls_match = re.search(r'class="([^"]*)"', tag)
    alt = alt_match.group(1) if alt_match else ""
    cls = f' class="{cls_match.group(1)}"' if cls_match else ""

    stripped = re.sub(r'\s*pdf-frames="[^"]*"', "", tag)
    if spec == "keep":
        return stripped

    frames = resolve_frames(stem, spec)
    if not frames:
        print(f"no frames for {stem}, keeping gif reference", file=sys.stderr)
        return stripped

    return "\n\n".join(
        f'<img{cls} src="./assets/frames/{f.name}" alt="{alt}">' for f in frames
    )


def strip_frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip()
    return text


def markdown_to_html(text):
    result = subprocess.run(
        ["npx", "-y", "marked", "--gfm"],
        input=text, text=True, capture_output=True, cwd=ROOT, check=True,
    )
    return result.stdout


def wrap(body):
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>The CPU: A very tall pile of simple</title>
<style>
:root {{
  --bg: #0f0f10;
  --ink: #e6e0d0;
  --muted: #8a8578;
  --rule: #2a2a2c;
  --accent: #c9a961;
  --code-bg: #1a1a1c;
}}
html, body {{
  background: var(--bg);
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}
body {{
  font-family: "New York", ui-serif, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  max-width: 680px;
  margin: 0 auto;
  padding: 60px 24px 80px;
  font-size: 17px;
  line-height: 1.75;
  color: var(--ink);
  text-rendering: geometricPrecision;
  -webkit-font-smoothing: antialiased;
}}
p {{ margin: 0 0 1.1em; text-align: justify; hyphens: auto; }}
h1, h2, h3, h4 {{
  font-family: "New York", ui-serif, Georgia, serif;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #f4efe1;
  break-after: avoid;
}}
h1 {{
  font-size: 2.4em;
  line-height: 1.15;
  margin: 0.2em 0 0.6em;
  text-align: center;
  font-weight: 500;
  letter-spacing: -0.02em;
}}
h1 + p {{ text-align: center; color: var(--muted); font-style: italic; }}
h2 {{
  font-size: 1.5em;
  margin: 2.4em 0 0.8em;
  padding-bottom: 0.2em;
  border-bottom: 1px solid var(--rule);
}}
h3 {{ font-size: 1.15em; margin: 1.8em 0 0.6em; color: var(--accent); font-style: italic; font-weight: 500; }}
img {{ max-width: 100%; display: block; margin: 32px auto; break-inside: avoid; }}
img.small {{ max-width: 260px; }}
figure {{ margin: 32px 0; text-align: center; }}
figcaption {{ color: var(--muted); font-size: 0.9em; font-style: italic; margin-top: 8px; }}
code {{
  background: var(--code-bg);
  color: #d6cdb5;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.88em;
  font-family: "SF Mono", ui-monospace, "JetBrains Mono", Menlo, monospace;
}}
pre {{ background: var(--code-bg); border: 1px solid var(--rule); border-radius: 6px; padding: 14px 18px; overflow-x: auto; }}
pre code {{ background: transparent; padding: 0; }}
blockquote {{
  border-left: 2px solid var(--accent);
  margin: 1.4em 0;
  padding: 0.2em 20px;
  color: #c9c2b0;
  font-style: italic;
}}
hr {{
  border: none;
  height: 40px;
  margin: 3em 0;
  background: no-repeat center / auto 10px;
  background-image: radial-gradient(circle, var(--muted) 1.5px, transparent 2px);
  background-size: 14px 10px;
}}
a {{ color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(201,169,97,0.35); }}
ul, ol {{ padding-left: 1.4em; }}
li {{ margin: 0.3em 0; }}
strong {{ color: #f4efe1; }}
em {{ color: #efe8d6; }}
@page {{ size: A4; margin: 22mm; }}
@media print {{
  html, body {{ background: var(--bg); }}
  h1, h2, h3, img, pre {{ break-inside: avoid; }}
  h2 {{ break-before: auto; }}
}}
</style></head><body>
{body}
</body></html>"""


def main():
    if not SRC.exists():
        print(f"{SRC} not found. run prepare.py first.", file=sys.stderr)
        sys.exit(1)

    text = SRC.read_text()
    text = strip_frontmatter(text)
    pattern = re.compile(r'<img [^>]*>')
    text = pattern.sub(lambda m: expand(m) if "pdf-frames=" in m.group(0) else m.group(0), text)

    body = markdown_to_html(text)
    body = body.replace('"./assets/', '"../assets/')

    HTML_OUT.write_text(wrap(body))

    subprocess.run([
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_OUT}",
        HTML_OUT.as_uri(),
    ], check=True)

    print(f"wrote {PDF_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
