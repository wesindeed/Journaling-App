"""Renders one self-contained HTML file (no network, no CDN) from build_dashboard_data()."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("dashboard_template.html")


def render(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload, 1)
