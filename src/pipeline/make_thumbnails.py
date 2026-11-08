"""
Pre-generate small, uniformly cropped card thumbnails from the full-size plant
photos in data/processed/images/.

They are written into the Streamlit app's static directory so the browser can
fetch and cache them as ordinary files (served at /app/static/...), instead of
the page re-sending image bytes inline on every rerun. Cropping to a fixed 4:3
ratio here also means the gallery grid stays even regardless of the original
photo's aspect ratio.

Output: src/app/static/plant_thumbs/<slug>.jpg
"""
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "data" / "processed" / "images"
OUT_DIR = ROOT / "src" / "app" / "static" / "plant_thumbs"
SIZE = (360, 270)  # 4:3, ~2x the rendered card size
QUALITY = 78


def main():
    if not SRC_DIR.exists():
        print(f"No source directory at {SRC_DIR} -- run fetch_plant_images.py first.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in SRC_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    print(f"Found {len(sources)} source images")

    written, failed = 0, 0
    for path in sources:
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                # cover-crop to the card aspect ratio, then downscale
                thumb = ImageOps.fit(img.convert("RGB"), SIZE, method=Image.LANCZOS, centering=(0.5, 0.45))
                thumb.save(OUT_DIR / f"{path.stem}.jpg", "JPEG", quality=QUALITY, optimize=True, progressive=True)
            written += 1
        except OSError as e:
            print(f"  skipped {path.name}: {e}")
            failed += 1

    total_kb = sum(p.stat().st_size for p in OUT_DIR.iterdir()) / 1024
    print(f"Wrote {written} thumbnails ({failed} failed) -- {total_kb:.0f} KB total in {OUT_DIR}")
    print(f"Average {total_kb / max(written, 1):.1f} KB per thumbnail")


if __name__ == "__main__":
    main()
