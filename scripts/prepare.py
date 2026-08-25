#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLE = ROOT / "article.md"
FRAMES = ROOT / "assets" / "frames"
OUT = ROOT / "pdf" / "article.pdf.md"


def has_frames(stem):
    return any(FRAMES.glob(f"{stem}-*.png"))


def annotate(match):
    tag = match.group(0)
    if "pdf-frames=" in tag:
        return tag
    stem = re.search(r'src="\./assets/final/([^"]+)\.gif"', tag).group(1)
    default = "last" if has_frames(stem) else "keep"
    return tag.replace("<img ", f'<img pdf-frames="{default}" ', 1)


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT} exists. re-run with --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    text = ARTICLE.read_text()
    pattern = re.compile(r'<img [^>]*src="\./assets/final/[^"]+\.gif"[^>]*>')
    text = pattern.sub(annotate, text)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
