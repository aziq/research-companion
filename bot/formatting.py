import html
import re

_SECTION_EMOJIS = {
    "main idea": "💡",
    "why it matters": "🎯",
    "category": "🏷",
    "suggested experiment": "🧪",
    "time required to explore": "⏱",
}


def format_analysis(analysis: str) -> str:
    """Convert markdown analysis text to Telegram HTML."""
    lines = analysis.split("\n")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue

        # Normalise: strip surrounding ** so "**Main idea:**" → "Main idea:"
        normalised = re.sub(r"^\*\*(.+?)\*\*$", r"\1", stripped)

        # Markdown headers: # / ## / ###
        header_match = re.match(r"^#{1,3}\s+(.*)", normalised)
        if header_match:
            raw = header_match.group(1).strip()
            lookup = re.sub(r"\*\*", "", raw).rstrip(":").strip().lower()
            emoji = _SECTION_EMOJIS.get(lookup, "")
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
            content = html.escape(clean)
            prefix = f"{emoji} " if emoji else ""
            out.append(f"\n{prefix}<b>{content}</b>")
            continue

        # Section headers ending with ":" (covers "Main idea:" and "**Main idea:**")
        if normalised.endswith(":") and len(normalised) < 60:
            lookup = normalised.rstrip(":").strip().lower()
            emoji = _SECTION_EMOJIS.get(lookup, "")
            label = html.escape(normalised)
            prefix = f"{emoji} " if emoji else ""
            out.append(f"\n{prefix}<b>{label}</b>")
            continue

        # Regular line: escape HTML, convert markdown bold, bullets
        escaped = html.escape(stripped)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        escaped = re.sub(r"^[\-\*]\s", "• ", escaped)
        out.append(escaped)

    return "\n".join(out).strip()
