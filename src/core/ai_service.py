"""Thin BYO-key wrapper around Anthropic's Messages API for AI Cards.

No key is ever bundled, proxied, or logged — callers pass the user's own
key straight through to Anthropic on every call, and nothing here persists
it (persistence + encryption is handled by utils/crypto.py + Settings).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import requests

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
AI_MODEL = "claude-sonnet-5"
REQUEST_TIMEOUT = 30
PERSONALIZATION_BATCH_SIZE = 15


class AIServiceError(Exception):
    """Raised for any failure calling the AI provider (auth, network, malformed output)."""


def _call_claude(api_key: str, system: str, user: str, max_tokens: int = 1024) -> str:
    if not api_key:
        raise AIServiceError("No API key configured. Add one in Settings.")

    try:
        response = requests.post(
            API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise AIServiceError("Request to Anthropic timed out. Check your connection and try again.")
    except requests.exceptions.RequestException as exc:
        raise AIServiceError(f"Network error contacting Anthropic: {exc}")

    if response.status_code == 401:
        raise AIServiceError("Invalid API key. Check the key saved in Settings.")
    if response.status_code == 429:
        raise AIServiceError("Rate limited by Anthropic. Wait a moment and try again.")
    if response.status_code != 200:
        raise AIServiceError(f"Anthropic API error ({response.status_code}): {response.text[:200]}")

    try:
        data = response.json()
        return "".join(
            block.get("text", "") for block in data.get("content", [])
            if block.get("type") == "text"
        )
    except (ValueError, KeyError) as exc:
        raise AIServiceError(f"Unexpected response from Anthropic: {exc}")


def _parse_json_response(text: str) -> Any:
    """Parse a JSON object/array out of a model response, tolerating markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIServiceError(f"AI response wasn't valid JSON: {exc}")


def validate_api_key(api_key: str) -> bool:
    """Minimal round trip to confirm the key works.

    Raises AIServiceError with a human-readable reason on failure.
    """
    _call_claude(api_key, system="Reply with exactly: OK", user="ping", max_tokens=8)
    return True


def generate_card_copy(product_description: str, api_key: str, style_names: List[str]) -> Dict[str, Any]:
    """Draft marketing-card copy from a plain-language product description.

    Returns a dict shaped like a card_creator_tab.py preset:
    {icon, tagline, description, features: [str, ...], price, old_price,
     price_note, style_name (one of style_names)}
    """
    if not product_description.strip():
        raise AIServiceError("Describe your product before generating.")
    if not style_names:
        raise AIServiceError("No card styles available.")

    system = (
        "You write concise, high-converting marketing card copy for a small business "
        "messaging app. Respond with ONLY a single JSON object, no markdown fences, "
        "matching exactly this shape: "
        '{"icon": "<single emoji>", "tagline": "<max 6 words>", '
        '"description": "<1-2 sentence pitch>", "features": ["<benefit>", ...3-5 items], '
        '"price": "<short price string or empty>", "old_price": "<short strikethrough '
        'price or empty>", "price_note": "<short note or empty>", '
        f'"style_name": "<exactly one of: {", ".join(style_names)}>"}}'
    )
    raw = _call_claude(api_key, system=system, user=product_description.strip(), max_tokens=600)
    data = _parse_json_response(raw)
    if not isinstance(data, dict):
        raise AIServiceError("AI response wasn't a JSON object.")
    if data.get("style_name") not in style_names:
        data["style_name"] = style_names[0]
    if not isinstance(data.get("features"), list):
        data["features"] = []
    return data


def generate_personalized_messages(
    card_summary: Dict[str, Any],
    contacts: List[Dict[str, Any]],
    api_key: str,
    channel: str,
) -> Dict[str, str]:
    """Generate a genuinely personalized outgoing message per contact.

    contacts: [{"key": str, "name": str, "phone": str, "email": str, "custom_fields": dict}]
    Returns {contact_key: message_text}. Contacts whose batch fails are simply
    absent from the result — callers must handle missing keys (e.g. skip + report).
    """
    if not contacts:
        return {}

    channel_guidance = (
        "Keep it under 300 characters, plain text, no markdown, WhatsApp-friendly tone."
        if channel == "whatsapp" else
        "Write 2-4 short plain-text paragraphs suitable for an email body (no HTML, no markdown)."
    )
    results: Dict[str, str] = {}

    for start in range(0, len(contacts), PERSONALIZATION_BATCH_SIZE):
        batch = contacts[start:start + PERSONALIZATION_BATCH_SIZE]
        system = (
            "You write personalized outreach messages for a product being promoted via "
            f"{channel}. {channel_guidance} Use each contact's name and any extra fields "
            "given to genuinely tailor the message (not just inserting their name) — "
            "reference their company/role/interest/etc. where provided. "
            "Respond with ONLY a JSON array, no markdown fences, shaped exactly like: "
            '[{"key": "<same key as input>", "message": "<personalized text>"}, ...]'
        )
        user = json.dumps({
            "product": {
                "tagline": card_summary.get("tagline", ""),
                "description": card_summary.get("description", ""),
                "features": card_summary.get("features", []),
            },
            "contacts": batch,
        })
        try:
            raw = _call_claude(api_key, system=system, user=user, max_tokens=2000)
            parsed = _parse_json_response(raw)
            if not isinstance(parsed, list):
                continue
            for item in parsed:
                key = item.get("key")
                message = item.get("message")
                if key and message:
                    results[key] = message
        except AIServiceError:
            continue

    return results
