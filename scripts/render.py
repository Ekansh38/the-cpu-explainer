#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "pdf" / "article.pdf.md"
FRAMES = ROOT / "assets" / "frames"
RASTER = ROOT / "pdf" / ".raster"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RASTER_WIDTH = 1800

LINE_GRAY = "#555555"
TEXT_BLACK = "#000000"
RASTER_GRAY = "#444444"

DARK_PREAMBLE = """\
#set page(paper: "a4", fill: rgb("#111111"), margin: (x: 24mm, y: 22mm))
#set text(fill: rgb("#e6e6e6"), size: 11pt)
#show heading.where(level: 1): it => block(below: 2.5em)[
  #set text(size: 26pt, weight: "bold")
  #it
]
#show heading.where(level: 2): it => block(above: 2.6em, below: 1em)[
  #set text(size: 18pt, weight: "bold")
  #it
  #v(0.2em)
  #line(length: 100%, stroke: 0.5pt + rgb("#333333"))
]
#show heading.where(level: 3): it => block(above: 1.8em, below: 0.6em)[
  #set text(size: 13pt, weight: "bold")
  #it
]

"""

LIGHT_PREAMBLE = """\
#set page(paper: "a4", fill: rgb("#ffffff"), margin: (x: 24mm, y: 22mm))
#set text(fill: rgb("#111111"), size: 11pt)
#show heading.where(level: 1): it => block(below: 2.5em)[
  #set text(size: 26pt, weight: "bold")
  #it
]
#show heading.where(level: 2): it => block(above: 2.6em, below: 1em)[
  #set text(size: 18pt, weight: "bold")
  #it
  #v(0.2em)
  #line(length: 100%, stroke: 0.5pt + rgb("#cccccc"))
]
#show heading.where(level: 3): it => block(above: 1.8em, below: 0.6em)[
  #set text(size: 13pt, weight: "bold")
  #it
]

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


def swap_near_white(text, target_hex):
    target_no_hash = target_hex.lstrip("#")
    tr = int(target_no_hash[0:2], 16)
    tg = int(target_no_hash[2:4], 16)
    tb = int(target_no_hash[4:6], 16)

    def rgb_sub(m):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if r >= 240 and g >= 240 and b >= 240:
            return f"rgb({tr}, {tg}, {tb})"
        return m.group(0)

    def hex_sub(m):
        h = m.group(1)
        if len(h) == 3:
            h = h[0] * 2 + h[1] * 2 + h[2] * 2
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if r >= 240 and g >= 240 and b >= 240:
            return target_hex
        return m.group(0)

    text = re.sub(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", rgb_sub, text)
    text = re.sub(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])", hex_sub, text)
    text = re.sub(r"\bwhite\b", target_hex, text)
    return text


def strip_text_shadow(text):
    return re.sub(r"text-shadow:[^;]*;", "text-shadow: none;", text)


def transform_svg_light(svg_text):
    text_block = re.compile(
        r"(<foreignObject[^>]*>.*?</foreignObject>|<text[^>]*>.*?</text>)",
        flags=re.DOTALL,
    )
    parts = text_block.split(svg_text)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            part = swap_near_white(part, TEXT_BLACK)
            part = strip_text_shadow(part)
        else:
            part = swap_near_white(part, LINE_GRAY)
        out.append(part)
    return "".join(out)


def svg_aspect(svg_path):
    text = svg_path.read_text()
    m = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"', text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'width="([\d.]+)"[^>]*height="([\d.]+)"', text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 800.0, 600.0


def rasterize_svg(svg_path, mode):
    out_dir = RASTER / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (svg_path.stem + ".png")
    if out.exists() and out.stat().st_mtime >= svg_path.stat().st_mtime:
        return out

    svg_text = svg_path.read_text()
    if mode == "light":
        svg_text = transform_svg_light(svg_text)

    processed = out_dir / f".{svg_path.stem}.svg"
    processed.write_text(svg_text)

    w, h = svg_aspect(processed)
    px_w = RASTER_WIDTH
    px_h = max(1, int(px_w * h / w))

    wrapper = out_dir / f".{svg_path.stem}.html"
    wrapper.write_text(
        f'<html><head><style>html,body{{margin:0;background:transparent}}'
        f'img{{width:{px_w}px;height:{px_h}px;display:block}}</style></head>'
        f'<body><img src="{processed.as_uri()}"></body></html>'
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
    processed.unlink()
    return out


def recolor_raster(raster_path):
    out_dir = RASTER / "light"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / raster_path.name
    if out.exists() and out.stat().st_mtime >= raster_path.stat().st_mtime:
        return out
    subprocess.run([
        "magick", str(raster_path),
        "-fuzz", "15%", "-fill", RASTER_GRAY, "-opaque", "white",
        "-fuzz", "15%", "-fill", "#ffffff00", "-opaque", "#101011",
        str(out),
    ], check=True)
    return out


def resolve_asset(src, mode):
    rel = src.lstrip("/").removeprefix("./")
    abs_src = (ROOT / rel).resolve()
    if not abs_src.exists():
        return None
    if abs_src.suffix.lower() == ".svg":
        return rasterize_svg(abs_src, mode)
    if mode == "light":
        return recolor_raster(abs_src)
    return abs_src


def swap_image_refs(text, mode):
    def sub(m):
        alt, src = m.group(1), m.group(2)
        target = resolve_asset(src, mode)
        if target is None:
            return m.group(0)
        rel = "/" + str(target.relative_to(ROOT))
        return f"![{alt}]({rel})"
    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", sub, text)


def to_typst(md_text):
    result = subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "typst"],
        input=md_text, text=True, capture_output=True, check=True,
    )
    return result.stdout


def build(mode):
    text = SRC.read_text()
    text = strip_frontmatter(text)
    text = re.sub(r'<a id="[^"]*"></a>\s*', "", text)
    text = re.sub(r"\[([^\]]+)\]\(#[^)]+\)", r"\1", text)
    text = re.sub(r"<img [^>]*>", expand, text)
    text = re.sub(r"<img [^>]*>", html_img_to_md, text)
    text = swap_image_refs(text, mode)

    typst_body = to_typst(text)
    preamble = DARK_PREAMBLE if mode == "dark" else LIGHT_PREAMBLE
    typ_path = ROOT / "pdf" / f"article-{mode}.typ"
    typ_path.write_text(preamble + typst_body)

    pdf_path = ROOT / "pdf" / f"the-cpu-explainer-{mode}.pdf"
    subprocess.run(
        ["typst", "compile", "--root", str(ROOT), str(typ_path), str(pdf_path)],
        check=True,
    )
    print(f"wrote {pdf_path.relative_to(ROOT)}")


def main():
    if not SRC.exists():
        print(f"{SRC} not found. run prepare.py first.", file=sys.stderr)
        sys.exit(1)
    build("dark")
    build("light")


if __name__ == "__main__":
    main()
