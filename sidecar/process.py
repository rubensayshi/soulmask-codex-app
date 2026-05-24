#!/usr/bin/env python3
"""Main entry: image path -> JSON stdout. Called by Tauri as a sidecar."""
import json, sys, os, argparse, traceback, base64
import cv2


def process_image(image_path: str, atlas_dir: str) -> dict:
    from detect_cards import detect_cards, crop_region
    from ocr_text import extract_card_text
    from match_traits import load_atlas, match_trait_row, build_neg_map

    img = cv2.imread(image_path)
    if img is None:
        return {"error": f"Cannot read image: {image_path}", "tribesmen": []}

    atlas = load_atlas(atlas_dir) if os.path.isdir(atlas_dir) else {}
    neg_map = build_neg_map(os.path.join(os.path.dirname(atlas_dir), "traits.json"))
    cards = detect_cards(img)

    tribesmen = []
    for i, card in enumerate(cards):
        card_img = card.crop(img)
        try:
            text = extract_card_text(card_img)
            trait_row = crop_region(card_img, "trait_row")
            matches = match_trait_row(trait_row, atlas, neg_map=neg_map) if atlas else []
            traits_out = []
            for m in matches:
                t = {
                    "icon_name": m.icon_name,
                    "confidence": round(m.confidence, 3),
                    "alternatives": [
                        {"icon_name": n, "confidence": round(s, 3)}
                        for n, s in m.alternatives
                    ],
                }
                x, y, w, h = m.bbox
                crop = trait_row[y:y+h, x:x+w]
                if crop.size > 0:
                    _, buf = cv2.imencode(".png", crop)
                    t["crop_b64"] = base64.b64encode(buf).decode("ascii")
                traits_out.append(t)
            tribesmen.append({
                "name": text.name,
                "level": text.level,
                "class": text.class_name,
                "clan": text.clan,
                "title": text.title,
                "status": text.status,
                "group": text.group,
                "traits": traits_out,
                "card_index": i,
            })
        except Exception as e:
            tribesmen.append({
                "name": f"[Card {i} error]",
                "error": str(e),
                "card_index": i,
                "traits": [],
            })

    tribesmen = [t for t in tribesmen if _is_valid_tribesman(t)]
    return {"tribesmen": tribesmen, "cards_found": len(cards)}


def _is_valid_tribesman(t: dict) -> bool:
    """Reject OCR garbage from partially visible or corrupt cards."""
    name = t.get("name") or ""
    if name.startswith("[Card"):
        return False
    clean_name = name.replace("_", "").replace("-", "").strip()
    if len(clean_name) < 3:
        return False
    has_level = t.get("level") is not None
    has_class = bool(t.get("class"))
    has_traits = len(t.get("traits", [])) >= 2
    score = int(has_level) + int(has_class) + int(has_traits)
    return score >= 2


def process_images(image_paths: list[str], atlas_dir: str) -> dict:
    """Process multiple screenshots and merge overlapping tribesmen."""
    from merge import match_and_merge

    per_image = []
    total_cards = 0
    for path in image_paths:
        result = process_image(path, atlas_dir)
        per_image.append(result.get("tribesmen", []))
        total_cards += result.get("cards_found", 0)

    merged = match_and_merge(per_image)
    return {
        "tribesmen": merged,
        "cards_found": total_cards,
        "images_processed": len(image_paths),
        "unique_tribesmen": len(merged),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", nargs="+", help="Path(s) to screenshot image(s)")
    parser.add_argument("--atlas", default=os.path.join(os.path.dirname(__file__), "..", "assets", "atlas"))
    args = parser.parse_args()

    missing = [p for p in args.image if not os.path.exists(p)]
    if missing:
        print(json.dumps({"error": f"File(s) not found: {missing}", "tribesmen": []}))
        sys.exit(1)

    try:
        if len(args.image) == 1:
            result = process_image(args.image[0], args.atlas)
        else:
            result = process_images(args.image, args.atlas)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e), "traceback": traceback.format_exc(), "tribesmen": []}))
        sys.exit(1)


if __name__ == "__main__":
    main()
