"""Stage 3-4: Extract trait icons from card row and match against reference atlas."""
import json
import os
import cv2
import numpy as np
from dataclasses import dataclass, field


@dataclass
class TraitMatch:
    icon_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h within the icon row
    alternatives: list[tuple[str, float]] = field(default_factory=list)


CONFIDENCE_THRESHOLD = 0.62
NONHEX_CONFIDENCE_THRESHOLD = 0.55
_COLOR_TO_SHAPE = {"green": "hexagon", "gold": "shield", "purple": "diamond"}

import re
_STAR_SUFFIX = re.compile(r'_s[123]$')
_VARIANT_SUFFIX = re.compile(r'_(\d+)$')

def _normalize_icon_name(name: str) -> str:
    """Strip atlas variant suffixes (_s1/_s2/_s3 star, _2/_3 dedup)."""
    name = _STAR_SUFFIX.sub('', name)
    m = _VARIANT_SUFFIX.search(name)
    if not m:
        return name
    base = name[:m.start()]
    if base.startswith("tianfu_") or base.startswith("ChengHao_") or base.startswith("Icon_NG_"):
        return base
    return name


def _normalize_ranked(ranked: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Normalize icon names and dedup, keeping highest score per base name."""
    seen: dict[str, float] = {}
    for name, score in ranked:
        base = _normalize_icon_name(name)
        if base not in seen or score > seen[base]:
            seen[base] = score
    return sorted(seen.items(), key=lambda x: x[1], reverse=True)


def _icon_shape(name: str) -> str:
    if name.startswith("Icon_NG_XiHao") or name.startswith("Icon_NG_XingGe"):
        return "diamond"
    if name.startswith("Icon_NG_BuLuo") or name.startswith("ChengHao") or name.startswith("Icon_NG_JingLi") or name.startswith("chushen_"):
        return "shield"
    return "hexagon"


def _classify_border_color(icon_bgr: np.ndarray) -> tuple[str, float]:
    """Classify an icon's border color to determine trait shape.

    Returns (color, saturation) where color is 'green' (hex), 'gold' (shield),
    'purple' (diamond), 'red' (negative/any shape), or 'unknown'.
    """
    h_px, w_px = icon_bgr.shape[:2]
    hsv = cv2.cvtColor(icon_bgr, cv2.COLOR_BGR2HSV)
    border = int(max(2, min(h_px, w_px) * 0.25))
    mask = np.zeros((h_px, w_px), dtype=np.uint8)
    cv2.rectangle(mask, (0, 0), (w_px - 1, h_px - 1), 255, border)
    bright = (mask > 0) & (hsv[:, :, 2] > 100)
    if bright.sum() < 10:
        bright = (mask > 0) & (hsv[:, :, 2] > 80)
    if bright.sum() < 10:
        bright = (mask > 0) & (hsv[:, :, 2] > 40)
    if bright.sum() < 10:
        return "unknown", 0.0
    hues = hsv[:, :, 0][bright]
    sats = hsv[:, :, 1][bright]
    h_med = float(np.median(hues))
    s_med = float(np.median(sats))
    if s_med < 20:
        return "unknown", s_med
    if (h_med < 8 or h_med > 168) and s_med > 60:
        return "red", s_med
    if 8 <= h_med < 30:
        return "gold", s_med
    if 30 <= h_med < 95:
        return "green", s_med
    if 95 <= h_med < 160:
        return "purple", s_med
    return "unknown", s_med


def _crop_interior(img: np.ndarray, margin_frac: float = 0.20) -> np.ndarray:
    """Crop the interior of an icon, removing the border ring."""
    h, w = img.shape[:2]
    m = int(min(h, w) * margin_frac)
    return img[m:h - m, m:w - m]


def load_atlas(atlas_dir: str, size: int | None = None) -> dict[str, np.ndarray]:
    atlas = {}
    for fname in os.listdir(atlas_dir):
        if not fname.endswith(".png"):
            continue
        name = os.path.splitext(fname)[0]
        img = cv2.imread(os.path.join(atlas_dir, fname), cv2.IMREAD_COLOR)
        if img is None:
            continue
        if size and (img.shape[0] != size or img.shape[1] != size):
            img = cv2.resize(img, (size, size))
        atlas[name] = img
    return atlas


def build_neg_map(traits_json_path: str) -> dict[str, str]:
    """Build mapping from positive base icon_name -> negative _2 icon_name."""
    try:
        with open(traits_json_path, encoding='utf-8') as f:
            traits = json.load(f)
        neg = {}
        for t in traits:
            iname = t.get("icon_name", "")
            if t.get("is_negative") and iname.endswith("_2"):
                neg[iname[:-2]] = iname
        return neg
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


@dataclass
class ShapedAtlas:
    full: dict[str, dict[str, np.ndarray]]
    cropped: dict[str, dict[str, np.ndarray]]
    red: dict[str, dict[str, np.ndarray]]
    neg_map: dict[str, str] = field(default_factory=dict)


def split_atlas_by_shape(atlas: dict[str, np.ndarray], neg_map: dict[str, str] | None = None) -> ShapedAtlas:
    full: dict[str, dict[str, np.ndarray]] = {"hexagon": {}, "diamond": {}, "shield": {}}
    cropped: dict[str, dict[str, np.ndarray]] = {"hexagon": {}, "diamond": {}, "shield": {}}
    red: dict[str, dict[str, np.ndarray]] = {"hexagon": {}, "diamond": {}, "shield": {}}
    neg_names = set(neg_map.values()) if neg_map else set()
    for name, img in atlas.items():
        base = _STAR_SUFFIX.sub('', name)
        if base in neg_names:
            shape = _icon_shape(base)
            red[shape][name] = img
            continue
        shape = _icon_shape(base)
        full[shape][name] = img
        cropped[shape][name] = _crop_interior(img)
    return ShapedAtlas(full=full, cropped=cropped, red=red, neg_map=neg_map or {})


MAX_TRAIT_SLOTS = 16


def _find_grid_anchors(gray: np.ndarray) -> list[tuple[int, int, int]]:
    """Find a few bright icons to establish grid pitch and y-center."""
    h, w = gray.shape
    min_side = min(max(int(h * 0.35), 16), 28)
    max_side = max(int(h * 0.85), 40)
    candidates: list[tuple[int, int, int]] = []
    for thresh in range(25, 90, 15):
        _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw < min_side or bh < min_side or bw > max_side or bh > max_side:
                continue
            if max(bw, bh) / max(min(bw, bh), 1) > 1.8:
                continue
            side = max(bw, bh)
            candidates.append((bx + bw // 2, by + bh // 2, side))
    if not candidates:
        return []
    candidates.sort(key=lambda c: c[0])
    merged: list[tuple[int, int, int]] = []
    used = [False] * len(candidates)
    for i, (cx, cy, s) in enumerate(candidates):
        if used[i]:
            continue
        grp_cx, grp_cy, grp_s = [cx], [cy], [s]
        used[i] = True
        for j in range(i + 1, len(candidates)):
            if used[j]:
                continue
            if abs(candidates[j][0] - cx) < s * 0.5 and abs(candidates[j][1] - cy) < s * 0.5:
                grp_cx.append(candidates[j][0])
                grp_cy.append(candidates[j][1])
                grp_s.append(candidates[j][2])
                used[j] = True
        merged.append((int(np.mean(grp_cx)), int(np.mean(grp_cy)), int(np.median(grp_s))))
    if len(merged) >= 3:
        sizes = sorted(m[2] for m in merged)
        med = sizes[len(sizes) // 2]
        merged = [m for m in merged if med * 0.5 <= m[2] <= med * 1.6]
    return merged


def segment_icons(trait_row: np.ndarray, expected_size: int = 64) -> list[tuple[np.ndarray, int, int]]:
    """Slice 16 fixed-pitch boxes from the trait icon row.

    Detects a few bright anchor icons to establish grid pitch and vertical
    center, then extrapolates all 16 possible slot positions. Faster and
    more reliable than threshold-based contour detection — faint icons
    that contour detection misses get sliced at their expected position.
    """
    gray = cv2.cvtColor(trait_row, cv2.COLOR_BGR2GRAY) if len(trait_row.shape) == 3 else trait_row
    h, w = gray.shape
    anchors = _find_grid_anchors(gray)
    if not anchors:
        return []

    sizes = [s for _, _, s in anchors]
    icon_size = int(np.median(sizes))
    cy_med = int(np.median([cy for _, cy, _ in anchors]))

    xs = sorted(a[0] for a in anchors)
    if len(xs) >= 2:
        pitches = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        pitch = int(np.median(pitches))
    else:
        pitch = int(icon_size * 1.08)
    pitch = max(pitch, icon_size + 1)

    first_cx = xs[0]

    half = icon_size // 2
    icons: list[tuple[np.ndarray, int, int]] = []
    for slot in range(MAX_TRAIT_SLOTS):
        cx = first_cx + slot * pitch
        x1 = cx - half
        x2 = x1 + icon_size
        if x2 > w:
            break
        x1 = max(0, x1)
        y1 = max(0, cy_med - half)
        y2 = min(h, y1 + icon_size)
        crop = trait_row[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        slot_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        if int(slot_gray.max()) < 80:
            continue
        icons.append((crop, x1, y1))

    return icons


def match_icon(icon_img: np.ndarray, atlas: dict[str, np.ndarray]) -> TraitMatch:
    """Match a single icon against the atlas using cross-correlation."""
    best_name = ""
    best_score = -1.0

    target_size = next(iter(atlas.values())).shape[0]
    if icon_img.shape[0] != target_size or icon_img.shape[1] != target_size:
        icon_img = cv2.resize(icon_img, (target_size, target_size))

    for name, ref in atlas.items():
        result = cv2.matchTemplate(icon_img, ref, cv2.TM_CCORR_NORMED)
        score = float(result[0][0])
        if score > best_score:
            best_score = score
            best_name = name

    return TraitMatch(icon_name=best_name, confidence=best_score, bbox=(0, 0, 0, 0))


@dataclass
class _SubsetResult:
    match: TraitMatch
    z_score: float
    ranked: list[tuple[str, float]]  # all (name, score) pairs sorted desc


def _match_icon_scored(icon_img: np.ndarray, atlas: dict[str, np.ndarray]) -> _SubsetResult | None:
    """Match icon against atlas subset and return z-score of best match."""
    if not atlas:
        return None
    target_size = next(iter(atlas.values())).shape[0]
    if icon_img.shape[0] != target_size or icon_img.shape[1] != target_size:
        icon_img = cv2.resize(icon_img, (target_size, target_size))

    name_scores: list[tuple[str, float]] = []
    for name, ref in atlas.items():
        result = cv2.matchTemplate(icon_img, ref, cv2.TM_CCORR_NORMED)
        name_scores.append((name, float(result[0][0])))

    name_scores.sort(key=lambda x: x[1], reverse=True)
    best_name, best_score = name_scores[0]
    scores = [s for _, s in name_scores]

    arr = np.array(scores)
    mean = float(arr.mean())
    std = float(arr.std())
    z = (best_score - mean) / std if std > 1e-6 else 0.0
    n = len(scores)
    expected_max = float(np.sqrt(2.0 * np.log(max(n, 2))))
    z_norm = z / expected_max if expected_max > 0 else z
    m = TraitMatch(icon_name=best_name, confidence=best_score, bbox=(0, 0, 0, 0))
    return _SubsetResult(match=m, z_score=z_norm, ranked=name_scores)


def _assign_zones(icons: list[tuple[np.ndarray, int, int]]) -> list[str]:
    """Assign shape zones using spatial ordering (shield → diamond → hex).

    Game arranges icons left-to-right: shields, then diamonds, then hexes.
    Uses green/purple color anchors to find zone boundaries. Requires at
    least one green or purple anchor to define any boundary; gold-only cards
    fall back to 'unknown' for z-score matching.
    """
    colors = [_classify_border_color(img)[0] for img, _, _ in icons]
    xs = [x for _, x, _ in icons]
    n = len(icons)
    if n == 0:
        return []

    first_green = next((xs[i] for i in range(n) if colors[i] == "green"), None)
    first_purple = next((xs[i] for i in range(n) if colors[i] == "purple"), None)

    has_boundary = first_green is not None or first_purple is not None
    if not has_boundary:
        return ["unknown"] * n

    zones: list[str] = []
    for i in range(n):
        x = xs[i]
        if first_green is not None and x >= first_green:
            zones.append("hexagon")
        elif first_purple is not None and x >= first_purple:
            zones.append("diamond")
        else:
            zones.append("shield")
    return zones


def _top_alts(ranked: list[tuple[str, float]], primary: str, threshold: float,
              taken: dict[str, int], limit: int = 2) -> list[tuple[str, float]]:
    return [(n, s) for n, s in ranked if n != primary and s >= threshold and n not in taken][:limit]


def _dedup_matches(candidates: list) -> list[TraitMatch]:
    """Deduplicate by icon_name: when two icons match the same template,
    the weaker one falls back to its next-best above-threshold match."""
    taken: dict[str, int] = {}
    result: list[TraitMatch] = [c.match for c in candidates]

    for idx, c in enumerate(candidates):
        result[idx].alternatives = _top_alts(c.ranked, c.match.icon_name, c.threshold, taken)

    for idx, c in enumerate(candidates):
        name = c.match.icon_name
        prev_idx = taken.get(name)
        if prev_idx is None:
            taken[name] = idx
            continue
        prev = candidates[prev_idx]
        loser_idx = prev_idx if c.match.confidence > prev.match.confidence else idx
        winner_idx = idx if loser_idx == prev_idx else prev_idx
        taken[name] = winner_idx

        loser = candidates[loser_idx]
        reassigned = False
        for alt_name, alt_score in loser.ranked:
            if alt_name == name:
                continue
            if alt_score < loser.threshold:
                break
            if alt_name not in taken:
                alt_match = TraitMatch(icon_name=alt_name, confidence=alt_score,
                                       bbox=loser.match.bbox,
                                       alternatives=_top_alts(loser.ranked, alt_name, loser.threshold, taken))
                result[loser_idx] = alt_match
                taken[alt_name] = loser_idx
                reassigned = True
                break
        if not reassigned:
            result[loser_idx] = None  # type: ignore

    return [m for m in result if m is not None]


_EDGE_RERANK_MIN_PX = 50
_EDGE_RERANK_MARGIN = 0.95
_SHIELD_CCOEFF_MIN_PX = 64
_SHIELD_CCOEFF_TOP_N = 5
_SHIELD_CCOEFF_SZ = 48


def _ccoeff_rerank_shield(ranked: list[tuple[str, float]], icon_img: np.ndarray,
                          atlas_subset: dict[str, np.ndarray]) -> list[tuple[str, float]]:
    if min(icon_img.shape[:2]) < _SHIELD_CCOEFF_MIN_PX:
        return ranked
    if len(ranked) < 2:
        return ranked
    interior = _crop_interior(icon_img, 0.25)
    gray = cv2.equalizeHist(cv2.cvtColor(interior, cv2.COLOR_BGR2GRAY))
    gray = cv2.resize(gray, (_SHIELD_CCOEFF_SZ, _SHIELD_CCOEFF_SZ))
    scores: list[tuple[str, float]] = []
    for name, _ in ranked[:_SHIELD_CCOEFF_TOP_N]:
        ref = atlas_subset.get(name)
        if ref is None:
            continue
        ref_int = _crop_interior(ref, 0.25)
        ref_gray = cv2.equalizeHist(cv2.cvtColor(ref_int, cv2.COLOR_BGR2GRAY))
        ref_gray = cv2.resize(ref_gray, (_SHIELD_CCOEFF_SZ, _SHIELD_CCOEFF_SZ))
        result = cv2.matchTemplate(gray, ref_gray, cv2.TM_CCOEFF_NORMED)
        scores.append((name, float(result[0][0])))
    if not scores:
        return ranked
    scores.sort(key=lambda x: x[1], reverse=True)
    best_ccoeff = scores[0][0]
    if best_ccoeff != ranked[0][0]:
        ccorr_score = next(s for n, s in ranked if n == best_ccoeff)
        rest = [(n, s) for n, s in ranked if n != best_ccoeff]
        return [(best_ccoeff, ccorr_score)] + rest
    return ranked


def _edge_iou(icon_img: np.ndarray, ref_img: np.ndarray) -> float:
    target = ref_img.shape[0]
    interior_ic = _crop_interior(icon_img, margin_frac=0.25)
    interior_ref = _crop_interior(ref_img, margin_frac=0.25)
    g_ic = cv2.equalizeHist(cv2.cvtColor(interior_ic, cv2.COLOR_BGR2GRAY))
    g_ref = cv2.equalizeHist(cv2.cvtColor(interior_ref, cv2.COLOR_BGR2GRAY))
    g_ic = cv2.resize(g_ic, (target, target))
    g_ref = cv2.resize(g_ref, (target, target))
    k = np.ones((2, 2), np.uint8)
    e_ic = cv2.dilate(cv2.Canny(cv2.GaussianBlur(g_ic, (3, 3), 0.5), 30, 100), k)
    e_ref = cv2.dilate(cv2.Canny(cv2.GaussianBlur(g_ref, (3, 3), 0.5), 30, 100), k)
    union = np.sum(cv2.bitwise_or(e_ic, e_ref) > 0)
    if union == 0:
        return 0.0
    return float(np.sum(cv2.bitwise_and(e_ic, e_ref) > 0)) / union


def _edge_rerank(ranked: list[tuple[str, float]], icon_img: np.ndarray,
                 atlas_subset: dict[str, np.ndarray]) -> list[tuple[str, float]]:
    if min(icon_img.shape[:2]) < _EDGE_RERANK_MIN_PX:
        return ranked
    if len(ranked) < 2:
        return ranked
    best_score = ranked[0][1]
    candidates = [(n, s) for n, s in ranked if s >= best_score * _EDGE_RERANK_MARGIN]
    if len(candidates) <= 1:
        return ranked
    best_name, best_edge = None, -1.0
    for name, _ in candidates:
        if name in atlas_subset:
            e = _edge_iou(icon_img, atlas_subset[name])
            if e > best_edge:
                best_edge = e
                best_name = name
    if best_name and best_name != ranked[0][0]:
        score = next(s for n, s in ranked if n == best_name)
        return [(best_name, score)] + [(n, s) for n, s in ranked if n != best_name]
    return ranked


_ORB = cv2.ORB_create(nfeatures=100, scaleFactor=1.2, edgeThreshold=5, patchSize=15)
_ORB_BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
_ORB_GOOD_DIST = 50
_ORB_RERANK_MARGIN = 0.90
_orb_feat_cache: dict[str, tuple] = {}


def _orb_features(name: str, img: np.ndarray) -> tuple | None:
    if name in _orb_feat_cache:
        return _orb_feat_cache[name]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    kp, desc = _ORB.detectAndCompute(g, None)
    if desc is None or len(desc) < 2:
        _orb_feat_cache[name] = None  # type: ignore
        return None
    result = (kp, desc)
    _orb_feat_cache[name] = result
    return result


def _orb_rerank(ranked: list[tuple[str, float]], icon_img: np.ndarray,
                atlas_subset: dict[str, np.ndarray]) -> list[tuple[str, float]]:
    if len(ranked) < 2:
        return ranked
    best_score = ranked[0][1]
    candidates = [(n, s) for n, s in ranked if s >= best_score * _ORB_RERANK_MARGIN]
    if len(candidates) <= 1:
        return ranked
    target = next(iter(atlas_subset.values())).shape[0]
    g_icon = cv2.cvtColor(cv2.resize(icon_img, (target, target)), cv2.COLOR_BGR2GRAY)
    kp1, d1 = _ORB.detectAndCompute(g_icon, None)
    if d1 is None or len(d1) < 2:
        return ranked
    best_name, best_orb = None, -1.0
    for name, _ in candidates:
        ref = atlas_subset.get(name)
        if ref is None:
            continue
        feat = _orb_features(name, ref)
        if feat is None:
            continue
        kp2, d2 = feat
        matches = _ORB_BF.match(d1, d2)
        good = sum(1 for m in matches if m.distance < _ORB_GOOD_DIST)
        score = good / max(len(kp1), len(kp2))
        if score > best_orb:
            best_orb = score
            best_name = name
    if best_name and best_name != ranked[0][0]:
        ccorr_score = next(s for n, s in ranked if n == best_name)
        return [(best_name, ccorr_score)] + [(n, s) for n, s in ranked if n != best_name]
    return ranked


def match_trait_row(trait_row: np.ndarray, atlas: dict[str, np.ndarray],
                    expected_icon_size: int | None = None,
                    neg_map: dict[str, str] | None = None) -> list[TraitMatch]:
    """Extract and match all icons in a trait row image.

    Uses spatial zone assignment (shield → diamond → hex left-to-right) to
    determine each icon's shape, then matches against that subset only.
    Falls back to z-score comparison when no spatial anchors are available.
    For large hex icons (>=50px), edge IoU re-ranks close CCORR candidates.
    Deduplicates by icon_name.
    """
    if expected_icon_size is None:
        expected_icon_size = trait_row.shape[0]
    icons = segment_icons(trait_row, expected_size=expected_icon_size)
    shaped = split_atlas_by_shape(atlas, neg_map)
    thresholds = {
        "hexagon": CONFIDENCE_THRESHOLD,
        "diamond": NONHEX_CONFIDENCE_THRESHOLD,
        "shield": NONHEX_CONFIDENCE_THRESHOLD,
    }
    zones = _assign_zones(icons)

    @dataclass
    class _Candidate:
        match: TraitMatch
        ranked: list[tuple[str, float]]
        threshold: float

    candidates: list[_Candidate] = []
    for (icon_img, x, y), zone in zip(icons, zones):
        color, _ = _classify_border_color(icon_img)
        orig_icon = icon_img

        if zone != "unknown":
            if color == "red" and shaped.red.get(zone):
                subset = shaped.red[zone]
            elif color == "green" and zone == "hexagon":
                subset = shaped.cropped[zone]
                icon_img = _crop_interior(icon_img)
            elif color in ("green", "purple", "gold"):
                subset = shaped.full[zone]
            else:
                subset = shaped.cropped[zone]
                icon_img = _crop_interior(icon_img)
            threshold = thresholds[zone]
            sr = _match_icon_scored(icon_img, subset)
            if sr and sr.match.confidence >= threshold:
                ranked = sr.ranked
                if zone == "hexagon" and color == "green":
                    ranked = _orb_rerank(ranked, orig_icon, shaped.full["hexagon"])
                elif zone == "hexagon":
                    ranked = _edge_rerank(ranked, orig_icon, shaped.full["hexagon"])
                elif zone == "shield":
                    ranked = _ccoeff_rerank_shield(ranked, orig_icon, shaped.full["shield"])
                ranked = _normalize_ranked(ranked)
                best_name, best_score = ranked[0]
                if color == "red":
                    best_name = shaped.neg_map.get(best_name, best_name)
                sr.match = TraitMatch(icon_name=best_name, confidence=best_score,
                                      bbox=(x, y, icon_img.shape[1], icon_img.shape[0]))
                sr.ranked = ranked
                candidates.append(_Candidate(match=sr.match, ranked=sr.ranked, threshold=threshold))
            continue

        icon_crop = _crop_interior(icon_img)
        best_sr: _SubsetResult | None = None
        best_z = -1.0
        best_threshold = 0.0
        best_shape = "hexagon"
        for shape_key, threshold in thresholds.items():
            if color == "red" and shaped.red.get(shape_key):
                subset = shaped.red[shape_key]
                match_img = icon_img
            else:
                subset = shaped.cropped[shape_key]
                match_img = icon_crop
            if not subset:
                continue
            sr = _match_icon_scored(match_img, subset)
            if sr is None or sr.match.confidence < threshold:
                continue
            if sr.z_score > best_z:
                best_z = sr.z_score
                best_sr = sr
                best_threshold = threshold
                best_shape = shape_key
        if best_sr is not None:
            ranked = best_sr.ranked
            if best_shape == "hexagon":
                ranked = _edge_rerank(ranked, orig_icon, shaped.full["hexagon"])
            elif best_shape == "shield":
                ranked = _ccoeff_rerank_shield(ranked, orig_icon, shaped.full["shield"])
            ranked = _normalize_ranked(ranked)
            best_name, best_score = ranked[0]
            if color == "red":
                best_name = shaped.neg_map.get(best_name, best_name)
            best_sr.match = TraitMatch(icon_name=best_name, confidence=best_score,
                                       bbox=(x, y, icon_img.shape[1], icon_img.shape[0]))
            best_sr.ranked = ranked
            candidates.append(_Candidate(match=best_sr.match, ranked=best_sr.ranked, threshold=best_threshold))

    return _dedup_matches(candidates)
