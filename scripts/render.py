#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "pdf" / "article.pdf.md"
FRAMES = ROOT / "assets" / "frames"
TYP_OUT = ROOT / "pdf" / "article.typ"
PDF_OUT = ROOT / "pdf" / "the-cpu-explainer.pdf"


PREAMBLE = """\
#set page(
  paper: "a4",
  fill: rgb("#111111"),
  margin: (x: 24mm, y: 22mm),
)
#set text(
  font: ("Charter", "New York", "Georgia"),
  size: 11pt,
  fill: rgb("#e6e6e6"),
)
#set par(leading: 0.7em, spacing: 1.1em, justify: false)
#show heading.where(level: 1): set text(size: 22pt, weight: "bold")
#show heading.where(level: 2): set text(size: 16pt, weight: "bold")
#show heading.where(level: 3): set text(size: 13pt, weight: "bold")
#show heading: it => block(above: 1.8em, below: 0.6em, it)
#show link: set text(fill: rgb("#e6e6e6"))
#show raw.where(block: true): block.with(
  fill: rgb("#1a1a1a"),
  inset: 12pt,
  radius: 4pt,
  width: 100%,
)
#show raw: set text(font: "Menlo")
#show image: it => align(center, block(above: 1.2em, below: 1.2em, it))

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
