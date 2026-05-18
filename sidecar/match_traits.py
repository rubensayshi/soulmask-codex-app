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


def segment_icons(trait_row: np.ndarray, expected_size: int = 64) -> list[tuple[np.ndarray, int, int]]:
    """Segment individual icons from the trait icon row.

    Uses multiple binary thresholds to handle varying background brightness
    (game world bleeds through semi-transparent card UI), then deduplicates
    overlapping detections via NMS-style merging.
    """
    gray = cv2.cvtColor(trait_row, cv2.COLOR_BGR2GRAY) if len(trait_row.shape) == 3 else trait_row
    h, w = gray.shape
    min_side = max(int(expected_size * 0.5), 20)
    max_side = int(expected_size * 2.0)

    candidates: list[tuple[int, int, int]] = []
    for thresh in range(20, 120, 10):
        _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
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


def match_trait_row(trait_row: np.ndarray, atlas: dict[str, np.ndarray],
                    expected_icon_size: int = 64) -> list[TraitMatch]:
    """Extract and match all icons in a trait row image."""
    icons = segment_icons(trait_row, expected_size=expected_icon_size)

    matches = []
    for icon_img, x, y in icons:
        m = match_icon(icon_img, atlas)
        m.bbox = (x, y, icon_img.shape[1], icon_img.shape[0])
        if m.confidence >= CONFIDENCE_THRESHOLD:
            matches.append(m)

    return matches
