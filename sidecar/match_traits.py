"""Stage 3-4: Extract trait icons from card row and match against reference atlas."""
import os
import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class TraitMatch:
    icon_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h within the icon row


CONFIDENCE_THRESHOLD = 0.62
NONHEX_CONFIDENCE_THRESHOLD = 0.55
_COLOR_TO_SHAPE = {"green": "hexagon", "gold": "shield", "purple": "diamond"}


def _icon_shape(name: str) -> str:
    if name.startswith("Icon_NG_XiHao") or name.startswith("Icon_NG_XingGe"):
        return "diamond"
    if name.startswith("Icon_NG_BuLuo") or name.startswith("ChengHao") or name.startswith("Icon_NG_JingLi"):
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


@dataclass
class ShapedAtlas:
    full: dict[str, dict[str, np.ndarray]]
    cropped: dict[str, dict[str, np.ndarray]]


def split_atlas_by_shape(atlas: dict[str, np.ndarray]) -> ShapedAtlas:
    full: dict[str, dict[str, np.ndarray]] = {"hexagon": {}, "diamond": {}, "shield": {}}
    cropped: dict[str, dict[str, np.ndarray]] = {"hexagon": {}, "diamond": {}, "shield": {}}
    for name, img in atlas.items():
        shape = _icon_shape(name)
        full[shape][name] = img
        cropped[shape][name] = _crop_interior(img)
    return ShapedAtlas(full=full, cropped=cropped)


def segment_icons(trait_row: np.ndarray, expected_size: int = 64) -> list[tuple[np.ndarray, int, int]]:
    """Segment individual icons from the trait icon row.

    Uses multiple binary thresholds to handle varying background brightness
    (game world bleeds through semi-transparent card UI), then deduplicates
    overlapping detections via NMS-style merging.
    """
    gray = cv2.cvtColor(trait_row, cv2.COLOR_BGR2GRAY) if len(trait_row.shape) == 3 else trait_row
    h, w = gray.shape
    min_side = max(int(expected_size * 0.4), 16)
    max_side = int(expected_size * 2.0)

    candidates: list[tuple[int, int, int]] = []

    def _collect(binary: np.ndarray) -> None:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw < min_side or bh < min_side or bw > max_side or bh > max_side:
                continue
            aspect = max(bw, bh) / min(bw, bh) if min(bw, bh) > 0 else 99
            if aspect > 1.8:
                continue
            side = max(bw, bh)
            cx, cy = bx + bw // 2, by + bh // 2
            candidates.append((cx, cy, side))

    for thresh in range(20, 120, 10):
        _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        _collect(binary)

    for block in [15, 21]:
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, block, -3)
        _collect(binary)

    if not candidates:
        return []

    candidates.sort(key=lambda c: c[0])
    merged: list[tuple[int, int, int]] = []
    used = [False] * len(candidates)
    for i, (cx, cy, side) in enumerate(candidates):
        if used[i]:
            continue
        group_cx, group_cy, group_side = [cx], [cy], [side]
        used[i] = True
        for j in range(i + 1, len(candidates)):
            if used[j]:
                continue
            cx2, cy2, side2 = candidates[j]
            if abs(cx2 - cx) < side * 0.4 and abs(cy2 - cy) < side * 0.4:
                group_cx.append(cx2)
                group_cy.append(cy2)
                group_side.append(side2)
                used[j] = True
        merged.append((
            int(np.mean(group_cx)),
            int(np.mean(group_cy)),
            int(np.median(group_side)),
        ))

    if len(merged) >= 3:
        sides = sorted([s for _, _, s in merged])
        median_side = sides[len(sides) // 2]
        lo, hi = median_side * 0.5, median_side * 1.6
        merged = [(cx, cy, s) for cx, cy, s in merged if lo <= s <= hi]

    icons: list[tuple[np.ndarray, int, int]] = []
    for cx, cy, side in merged:
        x1 = max(0, cx - side // 2)
        y1 = max(0, cy - side // 2)
        x2 = min(w, x1 + side)
        y2 = min(h, y1 + side)
        crop = trait_row[y1:y2, x1:x2]
        if crop.size > 0:
            icons.append((crop, x1, y1))

    icons.sort(key=lambda t: t[1])
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


def _dedup_matches(candidates: list) -> list[TraitMatch]:
    """Deduplicate by icon_name: when two icons match the same template,
    the weaker one falls back to its next-best above-threshold match."""
    taken: dict[str, int] = {}
    result: list[TraitMatch] = [c.match for c in candidates]

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
                                       bbox=loser.match.bbox)
                result[loser_idx] = alt_match
                taken[alt_name] = loser_idx
                reassigned = True
                break
        if not reassigned:
            result[loser_idx] = None  # type: ignore

    return [m for m in result if m is not None]


def match_trait_row(trait_row: np.ndarray, atlas: dict[str, np.ndarray],
                    expected_icon_size: int | None = None) -> list[TraitMatch]:
    """Extract and match all icons in a trait row image.

    Uses spatial zone assignment (shield → diamond → hex left-to-right) to
    determine each icon's shape, then matches against that subset only.
    Falls back to z-score comparison when no spatial anchors are available.
    Deduplicates by icon_name.
    """
    if expected_icon_size is None:
        expected_icon_size = trait_row.shape[0]
    icons = segment_icons(trait_row, expected_size=expected_icon_size)
    shaped = split_atlas_by_shape(atlas)
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

        if zone != "unknown":
            if color in ("green", "purple", "gold"):
                subset = shaped.full[zone]
            else:
                subset = shaped.cropped[zone]
                icon_img = _crop_interior(icon_img)
            threshold = thresholds[zone]
            sr = _match_icon_scored(icon_img, subset)
            if sr and sr.match.confidence >= threshold:
                sr.match.bbox = (x, y, icon_img.shape[1], icon_img.shape[0])
                candidates.append(_Candidate(match=sr.match, ranked=sr.ranked, threshold=threshold))
            continue

        icon_crop = _crop_interior(icon_img)
        best_sr: _SubsetResult | None = None
        best_z = -1.0
        best_threshold = 0.0
        for shape_key, threshold in thresholds.items():
            subset = shaped.cropped[shape_key]
            if not subset:
                continue
            sr = _match_icon_scored(icon_crop, subset)
            if sr is None or sr.match.confidence < threshold:
                continue
            if sr.z_score > best_z:
                best_z = sr.z_score
                best_sr = sr
                best_threshold = threshold
        if best_sr is not None:
            best_sr.match.bbox = (x, y, icon_img.shape[1], icon_img.shape[0])
            candidates.append(_Candidate(match=best_sr.match, ranked=best_sr.ranked, threshold=best_threshold))

    return _dedup_matches(candidates)
