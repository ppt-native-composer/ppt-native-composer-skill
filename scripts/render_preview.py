#!/usr/bin/env python3
"""Render a PPTX to PDF and a contact-sheet preview using local office tools."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def make_contact_sheet(image_paths: list[Path], output: Path, cols: int = 2) -> None:
    if not image_paths:
        raise RuntimeError("No preview images were generated.")
    thumbs = []
    for img_path in image_paths:
        im = Image.open(img_path).convert("RGB")
        im.thumbnail((520, 292))
        canvas = Image.new("RGB", (560, 340), "white")
        canvas.paste(im, ((560 - im.width) // 2, 20))
        ImageDraw.Draw(canvas).text((20, 315), img_path.stem, fill=(0, 0, 0))
        thumbs.append(canvas)
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (560 * cols, 340 * rows), (235, 235, 235))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * 560, (i // cols) * 340))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", help="Path to PPTX.")
    parser.add_argument("--outdir", required=True, help="Output preview directory.")
    parser.add_argument("--dpi", type=int, default=120, help="PDF to PNG render DPI.")
    parser.add_argument("--cols", type=int, default=2, help="Contact sheet columns.")
    args = parser.parse_args()

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdftoppm = shutil.which("pdftoppm")
    if not soffice:
        raise SystemExit("Missing soffice/libreoffice on PATH.")
    if not pdftoppm:
        raise SystemExit("Missing pdftoppm on PATH.")

    pptx = Path(args.pptx).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*"):
        if old.is_file():
            old.unlink()

    run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(pptx)])
    pdf = outdir / f"{pptx.stem}.pdf"
    if not pdf.exists():
        matches = sorted(outdir.glob("*.pdf"))
        if not matches:
            raise RuntimeError("PDF conversion did not produce a file.")
        pdf = matches[0]

    run([pdftoppm, "-png", "-r", str(args.dpi), str(pdf), str(outdir / "page")])
    pages = sorted(outdir.glob("page-*.png"))
    contact = outdir / "contact-sheet.png"
    make_contact_sheet(pages, contact, cols=args.cols)
    print(f"PDF: {pdf}")
    print(f"Pages: {len(pages)}")
    print(f"Contact sheet: {contact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
