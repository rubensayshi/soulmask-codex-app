"""Stage 1: Detect tribesman card boundaries in a screenshot.

The game renders cards in a 2-column grid with thin border lines.
We detect the grid by finding long horizontal separator lines
(morphological line detection) and the vertical column gap.
"""
import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class Card:
    x: int
    y: int
    w: int
    h: int

    def crop(self, img: np.ndarray) -> np.ndarray:
        return img[self.y:self.y + self.h, self.x:self.x + self.w]


# Relative offsets within a card (fractions of card w/h).
# Tuned against 889×140 card crops from 2000×1121 fixture.
LAYOUT = {
    "name":       {"x": 0.03, "y": 0.08, "w": 0.22, "h": 0.25},
    "level_line": {"x": 0.01, "y": 0.42, "w": 0.50, "h": 0.16},
    "trait_row":  {"x": 0.01, "y": 0.58, "w": 0.75, "h": 0.40},
    "status":     {"x": 0.78, "y": 0.43, "w": 0.19, "h": 0.15},
    "group":      {"x": 0.58, "y": 0.72, "w": 0.24, "h": 0.20},
}


def detect_cards(img: np.ndarray) -> list[Card]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    separator_ys = _find_horizontal_separators(gray, w, h)
    if len(separator_ys) < 2:
        return []

    col_gap_x = _find_column_gap(gray, separator_ys, w)

    cards = _build_grid(separator_ys, col_gap_x, w, h)

    if cards:
        heights = sorted([c.h for c in cards], reverse=True)
        median_h = heights[len(heights) // 2]
        min_h = int(median_h * 0.7)
        cards = [c for c in cards if c.h >= min_h]
    cards = [c for c in cards if c.w > 100 and c.h > 50]
    # Cards touching the bottom edge are likely UI chrome, not real cards
    cards = [c for c in cards if c.y + c.h < h - 10]
    cards.sort(key=lambda c: (c.y, c.x))
    return cards


def _find_horizontal_separators(gray: np.ndarray, w: int, h: int) -> list[int]:
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -3,
    )
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 5, 100), 1))
    horiz_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horiz_kernel)

    row_sums = np.sum(horiz_lines, axis=1) / 255
    min_extent = w * 0.60

    strong_rows = np.where(row_sums > min_extent)[0]
    lines: list[int] = []
    last = -100
    for r in strong_rows:
        if r - last > 8:
            lines.append(int(r))
        last = r

    if len(lines) < 2:
        return lines

    # Real card-row boundaries are double-lines (bottom of card N + top of
    # card N+1, ~20-30px apart).  Internal card lines are singles.
    # Identify double-line pairs and use their midpoints as separators.
    pairs: list[tuple[int, int]] = []
    used: set[int] = set()
    for i in range(len(lines) - 1):
        if i in used:
            continue
        if lines[i + 1] - lines[i] <= 35:
            pairs.append((lines[i], lines[i + 1]))
            used.add(i)
            used.add(i + 1)

    if len(pairs) < 2:
        return _filter_by_gap(lines, h)

    midpoints = [(a + b) // 2 for a, b in pairs]

    gaps = [midpoints[i + 1] - midpoints[i] for i in range(len(midpoints) - 1)]
    card_h = int(np.median(gaps))

    above: list[int] = []
    y = midpoints[0] - card_h
    while y > 0:
        above.append(max(0, y))
        y -= card_h
    above.reverse()

    below: list[int] = []
    y = midpoints[-1] + card_h
    while y < h:
        below.append(min(h, y))
        y += card_h

    return above + midpoints + below


def _filter_by_gap(lines: list[int], h: int) -> list[int]:
    """Fallback separator filter for low-res images without double-lines."""
    merged: list[int] = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and lines[i + 1] - lines[i] < 20:
            merged.append((lines[i] + lines[i + 1]) // 2)
            i += 2
        else:
            merged.append(lines[i])
            i += 1

    if len(merged) < 3:
        return merged

    gaps = [merged[i + 1] - merged[i] for i in range(len(merged) - 1)]
    gaps_sorted = sorted(gaps, reverse=True)
    dominant_h = int(np.median(gaps_sorted[: max(len(gaps_sorted) // 2, 2)]))
    # At higher resolutions (4K) internal card dividers can look like separators;
    # enforce an image-height-based floor so they are never accepted as card boundaries.
    min_card_h = max(int(dominant_h * 0.65), int(h * 0.08))

    def _sweep(pts: list[int], reverse: bool) -> list[int]:
        seq = list(reversed(pts)) if reverse else pts
        out = [seq[0]]
        for y in seq[1:]:
            gap = abs(y - out[-1])
            if gap >= min_card_h:
                out.append(y)
        if reverse:
            out.reverse()
        return out

    bottom_up = _sweep(merged, reverse=True)
    top_down = _sweep(merged, reverse=False)

    def _variance(seps: list[int]) -> float:
        if len(seps) < 2:
            return 0.0
        gs = [seps[i + 1] - seps[i] for i in range(len(seps) - 1)]
        avg = sum(gs) / len(gs)
        return sum((g - avg) ** 2 for g in gs) / len(gs)

    filtered = top_down if _variance(top_down) <= _variance(bottom_up) else bottom_up

    if len(filtered) >= 3:
        g1 = filtered[1] - filtered[0]
        g2 = filtered[2] - filtered[1]
        combined = filtered[2] - filtered[0]
        if g1 < dominant_h * 0.85 and g2 < dominant_h * 0.85 and combined >= min_card_h:
            filtered = [filtered[0]] + filtered[2:]
        elif g1 < dominant_h * 0.85:
            filtered = filtered[1:]

    return filtered


def _find_column_gap(gray: np.ndarray, sep_ys: list[int], w: int) -> int:
    if len(sep_ys) < 2:
        return w // 2

    y_start = sep_ys[len(sep_ys) // 2] if len(sep_ys) > 2 else sep_ys[0]
    y_end = sep_ys[-1]
    search_start = int(w * 0.40)
    search_end = int(w * 0.60)

    strip = gray[y_start:y_end, search_start:search_end]
    col_brightness = np.mean(strip, axis=0)

    kernel_size = max(w // 100, 5)
    if kernel_size % 2 == 0:
        kernel_size += 1
    smoothed = cv2.GaussianBlur(col_brightness.reshape(1, -1), (kernel_size, 1), 0).flatten()

    # Gap can be the brightest (daytime) or darkest (nighttime) column;
    # pick whichever candidate is closer to the image center.
    center = (search_end - search_start) // 2
    x_max = int(np.argmax(smoothed))
    x_min = int(np.argmin(smoothed))
    gap_local = x_max if abs(x_max - center) <= abs(x_min - center) else x_min
    return gap_local + search_start


def _build_grid(sep_ys: list[int], gap_x: int, w: int, h: int) -> list[Card]:
    cards = []
    # Inset from edges: cards don't go all the way to image borders
    left_margin = int(w * 0.04)
    right_margin = int(w * 0.04)
    col_padding = int(w * 0.01)

    left_col_w = gap_x - col_padding - left_margin
    col_ranges = [
        (left_margin, gap_x - col_padding),
        (gap_x + col_padding, gap_x + col_padding + left_col_w),
    ]

    for i in range(len(sep_ys) - 1):
        y_top = sep_ys[i]
        y_bot = sep_ys[i + 1]
        card_h = y_bot - y_top
        if card_h < 30:
            continue
        for col_left, col_right in col_ranges:
            col_w = col_right - col_left
            if col_w < 100:
                continue
            cards.append(Card(x=col_left, y=y_top, w=col_w, h=card_h))

    return cards


def crop_region(card_img: np.ndarray, region_key: str) -> np.ndarray:
    r = LAYOUT[region_key]
    h, w = card_img.shape[:2]
    x1 = int(r["x"] * w)
    y1 = int(r["y"] * h)
    x2 = int((r["x"] + r["w"]) * w)
    y2 = int((r["y"] + r["h"]) * h)
    return card_img[y1:y2, x1:x2]
