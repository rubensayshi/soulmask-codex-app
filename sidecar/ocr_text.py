"""Stage 2: OCR text extraction from cropped card regions."""
import re
import os
import cv2
import numpy as np
import pytesseract

# Ensure Tesseract is found on Windows
_TESSERACT_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.name == "nt" and os.path.exists(_TESSERACT_WIN):
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_WIN
from dataclasses import dataclass


@dataclass
class CardText:
    name: str
    level: int | None
    class_name: str | None
    clan: str | None
    title: str | None
    status: str | None
    group: str | None


def _mask_badge_icon(img: np.ndarray) -> np.ndarray:
    """Detect and mask the colored badge icon (hexagon/diamond/shield) in the name crop.

    The badge is a small, saturated, colored icon that appears after the name text.
    Name text is white/light gray (low saturation), while the badge is distinctly
    colored (green, purple, gold). We find the leftmost high-saturation column
    in the right 60% of the crop and black out everything from there rightward.
    """
    if len(img.shape) != 3:
        return img
    h, w = img.shape[:2]
    if w < 20 or h < 10:
        return img

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]  # saturation channel
    val = hsv[:, :, 2]  # value channel

    # Only look in the right 55% of the crop (badge is always after some text)
    search_start = int(w * 0.45)
    # For each column, check if there's a significant saturated+bright region.
    # Use strict thresholds to avoid catching semi-transparent card backgrounds.
    result = img.copy()
    badge_start = None
    consecutive = 0
    for x in range(search_start, w):
        col_sat = sat[:, x]
        col_val = val[:, x]
        # Count pixels that are distinctly colored (high sat + brightness)
        colored_pixels = np.sum((col_sat > 80) & (col_val > 80))
        if colored_pixels >= h * 0.30:
            consecutive += 1
            if consecutive >= 3 and badge_start is None:  # need 3+ consecutive columns
                badge_start = x - consecutive + 1
        else:
            consecutive = 0
    if badge_start is not None:
        # Add a small left margin to ensure we don't clip text
        mask_start = max(search_start, badge_start - 3)
        result[:, mask_start:] = 0

    return result


def preprocess_for_ocr(img: np.ndarray, threshold: int = 70, use_red: bool = False) -> np.ndarray:
    """Upscale and binarize game UI text (light text on dark background)."""
    if use_red and len(img.shape) == 3:
        # Golden/orange game text has high R channel even though grayscale is dim
        gray = img[:, :, 2]  # BGR → R channel
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape
    if w < 600:
        scale = 600 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return binary


def ocr_region(img: np.ndarray, psm: int = 7, threshold: int = 70,
               use_red: bool = False, whitelist: str | None = None) -> str:
    processed = preprocess_for_ocr(img, threshold=threshold, use_red=use_red)
    config = f"--psm {psm} --oem 3"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"
    text = pytesseract.image_to_string(processed, config=config)
    return text.strip()


_NAME_FIXES = [
    (r'^Sex\b', 'Ex'),
    (r'^Spy\b', 'Ex'),
    (r'\bGathererer\b', 'Gatherer'),
    (r'\bDefendert\b', 'Defender'),
]


