#!/usr/bin/env python3
"""Regenerate review-data.json from debug/captures/ screenshots."""
import json, os, sys, base64, glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sidecar"))

import re
import cv2
from detect_cards import detect_cards, crop_region
from match_traits import load_atlas, match_trait_row, build_neg_map, _icon_shape

_STAR_SUFFIX = re.compile(r'_s[123]$')

PROJ = os.path.join(os.path.dirname(__file__), "..")
ATLAS_DIR = os.path.join(PROJ, "assets", "atlas")
TRAITS_JSON = os.path.join(PROJ, "assets", "traits.json")
CAPTURES_DIR = os.path.join(PROJ, "debug", "captures")

with open(TRAITS_JSON, encoding="utf-8") as f:
    traits_db = json.load(f)

# --- Build name_lookup with group labels for shared icon_names -----------
# Many traits share the same icon_name (same visual icon). For the review UI
# we show a generic category label instead of an arbitrary specific trait name.

_XIHAO_TOPIC = {
    "ChouYan": "Tobacco", "DongWu": "Animals", "HeJiu": "Drinking",
    "JingRui": "Leaders", "PaiXie": "Hobbies", "RenDuo": "Communal living",
    "RouShi": "Meat", "ShuiMian": "Sleep", "ShuiYu": "Water",
    "SuShi": "Fruits & veg", "TiaoWu": "Dancing", "WenDu": "Temperature",
    "WuQi": "Weapons / Personality", "ZhuShi": "Staple food",
    "ZhuangBei": "Equipment", "faqie": "Tomatoes", "qingtian": "Sunny days",
    "xiaxue": "Snow", "xiayu": "Rain", "xizao": "Baths",
}
_BULUO_CLAN = {
    "DuYa": "Fang", "HuangLang": "Wildwolf", "HuoShi": "Flint",
    "LiZhua": "Clawfang", "ManJiao": "Savagehorn",
    "liufangzhe": "Outcast",
}

def _build_group_label(icon_name: str) -> str | None:
    """Return a generic label for icon_names shared by multiple traits, or None."""
    # Preference traits: Icon_NG_XiHao_<Topic>[_2]
    m = re.match(r'Icon_NG_XiHao_(.+?)(-)?(_2)?$', icon_name)
    if m:
        topic_key = m.group(1)
        is_neg = m.group(3) == '_2'
        topic = _XIHAO_TOPIC.get(topic_key)
        if topic:
            return f"Dislikes ({topic})" if is_neg else f"Likes ({topic})"
    # Tribe-born traits: Icon_NG_BuLuo_<Clan>
    m = re.match(r'Icon_NG_BuLuo_(.+)$', icon_name)
    if m:
        clan = _BULUO_CLAN.get(m.group(1))
        if clan:
            return f"Tribe ({clan})"
    # Origin poor survival: chushen_shengcun_2
    if icon_name == 'chushen_shengcun_2':
        return "Origin: Poor Survival"
    return None

# Count distinct names per icon_name to detect shared icons
from collections import defaultdict as _defaultdict
_icon_name_counts: dict[str, int] = {}
_icon_names_seen: _defaultdict[str, set[str]] = _defaultdict(set)
for t in traits_db:
    icon = t.get("icon_name")
    name = t.get("name_en") or t.get("name", "")
    if icon and name:
        _icon_names_seen[icon].add(name)
_icon_name_counts = {k: len(v) for k, v in _icon_names_seen.items()}

name_lookup = {}
for t in traits_db:
    icon = t.get("icon_name")
    if icon and icon not in name_lookup:
        if _icon_name_counts.get(icon, 0) > 1:
            label = _build_group_label(icon)
            if label:
                name_lookup[icon] = label
                continue
        name_lookup[icon] = t.get("name_en") or t.get("name", icon)

atlas = load_atlas(ATLAS_DIR)
neg_map = build_neg_map(TRAITS_JSON)

shape_map = {
    "hexagon": "hex",
    "diamond": "other",
    "shield": "shield",
    "shield_alt": "shield",
}

captures = sorted(glob.glob(os.path.join(CAPTURES_DIR, "capture_*.png")))
print(f"Found {len(captures)} captures, atlas has {len(atlas)} entries")

all_data = []
for cap_path in captures:
    cap_name = os.path.splitext(os.path.basename(cap_path))[0]
    img = cv2.imread(cap_path)
    if img is None:
        print(f"  SKIP {cap_name}: cannot read")
        continue

    cards = detect_cards(img)
    print(f"  {cap_name}: {len(cards)} cards")

    tribesmen = []
    for ci, card in enumerate(cards):
        card_img = card.crop(img)
        _, card_buf = cv2.imencode(".png", card_img)
        card_b64 = base64.b64encode(card_buf).decode("ascii")

        try:
            from ocr_llm import extract_cards_llm
            texts = extract_cards_llm([card_img])
            text = texts[0] if texts else None
        except Exception:
            text = None

        try:
            trait_row = crop_region(card_img, "trait_row")
            matches = match_trait_row(trait_row, atlas, neg_map=neg_map)
        except Exception as e:
            print(f"    Card {ci}: match error: {e}")
            matches = []

        traits_out = []
        for m in matches:
            x, y, w, h = m.bbox
            crop = trait_row[y:y+h, x:x+w]
            crop_b64 = ""
            if crop.size > 0:
                _, buf = cv2.imencode(".png", crop)
                crop_b64 = base64.b64encode(buf).decode("ascii")

            base_name = _STAR_SUFFIX.sub('', m.icon_name)
            selected_name = name_lookup.get(base_name, base_name)

            shape_raw = _icon_shape(base_name)
            shape = shape_map.get(shape_raw, shape_raw)

            candidates = []
            all_alts = [(m.icon_name, m.confidence)] + list(m.alternatives)
            for alt_name, alt_conf in all_alts[:5]:
                alt_base = _STAR_SUFFIX.sub('', alt_name)
                candidates.append({
                    "icon_name": alt_name,
                    "name": name_lookup.get(alt_base, alt_base),
                    "confidence": round(alt_conf, 3),
                })

            traits_out.append({
                "shape": shape,
                "selected": m.icon_name,
                "selected_name": selected_name,
                "confidence": round(m.confidence, 3),
                "crop_b64": crop_b64,
                "candidates": candidates,
            })

        tm_data = {
            "name": text.name if text else f"Card {ci}",
            "level": text.level if text else None,
            "class": text.class_name if text else None,
            "clan": text.clan if text else None,
            "status": text.status if text else None,
            "group": text.group if text else None,
            "card_b64": card_b64,
            "traits": traits_out,
        }
        tribesmen.append(tm_data)

    all_data.append({
        "capture": cap_name,
        "file": cap_path,
        "cards_found": len(cards),
        "tribesmen": tribesmen,
    })

out_path = os.path.join(os.path.dirname(__file__), "review-data.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False)

total_tm = sum(len(c["tribesmen"]) for c in all_data)
total_tr = sum(len(t["traits"]) for c in all_data for t in c["tribesmen"])
print(f"\nWrote {out_path}: {len(all_data)} captures, {total_tm} tribesmen, {total_tr} traits")
