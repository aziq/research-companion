import os
from dotenv import load_dotenv

load_dotenv()

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if not _ANTHROPIC_KEY and not _OPENAI_KEY:
    raise EnvironmentError("Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")

_PROVIDER = "anthropic" if _ANTHROPIC_KEY else "openai"

if _PROVIDER == "anthropic":
    import anthropic
    client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
    _MODEL = "claude-haiku-4-5-20251001"
else:
    from openai import OpenAI
    client = OpenAI(api_key=_OPENAI_KEY)
    _MODEL = "gpt-4o-mini"

_PROMPT = """You are my personal AI research analyst.

Analyze the following content and return:

Main idea:
Why it matters:
Category:
Suggested experiment:
Time required to explore:

CONTENT:
{text}"""


def analyze(text: str) -> str:
    prompt = _PROMPT.format(text=text)
    if _PROVIDER == "anthropic":
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    else:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content


def analyze_image(b64: str, caption: str = "") -> str:
    """Describe and extract key info from a base64-encoded JPEG image."""
    prompt = "Extract and describe all text and key information visible in this image."
    if caption:
        prompt += f" Context provided: {caption}"

    if _PROVIDER == "anthropic":
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return resp.content[0].text
    else:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
        )
        return resp.choices[0].message.content
