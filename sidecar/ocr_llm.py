"""Card text extraction via Claude vision API."""
import base64
import json
import os

import anthropic
import cv2
import numpy as np

from ocr_text import CardText

_MODEL = "claude-haiku-4-5-20251001"


def _encode_card(card_img: np.ndarray) -> str:
    _, buf = cv2.imencode(".png", card_img)
    return base64.standard_b64encode(buf).decode("ascii")


def extract_cards_llm(card_images: list[np.ndarray]) -> list[CardText]:
    if not card_images:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY") or ""
    if not api_key:
        from dotenv import dotenv_values
        env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
        api_key = env.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment or .env")

    client = anthropic.Anthropic(api_key=api_key)

    content = []
    for i, img in enumerate(card_images):
        content.append({"type": "text", "text": f"Card {i}:"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": _encode_card(img)},
        })

    content.append({
        "type": "text",
        "text": (
            "These are tribesman cards from the game Soulmask. "
            "For each card, extract:\n"
            "- name: the tribesman's name (top-left, white text, may include a Roman numeral suffix like II, VII)\n"
            "- level: the number after 'LV.' (purple text line)\n"
            "- class_name: the class/profession text (e.g. 'Skilled Craftsman', 'Master Warrior') from the purple line\n"
            "- clan: the clan name inside angle brackets <...> (e.g. 'Flint Tribe' -> 'Flint', 'Long Fang Tribe' -> 'Long', 'Outcast')\n"
            "- title: any title text after the clan (e.g. 'Famous Trash', 'Weapon Master') from the purple line\n"
            "- status: the activity text on the right side (e.g. 'Idle', 'Working', 'Work Break', 'Training in Progress', 'Mining', 'Resting')\n"
            "- group: the group name in parentheses near the bottom-right (e.g. 'Workers', 'Trainers', 'Meh Fighters'). '(Ungrouped)' means null.\n\n"
            "Return ONLY a JSON array with one object per card, in order. "
            "Use null for any field you can't read. Example:\n"
            '[{"name": "Bad Guy", "level": 15, "class_name": "Skilled Craftsman", "clan": "Flint", "title": "Famous Trash", "status": null, "group": "Workers"}]'
        ),
    })

    resp = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )

    text = resp.content[0].text.strip()
    start = text.index("[")
    end = text.rindex("]") + 1
    raw = json.loads(text[start:end])

    results = []
    for entry in raw:
        results.append(CardText(
            name=entry.get("name") or "",
            level=entry.get("level"),
            class_name=entry.get("class_name"),
            clan=entry.get("clan"),
            title=entry.get("title"),
            status=entry.get("status"),
            group=entry.get("group"),
        ))
    return results
