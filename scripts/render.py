#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "pdf" / "article.pdf.md"
FRAMES = ROOT / "assets" / "frames"
FINAL = ROOT / "assets" / "final"
RASTER = ROOT / "pdf" / ".raster"
TYP_OUT = ROOT / "pdf" / "article.typ"
PDF_OUT = ROOT / "pdf" / "the-cpu-explainer.pdf"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RASTER_WIDTH = 1800

PREAMBLE = """\
#set page(paper: "a4", fill: rgb("#111111"), margin: (x: 24mm, y: 22mm))
#set text(fill: rgb("#e6e6e6"))
#show heading.where(level: 1): it => block(below: 2em, it)

"""


def strip_frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip()
    return text


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
    if "pdf-frames=" not in tag:
        return tag
    spec = re.search(r'pdf-frames="([^"]+)"', tag).group(1)
    src_match = re.search(r'src="\./assets/final/([^"]+)\.gif"', tag)
    if not src_match:
        return tag
    stem = src_match.group(1)
    alt_match = re.search(r'alt="([^"]*)"', tag)
    alt = alt_match.group(1) if alt_match else ""

    if spec == "keep":
        return f"![{alt}](./assets/final/{stem}.gif)"
    frames = resolve_frames(stem, spec)
    if not frames:
        print(f"no frames for {stem}, keeping gif reference", file=sys.stderr)
        return f"![{alt}](./assets/final/{stem}.gif)"
    return "\n\n".join(f"![{alt}](./assets/frames/{f.name})" for f in frames)


def html_img_to_md(match):
    tag = match.group(0)
    src_match = re.search(r'src="([^"]+)"', tag)
    if not src_match:
        return ""
    src = src_match.group(1)
    alt_match = re.search(r'alt="([^"]*)"', tag)
    alt = alt_match.group(1) if alt_match else ""
    return f"![{alt}]({src})"


def svg_aspect(svg_path):
    text = svg_path.read_text()
    m = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"', text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'width="([\d.]+)"[^>]*height="([\d.]+)"', text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 800.0, 600.0


def rasterize(svg_path):
    RASTER.mkdir(exist_ok=True)
    out = RASTER / (svg_path.stem + ".png")
    if out.exists() and out.stat().st_mtime >= svg_path.stat().st_mtime:
        return out

    w, h = svg_aspect(svg_path)
    px_w = RASTER_WIDTH
    px_h = max(1, int(px_w * h / w))

    wrapper = RASTER / f".{svg_path.stem}.html"
    wrapper.write_text(
        f'<html><head><style>html,body{{margin:0;background:transparent}}'
        f'img{{width:{px_w}px;height:{px_h}px;display:block}}</style></head>'
        f'<body><img src="{svg_path.as_uri()}"></body></html>'
    )

    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu",
        f"--window-size={px_w},{px_h}",
        "--hide-scrollbars",
        "--default-background-color=00000000",
        f"--screenshot={out}",
        wrapper.as_uri(),
    ], check=True, capture_output=True)
    wrapper.unlink()
    return out


def swap_svg_refs(text):
    def sub(match):
        alt, src = match.group(1), match.group(2)
        if not src.endswith(".svg"):
            return match.group(0)
        svg_path = (ROOT / src.lstrip("/").removeprefix("./")).resolve()
        if not svg_path.exists():
            return match.group(0)
        png = rasterize(svg_path)
        rel = "/" + str(png.relative_to(ROOT))
        return f"![{alt}]({rel})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", sub, text)


def to_typst(md_text):
    result = subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "typst"],
        input=md_text, text=True, capture_output=True, check=True,
    )
    return result.stdout


def main():
    if not SRC.exists():
        print(f"{SRC} not found. run prepare.py first.", file=sys.stderr)
        sys.exit(1)

    text = SRC.read_text()
    text = strip_frontmatter(text)
    text = re.sub(r'<a id="[^"]*"></a>\s*', "", text)
    text = re.sub(r"\[([^\]]+)\]\(#[^)]+\)", r"\1", text)
    text = re.sub(r"<img [^>]*>", expand, text)
    text = re.sub(r"<img [^>]*>", html_img_to_md, text)
    text = swap_svg_refs(text)
    text = text.replace("./assets/", "/assets/")

    typst_body = to_typst(text)
    TYP_OUT.write_text(PREAMBLE + typst_body)

    subprocess.run(
        ["typst", "compile", "--root", str(ROOT), str(TYP_OUT), str(PDF_OUT)],
        check=True,
    )
    print(f"wrote {PDF_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
