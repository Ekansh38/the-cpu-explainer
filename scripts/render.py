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
@page {{ size: A4; margin: 22mm 24mm; }}
html, body {{
  background: #111;
  color: #e6e6e6;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
  margin: 0;
}}
body {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: 12pt;
  line-height: 1.55;
}}
h1 {{ font-size: 22pt; margin: 0 0 1em; }}
h2 {{ font-size: 16pt; margin: 2em 0 0.5em; break-after: avoid; }}
h3 {{ font-size: 13pt; margin: 1.5em 0 0.5em; break-after: avoid; }}
p {{ margin: 0 0 1em; orphans: 3; widows: 3; }}
img {{ max-width: 100%; max-height: 21cm; display: block; margin: 1.2em auto; break-inside: avoid; }}
img.small {{ max-width: 220px; }}
code {{ font-family: "Courier New", monospace; font-size: 0.9em; }}
pre {{ background: #1a1a1a; padding: 12px; overflow-x: auto; break-inside: avoid; }}
blockquote {{ border-left: 2px solid #444; margin: 1em 0; padding-left: 1em; color: #bbb; break-inside: avoid; }}
hr {{ border: none; border-top: 1px solid #444; margin: 2em 0; }}
a {{ color: inherit; }}
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