def parse_name(text: str) -> str:
    text = re.sub(r'(?<=\s)\|(?=\s)', 'I', text)
    text = re.sub(r'(?<=\S)\|(?=V)', ' I', text)
    text = re.sub(r'[|\u00ae\u00ab\u00bb\u00a9]', ' ', text)

    # Replace non-ASCII characters with nothing (OCR encoding artifacts like ·, ü, etc.)
    text = re.sub(r'[^\x20-\x7e]', '', text)
    # Apostrophe between words without space is likely OCR noise: "Bepker'Bee" → "Bepker Bee"
    text = re.sub(r"(?<=[a-zA-Z])'(?=[a-zA-Z])", ' ', text)
    # Split CamelCase: "ExChef" \u2192 "Ex Chef" (but not ALL CAPS or roman like "VII")
    text = re.sub(r'(?<=[a-z])(?=[A-Z][a-z])', ' ', text)
    # Fix OCR stutter at word start: "Iitem" \u2192 "Item"
    words = text.split()
    for idx, w in enumerate(words):
        if len(w) >= 3 and w[0].isupper() and w[1].islower() and w[0].lower() == w[1]:
            words[idx] = w[0] + w[2:]  # keep the uppercase, drop the duplicate lowercase
    text = ' '.join(words)
    text = re.sub(r'^[\u25c6\u25c7\u2666<>\[\]\u00a9\u00ae\u00b0\u2022\u00b7&@#%~*\-_\d\s\'\"\u2018\u2019\u201c\u201d()+:;,.!?/\\\u20ac{}]+', '', text)
    text = re.sub(r'^[a-z&@#~*\-]{1,4}\s+', '', text)
    text = re.sub(r'^x[a-z]?\s+', '', text, flags=re.IGNORECASE)
    # Strip single uppercase letter + space before a capitalized word (OCR bleed)
    # Exclude V/X which could be valid roman numeral starts
    text = re.sub(r'^[A-HJ-UW-Z]\s+(?=[A-Z][a-z])', '', text)
    # Strip leading "I" or "l" before a clearly non-roman word ("I Farmer" but not "I Viking")
    text = re.sub(r'^[Il]\s+(?=[A-UW-Z][a-eg-z])', '', text)
    # Strip uppercase noise prefix (2-4 chars) before a capitalized word ("ABV Worker" → "Worker")
    text = re.sub(r'^[A-Z]{2,4}\s+(?=[A-Z][a-z])', '', text)

    text = re.sub(r'\bl(?=[A-Z])', 'I', text)
    text = re.sub(r'^[A-Z](?=[A-Z][a-z])', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Re-apply I/l-strip after l→I conversion ("l Farmer" → "I Farmer" → "Farmer")
    text = re.sub(r'^[Il]\s+(?=[A-UW-Z][a-eg-z])', '', text)

    text = re.sub(r'\(X\b', 'IX', text)
    text = re.sub(r'\[V\b', 'IV', text)
    text = re.sub(r'\(V[v]?\b', 'IV', text)

    # Fix garbled Roman numerals containing non-alpha chars (word cleanup would strip them)
    text = re.sub(r'(?<=\s)[!\\]V[^a-zA-Z\s]*', 'IV', text)
    text = re.sub(r'(?<=\s)Ul\b', 'II', text)
    text = re.sub(r'(?<=\s)Il\b', 'II', text)
    text = re.sub(r'(?<=\s)V[vu]\b', 'VII', text)
    text = re.sub(r'(?<=\s)lV\b', 'IV', text)

    # Split glued roman numerals from end of words: "BeelV" → "Bee IV"
    # Only match clear roman patterns (lV, lI+V, etc.), NOT standalone l/ll/lll
    # which would falsely split words like "Final" → "Fina I"
    text = re.sub(r'(?<=[a-z])(lV(?:II?I?)?|Il{1,2}|lI)(?=\s|$)',
                  lambda m: ' ' + m.group(1).replace('l', 'I'), text)
    text = re.sub(r'\s+', ' ', text).strip()

    words = text.split()
    while words:
        w = words[-1]
        if len(w) == 1 and w not in 'IVXLl':
            words.pop()
        elif re.match(r'^\d+$', w):
            words.pop()
        elif re.match(r'^[^a-zA-Z]+$', w):
            words.pop()
        elif len(w) <= 2 and not re.match(r'^[A-Z]{1,2}$', w) and not re.match(r'^[lI]+$', w):
            words.pop()
        elif re.search(r'[^a-zA-Z]', w) and len(w) <= 4:
            words.pop()
        else:
            break
    text = ' '.join(words)

    text = re.sub(r'(?<=\s)t[tl]{1,2}\b', lambda m: 'I' * len(m.group()), text)
    text = re.sub(r'(?<=\s)[lI]{2,3}(?=[\s\W]|$)', lambda m: 'I' * len(m.group()), text)
    text = re.sub(r'(?<=[a-z])[lI]{2,3}(?=[\s\W]|$)', lambda m: ' ' + 'I' * len(m.group()), text)
    text = re.sub(r'(?<=\s)l(?=\s|$)', 'I', text)

    text = re.sub(r'VILL\b', 'VIII', text)
    text = re.sub(r'VIL\b', 'VII', text)
    text = re.sub(r'VUS\b', 'VII', text)
    text = re.sub(r'VU\b', 'VII', text)
    text = re.sub(r'[Vv]ie\b', 'VI', text)
    text = re.sub(r'VIS\b', 'VI', text)
    text = re.sub(r'VL\b', 'VI', text)
    text = re.sub(r'(?<=\s)Vi\b', 'VI', text)
    text = re.sub(r'(?<=\s)Vil\b', 'VII', text)
    text = re.sub(r'(?<=\s)Vili\b', 'VIII', text)
    text = re.sub(r'(?<=\s)li\b', 'II', text)
    text = re.sub(r'(?<=\s)lil\b', 'III', text)
    # Fix garbled X-based romans: "XIl" → "XII", "Xl" → "XI"
    text = re.sub(r'(?<=\s)X[Ii]l\b', 'XII', text)
    text = re.sub(r'(?<=\s)Xl\b', 'XI', text)
    text = re.sub(r'(?<=\s)LX\b', 'IX', text)
    text = re.sub(r'VUL\b', 'VIII', text)
    text = re.sub(r'(?<=\s)Vir\b', 'VIII', text)

    text = re.sub(r'\s+(V?I{0,3})L(?=["\x27\u201c\u201d\u2018\u2019\s]|$)', lambda m: ' ' + m.group(1) + 'I', text)
    text = re.sub(r'["\x27\u201c\u201d\u2018\u2019]$', '', text).strip()

    text = re.sub(r'([a-z])(VIII|VII|VI|IX|IV|III|II|X|I)(?=[\s\W]|$)', lambda m: m.group(1) + ' ' + m.group(2), text)
    text = re.sub(r'\s+', ' ', text).strip()

    text = re.sub(r'(?<=\s)([IVX]{1,4})[^a-zA-Z\s]+\S*', r'\1', text)
    # Strip garbled prefix on roman numerals: "UWLVI" → "VI" (only if
    # the prefix contains non-roman chars like W,U,L mixed with I/V/X)
    text = re.sub(r'(?<=\s)[A-Z]*[^IVX\s][A-Z]*(VIII|VII|VI|IX|IV|III|II)\b', r'\1', text)

    roman_suffix = ""
    rm = re.search(r'\s+(VIII|VII|VI|IX|IV|V|III|II|X|I)(?:\s|$)', text)
    if rm:
        roman_suffix = " " + rm.group(1)
        text = text[:rm.start()]

    text = re.sub(r'\s+[A-Za-z]*\s*\d+\s*[A-Za-z]*\s*$', '', text)
    text = re.sub(r'\s+[^\w\s].*$', '', text)
    text = re.sub(r'\s+[&@#<>\[\]\u00a9\u00ae\u00b0\u2022\u00b7\-_|:;,.!?\d]+$', '', text)
    if not re.search(r'\s+[IVXL]{1,5}$', text):
        text = re.sub(r'\s+\S{1,2}$', '', text)
    text = re.sub(r'[&@#\d\s.,:;!?]+$', '', text)
    # Strip trailing all-lowercase words (class/weapon text leaking into name)
    # e.g. "Tanner sword. blade" \u2192 "Tanner"
    text = re.sub(r'(\s+[a-z][a-z.,:;!?]*)+$', '', text)
    result = (text + roman_suffix).strip()
    if result and result[0] == 'l':
        result = 'I' + result[1:]
    # Strip trailing single uppercase letter (OCR artifact, e.g. "YayaS" → "Yaya")
    result = re.sub(r'(?<=[a-z])[A-Z]$', '', result)
    # Fix roman numeral glued to previous word: "BeelV" → "Bee IV"
    result = re.sub(r'(?<=[a-z])(VIII|VII|VI|IX|IV|III|II|lV|lI|Il)$', lambda m: ' ' + m.group(1).replace('l', 'I'), result)
    for bad, good in _NAME_FIXES:
        result = re.sub(bad, good, result)
    return result


_VALID_ROMAN_SET = {'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'}


def _score_name(name: str) -> int:
    if not name or not name[0].isupper():
        return -100
    alpha = sum(c.isalpha() for c in name)
    if alpha < 3:
        return -50
    words = name.split()
    score = min(alpha, 10) * 2
    score += min(len(words), 3) * 3
    score -= max(0, len(words) - 3) * 15
    score += sum(3 for w in words if w and w[0].isupper())
    score -= sum(5 for w in words if w and w[0].islower() and w not in ('of', 'the', 'and', 'in'))
    # Penalize non-alpha characters; non-ASCII artifacts (encoding garbage) are much worse
    for c in name:
        if c == ' ':
            continue
        if not c.isalpha():
            score -= 10 if not c.isascii() else 3
    for w in words:
        if w.isupper() and len(w) >= 2 and w not in _VALID_ROMAN_SET:
            score -= 12
    if re.search(r'\s+(VIII|VII|VI|IX|IV|V|III|II|X|I)$', name):
        score += 5
    return score


KNOWN_CLANS = ["Flint", "Long", "Fang", "Claw", "Wolf", "Horn", "Outcast"]

_CLAN_MAP = {
    "flint": "Flint", "iint": "Flint", "ilint": "Flint", "mint": "Flint",
    "lint": "Flint", "fint": "Flint", "flinlt": "Flint", "llint": "Flint",
    "ulint": "Flint", "illint": "Flint", "flintg": "Flint", "itinl": "Flint",
    "llmt": "Flint", "i lint": "Flint", "fi": "Flint",
    "fiint": "Flint", "fliint": "Flint", "filnt": "Flint", "ftint": "Flint",
    "flinl": "Flint", "rint": "Flint", "pint": "Flint", "finl": "Flint",
    "falint": "Flint", "lhint": "Flint", "fitnt": "Flint", "ptnt": "Flint",
    "hnt": "Flint",
    "long": "Long", "lang": "Long", "iane": "Long", "iang": "Long",
    "ianp": "Long", "lanp": "Long", "lange": "Long", "llang": "Long",
    "ang": "Long",
    "fang": "Fang", "fanpg": "Fang", "fanp": "Fang",
    "claw": "Claw", "ciaw": "Claw",
    "wolf": "Wolf", "wolt": "Wolf", "woll": "Wolf",
    "horn": "Horn", "hom": "Horn",
    "outcast": "Outcast", "oulcast": "Outcast", "oulcasl": "Outcast",
    "outcasl": "Outcast", "0utcast": "Outcast",
}


def _normalize_clan(raw: str) -> str:
    key = raw.lower().strip()
    # Strip non-alpha except spaces, collapse spaces
    cleaned = re.sub(r'[^a-z\s]', '', key).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    words = cleaned.split()
    first = words[0] if words else ""
    # Also try joining first 2 short words ("b ang" → "bang")
    joined = ''.join(words[:2]) if len(words) >= 2 and len(words[0]) <= 2 else first

    for candidate in [key, cleaned, first, joined]:
        if candidate in _CLAN_MAP:
            return _CLAN_MAP[candidate]

    # Substring check
    for clan in KNOWN_CLANS:
        cl = clan.lower()
        if cl in cleaned or first in cl:
            return clan

    # Edit distance fallback on first word
    best_clan, best_dist = None, 999
    for clan in KNOWN_CLANS:
        cl = clan.lower()
        for w in [first, joined]:
            if not w:
                continue
            d = _edit_distance(w, cl)
            if d < best_dist:
                best_dist = d
                best_clan = clan
    if best_clan and best_dist <= max(2, len(first) // 2):
        return best_clan
    return raw


def _edit_distance(a: str, b: str) -> int:
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for j in range(1, len(b) + 1):
        curr = [j] + [0] * len(a)
        for i in range(1, len(a) + 1):
            curr[i] = min(prev[i] + 1, curr[i - 1] + 1, prev[i - 1] + (a[i - 1] != b[j - 1]))
        prev = curr
    return prev[len(a)]


_DIGIT_FIXES = str.maketrans({
    'G': '6', 'O': '0', 'S': '5', 'B': '8',
    'g': '6', 's': '5', 'b': '8',
    'l': '1', 'i': '1', 'o': '0', '/': '7', 'I': '1',
})


def extract_level_number(level_img: np.ndarray) -> int | None:
    """Extract level from tight crop using digit-only OCR + pattern matching + majority vote."""
    h, w = level_img.shape[:2]
    tight = level_img[:, :int(w * 0.25)]

    candidates: list[int] = []
    thresholds = [
        (50, False), (65, False), (80, False), (100, False),
        (80, True), (100, True), (120, True),
    ]
    for thresh, use_red in thresholds:
        # Digit-whitelist pass: Tesseract only looks for digits
        raw_d = ocr_region(tight, psm=8, threshold=thresh, use_red=use_red,
                           whitelist="0123456789")
        digits = re.sub(r'[^0-9]', '', raw_d)
        if len(digits) >= 2:
            val = int(digits[-2:])
            if 1 <= val <= 60:
                candidates.append(val)

        # Pattern pass: find "V.XX" in full text and apply digit fixes
        raw_f = ocr_region(tight, psm=7, threshold=thresh, use_red=use_red)
        m = re.search(r'[VvNn¥]\.?\s*(\S{1,3}?)(?=\s|$)', raw_f)
        if m:
            fixed = m.group(1).translate(_DIGIT_FIXES)
            fixed = re.sub(r'[^0-9]', '', fixed)
            if len(fixed) >= 2:
                val = int(fixed[-2:])
                if 1 <= val <= 60:
                    candidates.append(val)

    if not candidates:
        return None

    from collections import Counter
    counts = Counter(candidates)
    best_val, best_count = counts.most_common(1)[0]
    if best_count >= 2:
        return best_val
    return best_val if len(candidates) >= 2 else None


def parse_level_line(text: str) -> dict:
    result: dict = {"level": None, "class_name": None, "clan": None, "title": None}

    # Extract clan from angle brackets: <Flint Tribe>
    clan_match = re.search(r'[<＜]([^>＞]+)[>＞]', text)
    if clan_match:
        clan_raw = clan_match.group(1).strip()
        # Strip "Tribe"/"ribe"/"lribe" suffix (OCR mangles capitalization and spacing)
        clan_raw = re.sub(r"[\s']*[TtlI]?ribe\s*$", "", clan_raw).strip()
        clan_raw = re.sub(r"['`]", "", clan_raw).strip()
        # Strip trailing punctuation, parens, digits, and single-char artifacts
        clan_raw = re.sub(r'[*()\[\]{}<>.,;:!?&@#%\d]+$', '', clan_raw).strip()
        clan_raw = re.sub(r'\s+\S$', '', clan_raw).strip()
        # Collapse spaces and strip short trailing fragments for cleaner lookup
        clan_raw = re.sub(r'\s+', ' ', clan_raw).strip()
        result["clan"] = _normalize_clan(clan_raw)
        text = text[:clan_match.start()] + text[clan_match.end():]

    # Extract level: LV.32  (OCR misreads L→1/I, V→¥, digits→letters)
    _D = r'[0-9GOSBgosblIio/]'  # any char that could be an OCR-garbled digit
    level_match = re.search(
        r'(?:^|(?<=[\s|]))(?:[1lILi])?[Vv¥Nn]\.?\s*(' + _D + _D + r'{0,2})(?=[\s).>,;:A-Z\[]|[^a-zA-Z0-9]|$)',
        text
    )
    if not level_match:
        # LV stuck to leading garbage: "HILV.48" "ftv.ss" — require 2+ digit chars
        level_match = re.search(
            r'[Vv¥]\.?\s*(' + _D + r'{2,3})(?=[\s).>,;:A-Z\[]|[^a-zA-Z0-9]|$)',
            text
        )
    if not level_match:
        # Bare digits anywhere: "qu 32 Skilled" or "33 Skilled Guard"
        level_match = re.search(r'(?:^|(?<=\s))(\d{2,3})(?=\s+[A-Z])', text)
    if level_match:
        raw_lv = level_match.group(1)
        cleaned_lv = raw_lv.translate(_DIGIT_FIXES)
        cleaned_lv = re.sub(r'[^0-9]', '', cleaned_lv)
        lv = int(cleaned_lv) if cleaned_lv else None
        if lv is not None:
            if lv <= 100:
                result["level"] = lv
            elif 100 < lv < 1000:
                trimmed = lv % 100
                result["level"] = trimmed if trimmed > 0 else None
        text = text[:level_match.start()] + text[level_match.end():]

    class_name = text.strip().strip(".,;: ")
    class_name = re.sub(r'^[\d|!\[\](){}<>"\'\s.,;:*#@&%^~`/\\]+', '', class_name).strip()
    # Remove leading short artifacts (1-2 chars before space): "cv Novice..." → "Novice..."
    class_name = re.sub(r'^\S{1,2}\s+', '', class_name).strip()
    parts = re.split(r'\s{2,}', class_name)
    parts = [p.strip() for p in parts if len(p.strip()) > 1]
    if parts:
        result["class_name"] = _normalize_class(parts[0])
        if len(parts) > 1:
            result["title"] = parts[-1]

    return result


KNOWN_CLASSES = [
    "Skilled Craftsman", "Novice Craftsman", "Master Craftsman",
    "Skilled Warrior", "Novice Warrior", "Master Warrior",
    "Skilled Guard", "Novice Guard", "Master Guard",
    "Skilled Tamer", "Novice Tamer", "Master Tamer",
    "Skilled Hunter", "Novice Hunter", "Master Hunter",
    "Skilled Laborer", "Novice Laborer", "Master Laborer",
]


_CLASS_WORD_FIXES = {
    "lhmler": "Hunter", "lhimler": "Hunter", "limler": "Hunter",
    "iimler": "Hunter", "himler": "Hunter", "lhunter": "Hunter",
    "llimler": "Hunter", "llumter": "Hunter", "ilumter": "Hunter",
    "ihmter": "Hunter", "tlimter": "Hunter", "himter": "Hunter",
    "lmter": "Hunter", "lhmter": "Hunter", "lumter": "Hunter",
    "iimter": "Hunter", "limter": "Hunter", "lhumter": "Hunter",
    "hlimler": "Hunter", "hmter": "Hunter", "imler": "Hunter",
    "imter": "Hunter", "unter": "Hunter", "unler": "Hunter",
    "labore": "Laborer", "larborer": "Laborer",
    "wairior": "Warrior", "warri": "Warrior", "wantior": "Warrior",
    "wartior": "Warrior", "waniior": "Warrior", "warrion": "Warrior",
    "wantion": "Warrior", "wafrir": "Warrior", "watridr": "Warrior",
    "wgtribr": "Warrior", "watfior": "Warrior", "wattior": "Warrior",
    "guaid": "Guard", "gnard": "Guard", "guad": "Guard",
    "craltsman": "Craftsman", "craftman": "Craftsman",
    "craftsmah": "Craftsman", "cfgsgnan": "Craftsman",
    "itimler": "Hunter", "bnler": "Hunter", "ihmler": "Hunter",
    "noyjge": "Novice", "novige": "Novice", "novjce": "Novice",
    "masigr": "Master", "magigr": "Master", "masler": "Master",
    "skiled": "Skilled", "skiiled": "Skilled",
}


def _normalize_class(raw: str) -> str:
    cleaned = re.sub(r'[|}{)\[\]0-9:;,.!?\\]', '', raw).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    words = cleaned.split()
    for i, w in enumerate(words):
        fix = _CLASS_WORD_FIXES.get(w.lower())
        if fix:
            words[i] = fix
    cleaned = ' '.join(words)
    r = cleaned.lower()
    for klass in KNOWN_CLASSES:
        k = klass.lower()
        words = k.split()
        if len(words) == 2 and all(_fuzzy_word(w, r) for w in words):
            return klass
    # Single-word fallback: OCR drops the rank prefix entirely
    role_words = ["craftsman", "warrior", "guard", "tamer", "hunter", "laborer"]
    for role in role_words:
        if _fuzzy_word(role, r):
            for klass in KNOWN_CLASSES:
                if role in klass.lower():
                    return klass
            break
    return cleaned if cleaned else raw


def _fuzzy_word(word: str, text: str) -> bool:
    """Check if word appears approximately in text (3+ char substring match)."""
    if word in text:
        return True
    for i in range(len(word) - 2):
        if word[i:i+3] in text:
            return True
    # Also check reverse: does any 3-char chunk of text appear in the word?
    text_nospace = text.replace(' ', '')
    for i in range(len(text_nospace) - 2):
        if text_nospace[i:i+3] in word:
            return True
    return False


def _merge_level_data(a: dict, b: dict) -> dict:
    """Merge two level_line parse results, preferring whichever has more data."""
    ca = a.get("class_name", "")
    cb = b.get("class_name", "")
    ca_known = ca in KNOWN_CLASSES
    cb_known = cb in KNOWN_CLASSES

    # For level: prefer the channel that also produced a known class (better OCR quality)
    if a["level"] is not None and b["level"] is not None:
        if cb_known and not ca_known:
            level = b["level"]
        elif ca_known and not cb_known:
            level = a["level"]
        else:
            level = a["level"]
    else:
        level = a["level"] if a["level"] is not None else b["level"]

    result = {"level": level}
    if ca_known and not cb_known:
        result["class_name"] = ca
    elif cb_known and not ca_known:
        result["class_name"] = cb
    else:
        result["class_name"] = ca or cb
    result["clan"] = a.get("clan") or b.get("clan")
    result["title"] = a.get("title") or b.get("title")
    return result


KNOWN_STATUSES = [
    "Idle", "Hosting", "Working", "Training in Progress",
    "Work Break", "Resting", "Mining", "Farming",
]


def _is_known_status(s: str | None) -> bool:
    return s is not None and s in KNOWN_STATUSES


def parse_status(text: str) -> str | None:
    text = text.strip()
    for s in KNOWN_STATUSES:
        if s.lower() in text.lower():
            return s
    t = re.sub(r'[^a-zA-Z\s]', '', text).lower().strip()
    if not t:
        return None
    if "dle" in t or "idl" in t or "ldle" in t:
        return "Idle"
    # "Work Break" — OCR produces Wook/Wark/Winrk + Rrea/Rreal/break/eak
    if re.search(r'w\w{0,4}k\s+\w{0,2}rea', t) or ("ork" in t and "eak" in t):
        return "Work Break"
    if re.search(r'w\w{0,3}rk\s+r', t) and "rea" in t:
        return "Work Break"
    if "ark" in t and ("rea" in t or "eal" in t):
        return "Work Break"
    if re.search(r'rain\w*\s+in\s+\w*ro', t) or "raining" in t:
        return "Training in Progress"
    if re.search(r'rain.*in.*pro', t):
        return "Training in Progress"
    if "inin" in t or "minin" in t:
        return "Mining"
    if "armin" in t:
        return "Farming"
    if "estin" in t:
        return "Resting"
    if "orkin" in t or ("ark" in t and "in" in t and "rea" not in t and "eal" not in t):
        return "Working"
    if "ostin" in t or "lostin" in t or "osting" in t or "nctin" in t:
        return "Hosting"
    return None


def parse_group(text: str) -> str | None:
    text = text.strip()
    if not text or "(Ungrouped" in text:
        return None
    # Strip leading and trailing OCR noise
    text = re.sub(r'^[\s\d|\\\/\[\]:_~*\-\'\"(){}#@&<>‘’“”]+', '', text).strip()
    text = re.sub(r"[\s▼▾↓vy~¥_|:;,.!?\d*#@&'\"‘’“”()]+$", "", text).strip()
    # Strip leading "Ww) v4 |" style garbage: anything before a pipe followed by a word
    text = re.sub(r'^.*\|\s*', '', text).strip()
    # Strip trailing short OCR artifacts (dropdown arrows, noise)
    text = re.sub(r'\s+\S{1,3}$', '', text).strip()
    if text.upper() == text and len(text) > 3 and not any(c.islower() for c in text):
        return None
    # Reject if it looks like OCR garbage (e.g. "ee LEVEL", "re")
    words = text.split()
    if all(len(w) <= 2 for w in words):
        return None
    if any(w.isupper() and len(w) >= 4 for w in words) and not any(c.islower() for c in text.replace(' ', '')):
        return None
    return text if text else None


def extract_card_text(card_img: np.ndarray) -> CardText:
    from detect_cards import crop_region

    # Name: white text — try multiple thresholds and pick best result
    name_img = crop_region(card_img, "name")
    name_candidates = []
    for t in [90, 100, 110, 120, 130]:
        name_candidates.append(parse_name(ocr_region(name_img, psm=7, threshold=t)))
    name_candidates.append(parse_name(ocr_region(name_img, psm=7, threshold=120, use_red=True)))
    scored = [(c, _score_name(c)) for c in name_candidates]
    name, best_score = max(scored, key=lambda x: x[1])
    for cand, sc in scored:
        if sc >= 10 and cand != name and name.startswith(cand + ' '):
            extra = name[len(cand):].strip()
            if extra and not re.match(r'^(VIII|VII|VI|IX|IV|V|III|II|X|I)$', extra):
                name = cand
                break
    # If best name has a short leading word (1-2 chars) that looks like noise,
    # prefer a candidate that matches the rest
    best_words = name.split()
    if len(best_words) >= 3 and len(best_words[0]) <= 2:
        tail = ' '.join(best_words[1:])
        for cand, sc in scored:
            if sc >= 10 and cand == tail:
                name = cand
                break

    # Cross-threshold Roman numeral recovery: if any candidate produced a
    # Roman suffix with a matching base name, adopt it via majority vote
    _ROMAN_RE = re.compile(r'\s+(VIII|VII|VI|IX|IV|V|III|II|X|I)$')
    rm = _ROMAN_RE.search(name)
    name_base = name[:rm.start()] if rm else name
    roman_votes: list[str] = []
    for cand, _ in scored:
        cm = _ROMAN_RE.search(cand)
        if not cm:
            continue
        cand_base = cand[:cm.start()]
        if cand_base == name_base or (len(name_base) >= 4 and cand_base.endswith(name_base)):
            roman_votes.append(cm.group(1))
    if roman_votes:
        from collections import Counter
        top_roman, top_count = Counter(roman_votes).most_common(1)[0]
        current = rm.group(1) if rm else None
        if not current:
            name = name_base + ' ' + top_roman
        elif top_count > roman_votes.count(current):
            name = name_base + ' ' + top_roman

    # Level/class/clan: purple text has poor grayscale contrast but high R channel.
    level_img = crop_region(card_img, "level_line")
    level_data_gray = parse_level_line(ocr_region(level_img, psm=7, threshold=65))
    level_data_red = parse_level_line(ocr_region(level_img, psm=7, threshold=100, use_red=True))
    level_data = _merge_level_data(level_data_gray, level_data_red)
    # Digit-only OCR on tight level crop — more reliable than regex on garbled text
    digit_level = extract_level_number(level_img)
    if digit_level is not None:
        level_data["level"] = digit_level

    status_img = crop_region(card_img, "status")
    # Status text can be white (Idle) or golden (Work Break). Try multiple thresholds.
    status_attempts = [
        ocr_region(status_img, psm=7, threshold=170, use_red=True),
        ocr_region(status_img, psm=7, threshold=160),
        ocr_region(status_img, psm=7, threshold=180),
    ]
    status = None
    for raw in status_attempts:
        s = parse_status(raw)
        if _is_known_status(s):
            status = s
            break
    if not status:
        for raw in status_attempts:
            s = parse_status(raw)
            if s:
                status = s
                break

    group_img = crop_region(card_img, "group")
    group = parse_group(ocr_region(group_img, psm=7, threshold=90))

    return CardText(
        name=name,
        level=level_data["level"],
        class_name=level_data["class_name"],
        clan=level_data["clan"],
        title=level_data["title"],
        status=status,
        group=group,
    )
