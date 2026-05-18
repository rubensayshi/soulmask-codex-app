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


def ocr_region(img: np.ndarray, psm: int = 7, threshold: int = 70, use_red: bool = False) -> str:
    processed = preprocess_for_ocr(img, threshold=threshold, use_red=use_red)
    config = f"--psm {psm} --oem 3"
    text = pytesseract.image_to_string(processed, config=config)
    return text.strip()


def parse_name(text: str) -> str:
    # Strip leading OCR artifacts and punctuation
    text = re.sub(r'^[\u25c6\u25c7\u2666<>\[\]\u00a9\u00ae\u00b0\u2022\u00b7&@#%~*\-_\d\s\'\"\u2018\u2019\u201c\u201d]+', '', text)
    text = re.sub(r'^[a-z&@#~*\-]\s+', '', text)
    text = re.sub(r'^x[a-z]?\s+', '', text, flags=re.IGNORECASE)
    # OCR "|" is often "I"; treat as I when space-separated, else as space
    text = re.sub(r'(?<=\s)\|(?=\s)', 'I', text)
    text = re.sub(r'(?<=\S)\|(?=V)', ' I', text)
    text = re.sub(r'[|\u00ae\u00ab\u00bb\u00a9]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Strip trailing non-alnum garbage before numeral normalization
    text = re.sub(r'[<>\[\]{}()*&@#%]+$', '', text).strip()

    # Normalize roman numerals: OCR produces "VU"->VII, "VILL"->VIII, "VIe"->VI,
    # "ll"/"Il"->II, "VL"->VI, "VIL"->VII, "lll"->III, trailing "l"->"I"
    text = re.sub(r'(?<=[a-z])[lI]{2,3}(?=[\s<>\[\]{}()*&@#%]|$)', lambda m: ' ' + 'I' * len(m.group()), text)
    text = re.sub(r'\s+[lI]{2,3}(?=[\s<>\[\]{}()*&@#%]|$)', lambda m: ' ' + 'I' * len(m.group().strip()), text)
    text = re.sub(r'(?<=[a-z])l(?=\s|$)', ' I', text)
    text = re.sub(r'VILL\b', 'VIII', text)
    text = re.sub(r'VIL\b', 'VII', text)
    text = re.sub(r'VUS\b', 'VII', text)
    text = re.sub(r'VU\b', 'VII', text)
    text = re.sub(r'Vie\b', 'VI', text)
    text = re.sub(r'VL\b', 'VI', text)
    text = re.sub(r'\s+(V?I{0,3})L(?=["\x27\u201c\u201d\u2018\u2019\s]|$)', lambda m: ' ' + m.group(1) + 'I', text)
    text = re.sub(r'["\x27\u201c\u201d\u2018\u2019]$', '', text).strip()

    # Split stuck-together name+numeral: "MehVI"->"Meh VI", "MentorIII"->"Mentor III"
    text = re.sub(r'([a-z])(VIII|VII|VI|IV|III|II|I)(?=\s|$)', lambda m: m.group(1) + ' ' + m.group(2), text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Extract trailing roman numeral (I-VIII) before stripping garbage
    roman_suffix = ""
    rm = re.search(r'\s+(VIII|VII|VI|IV|V|III|II|I)(?:\s|$)', text)
    if rm:
        roman_suffix = " " + rm.group(1)
        text = text[:rm.start()]
    # Strip trailing garbage
    text = re.sub(r'\s+[A-Za-z]*\s*\d+\s*[A-Za-z]*\s*$', '', text)
    text = re.sub(r'\s+[^\w\s].*$', '', text)
    text = re.sub(r'\s+[&@#<>\[\]\u00a9\u00ae\u00b0\u2022\u00b7\-_|:;,.!?\d]+$', '', text)
    if not re.search(r'\s+[IVXL]{1,5}$', text):
        text = re.sub(r'\s+\S{1,2}$', '', text)
    text = re.sub(r'[&@#\d\s.,:;!?]+$', '', text)
    return (text + roman_suffix).strip()


KNOWN_CLANS = ["Flint", "Long", "Fang", "Claw", "Wolf", "Horn", "Outcast"]

_CLAN_MAP = {
    "flint": "Flint", "iint": "Flint", "ilint": "Flint", "mint": "Flint",
    "lint": "Flint", "fint": "Flint", "flinlt": "Flint", "llint": "Flint",
    "ulint": "Flint", "illint": "Flint", "flintg": "Flint", "itinl": "Flint",
    "llmt": "Flint", "i lint": "Flint", "fi": "Flint",
    "llint liibe": "Flint", "llint lnbe": "Flint", "llint i be": "Flint",
    "llint lii": "Flint", "iint tibe": "Flint", "llmt tibe": "Flint",
    "flint lii": "Flint",
    "long": "Long", "lang": "Long", "iane": "Long", "iang": "Long",
    "ianp": "Long", "lanp": "Long", "lange": "Long",
    "lang lhibe": "Long",
    "fang": "Fang", "fanpg": "Fang", "fanp": "Fang",
    "claw": "Claw", "ciaw": "Claw",
    "wolf": "Wolf", "wolt": "Wolf", "woll": "Wolf",
    "horn": "Horn", "hom": "Horn",
    "outcast": "Outcast", "oulcast": "Outcast", "oulcasl": "Outcast",
    "outcasl": "Outcast", "0utcast": "Outcast",
}


def _normalize_clan(raw: str) -> str:
    key = raw.lower().strip()
    if key in _CLAN_MAP:
        return _CLAN_MAP[key]
    # Try first word only (multi-word OCR artifacts)
    first = key.split()[0] if key else ""
    if first in _CLAN_MAP:
        return _CLAN_MAP[first]
    # Fuzzy fallback: check if any known clan is a substring
    for clan in KNOWN_CLANS:
        if clan.lower() in key or key in clan.lower():
            return clan
    # Try first word fuzzy
    for clan in KNOWN_CLANS:
        if clan.lower() in first or first in clan.lower():
            return clan
    return raw


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

    # Extract level: LV.32  (OCR misreads L→1/I, V→¥, or drops prefix)
    level_match = re.search(r'(?:^|(?<=[\s|]))(?:[1lIL])?[Vv¥]\.?\s*(\d{1,3})(?=[\s).>]|$)', text)
    if not level_match:
        # Bare leading digits: "33 Skilled Guard" (1+ spaces before alpha)
        level_match = re.match(r'(\d{2,3})\s+(?=[A-Z])', text)
    if level_match:
        lv = int(level_match.group(1))
        if lv <= 100:
            result["level"] = lv
        elif lv > 100 and lv < 1000:
            # OCR prefix digit bled in: 359→59, 144→44
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
    "labore": "Laborer", "larborer": "Laborer",
    "wairior": "Warrior", "warri": "Warrior",
    "guaid": "Guard", "gnard": "Guard",
    "craltsman": "Craftsman", "craftman": "Craftsman",
}


def _normalize_class(raw: str) -> str:
    cleaned = re.sub(r'[|}{)\[\]0-9]', '', raw).strip()
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

    # Name: white text, needs higher threshold to avoid dark bg noise
    name_img = crop_region(card_img, "name")
    name = parse_name(ocr_region(name_img, psm=7, threshold=110))

    # Level/class/clan: purple text has poor grayscale contrast but high R channel.
    # Run OCR on both channels and merge results.
    level_img = crop_region(card_img, "level_line")
    level_data_gray = parse_level_line(ocr_region(level_img, psm=7, threshold=65))
    level_data_red = parse_level_line(ocr_region(level_img, psm=7, threshold=100, use_red=True))
    level_data = _merge_level_data(level_data_gray, level_data_red)

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
