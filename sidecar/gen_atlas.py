"""Generate reference atlas: composite each trait icon onto its game badge shape."""
import json, os
from PIL import Image

SHAPES_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "shapes")
ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")

SHAPE_FILES = {
    ("hexagon", False):    "hexagon.png",
    ("hexagon", True):     "hexagon_inactive.png",
    ("diamond", False):    "diamond.png",
    ("diamond", True):     "diamond_inactive.png",
    ("shield", False):     "shield.png",
    ("shield", True):      "shield_inactive.png",
    ("shield_alt", False): "shield_alt.png",
    ("shield_alt", True):  "shield_alt_inactive.png",
}

ICON_SCALE = {
    "hexagon": 0.86,
    "diamond": 0.80,
    "shield": 0.86,
    "shield_alt": 0.80,
}

# Compensate for shape files having more padding than game renders.
# Measured: captured shield fills 94% but atlas fills 90.6%, hex 100% vs 85.9%.
BADGE_SCALE = {
    "hexagon": 1.01,
    "diamond": 1.05,
    "shield": 1.06,
    "shield_alt": 1.06,
}

# Nudge (px) applied when center-cropping badge to final size.
# X: positive = shift content left. Y: positive = shift content up.
CONTENT_NUDGE_X = {
    "shield": 1,
    "shield_alt": 2,
    "diamond": 1,
}
CONTENT_NUDGE_Y = {
    "shield": -2,
    "hexagon": -1,
}

# Vertical nudge for the inner icon within the badge (before crop).
# Negative = move icon up.
ICON_NUDGE_Y = {
    "hexagon": -3,
    "diamond": -3,
    "shield": -5,
    "shield_alt": -3,
}


SOURCE_TO_FOLDER = {
    "Normal": "TianFu",
    "XiHao": "xihao",
    "XingGe": "xihao",
    "ChengHao": "ChengHao",
    "BornBuLuoCiTiao": "BuLuo",
    "JingLi": "BuLuo",
    "BornChuShen": "ChuShen",
}


def source_to_badge_shape(source: str) -> str:
    if source == "Normal":
        return "hexagon"
    if source in ("XiHao", "XingGe"):
        return "diamond"
    if source == "BornBuLuoCiTiao":
        return "shield"
    return "shield_alt"


def _crop_to_content(img: Image.Image, threshold: int = 20) -> Image.Image:
    """Crop RGBA image to visible content, pad to square with equal margins."""
    import numpy as np
    arr = np.array(img)
    mask = arr[:, :, 3] > threshold
    if not mask.any():
        return img
    ys, xs = np.where(mask)
    x1, y1, x2, y2 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    cropped = img.crop((x1, y1, x2, y2))
    w, h = cropped.size
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(cropped, ((side - w) // 2, (side - h) // 2))
    return square


def composite_icon(icon_path: str, shape: str, negative: bool, size: int,
                   star: int = 0) -> Image.Image:
    shape_file = SHAPE_FILES[(shape, negative)]
    badge = Image.open(os.path.join(SHAPES_DIR, shape_file)).convert("RGBA")
    badge = _crop_to_content(badge)
    bscale = BADGE_SCALE.get(shape, 1.0)
    badge_size = int(size * bscale)
    badge = badge.resize((badge_size, badge_size), Image.LANCZOS)

    icon = Image.open(icon_path).convert("RGBA")
    scale = ICON_SCALE.get(shape, 0.85)
    icon_size = int(badge_size * scale)
    icon = icon.resize((icon_size, icon_size), Image.LANCZOS)
    offset = (badge_size - icon_size) // 2
    iy = ICON_NUDGE_Y.get(shape, 0)
    badge.paste(icon, (offset, offset + iy), icon)

    if 1 <= star <= 3:
        star_img = Image.open(os.path.join(SHAPES_DIR, f"star_{star}.png")).convert("RGBA")
        sw, sh = star_img.size
        star_scale = badge_size / 64.0
        new_sw = max(int(sw * star_scale), 1)
        new_sh = max(int(sh * star_scale), 1)
        star_img = star_img.resize((new_sw, new_sh), Image.LANCZOS)
        sx = (badge_size - new_sw) // 2
        sy = badge_size - new_sh - max(int(badge_size * 0.03), 1)
        badge.paste(star_img, (sx, sy), star_img)

    nx = CONTENT_NUDGE_X.get(shape, 0)
    ny = CONTENT_NUDGE_Y.get(shape, 0)
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    if badge_size >= size:
        margin = (badge_size - size) // 2
        badge = badge.crop((margin + nx, margin + ny, margin + nx + size, margin + ny + size))
        bg.paste(badge, (0, 0), badge)
    else:
        pad = (size - badge_size) // 2
        bg.paste(badge, (pad - nx, pad - ny), badge)
    return bg.convert("RGB")


def _find_icon(icon_name: str, source: str) -> str | None:
    folder = SOURCE_TO_FOLDER.get(source)
    if folder:
        path = os.path.join(ICONS_DIR, folder, icon_name + ".png")
        if os.path.exists(path):
            return path
    for folder in os.listdir(ICONS_DIR):
        path = os.path.join(ICONS_DIR, folder, icon_name + ".png")
        if os.path.exists(path):
            return path
    return None


def build_atlas(traits_path: str, out_dir: str, size: int = 64,
                star_variants: bool = False) -> dict:
    with open(traits_path, encoding='utf-8') as f:
        traits = json.load(f)

    if star_variants:
        entries: list[tuple[str, str, bool, int]] = []
        seen: set[tuple[str, int]] = set()
        for t in traits:
            name = t.get("icon_name")
            if not name:
                continue
            star = t.get("star", 1)
            key = (name, star)
            if key in seen:
                continue
            seen.add(key)
            entries.append((name, t["source"], t.get("is_negative", False), star))
    else:
        icon_meta: dict[str, dict] = {}
        for t in traits:
            name = t.get("icon_name")
            if not name or name in icon_meta:
                continue
            icon_meta[name] = {
                "source": t["source"],
                "negative": t.get("is_negative", False),
            }
        entries = [(n, m["source"], m["negative"], 0) for n, m in icon_meta.items()]

    os.makedirs(out_dir, exist_ok=True)
    generated = 0
    missing = 0
    for icon_name, source, negative, star in entries:
        icon_path = _find_icon(icon_name, source)
        if not icon_path:
            missing += 1
            continue
        shape = source_to_badge_shape(source)
        img = composite_icon(icon_path, shape, negative, size, star)
        suffix = f"_s{star}" if star_variants else ""
        img.save(os.path.join(out_dir, f"{icon_name}{suffix}.png"))
        generated += 1

    return {"generated": generated, "missing": missing, "total": len(entries)}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--traits", default=os.path.join(os.path.dirname(__file__), "..", "assets", "traits.json"))
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "assets", "atlas"))
    p.add_argument("--size", type=int, default=64)
    p.add_argument("--clean", action="store_true", help="Remove existing atlas PNGs before generating")
    p.add_argument("--stars", action="store_true", help="Generate per-star-level variants")
    args = p.parse_args()

    if args.clean and os.path.isdir(args.out):
        import glob
        for f in glob.glob(os.path.join(args.out, "*.png")):
            os.remove(f)
        print(f"Cleaned {args.out}")

    stats = build_atlas(args.traits, args.out, args.size, star_variants=args.stars)
    print(f"Atlas: {stats['generated']} generated, {stats['missing']} missing icons, {stats['total']} total")
