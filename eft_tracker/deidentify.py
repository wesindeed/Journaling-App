"""Best-effort scrubbing before any text leaves the machine. Not a guarantee: review before sending."""
from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)")


def scrub(text: str, names: dict[str, str]) -> str:
    """names maps real name -> placeholder (e.g. {"Jane": "Partner A"}). Whole-word, case-insensitive."""
    for real, placeholder in sorted(names.items(), key=lambda kv: -len(kv[0])):
        if real.strip():
            text = re.sub(rf"\b{re.escape(real.strip())}\b", placeholder, text, flags=re.IGNORECASE)
    text = EMAIL.sub("[email]", text)
    return PHONE.sub("[phone]", text)
