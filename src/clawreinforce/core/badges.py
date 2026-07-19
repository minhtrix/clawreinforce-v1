from __future__ import annotations

from html import escape


def badge_svg(scope: str, pass_rate: float, *, gpt56: bool = False) -> str:
    label = "GPT-5.6 verified" if gpt56 else "skill verified"
    value = f"{scope} · {pass_rate:.0%}"
    left = max(100, len(label) * 7 + 18)
    right = max(110, len(value) * 7 + 18)
    total = left + right
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="28" role="img" aria-label="{escape(label)}: {escape(value)}">
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-opacity=".12"/></linearGradient>
<clipPath id="r"><rect width="{total}" height="28" rx="6"/></clipPath>
<g clip-path="url(#r)"><rect width="{left}" height="28" fill="#17191f"/><rect x="{left}" width="{right}" height="28" fill="#6d5dfc"/><rect width="{total}" height="28" fill="url(#s)"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana, sans-serif" font-size="11" font-weight="600"><text x="{left / 2}" y="18">{escape(label)}</text><text x="{left + right / 2}" y="18">{escape(value)}</text></g>
</svg>"""

