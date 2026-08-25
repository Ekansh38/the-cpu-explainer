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
body {{ font-family: Georgia, serif; max-width: 720px; margin: 40px auto; padding: 0 20px; line-height: 1.55; color: #111; }}
h1, h2, h3 {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
h1 {{ font-size: 2em; }}
img {{ max-width: 100%; display: block; margin: 24px auto; break-inside: avoid; }}
img.small {{ max-width: 240px; }}
figure {{ margin: 24px 0; }}
code {{ background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }}
pre code {{ display: block; padding: 12px; overflow-x: auto; }}
blockquote {{ border-left: 3px solid #ccc; margin: 0; padding: 4px 16px; color: #444; }}
hr {{ border: none; border-top: 1px solid #ccc; margin: 40px 0; }}
a {{ color: inherit; }}
@page {{ size: A4; margin: 20mm; }}
</style></head><body>
{body}
</body></html>"""


def main():
    if not SRC.exists():
        print(f"{SRC} not found. run prepare.py first.", file=sys.stderr)
        sys.exit(1)

    text = SRC.read_text()
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
