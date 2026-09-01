"""Thin BYO-key wrapper around AI providers for AI Cards.

No key is ever bundled, proxied, or logged — callers pass the user's own
key straight through to the chosen provider on every call, and nothing here
persists it (persistence + encryption is handled by utils/crypto.py +
Settings).

Two providers, chosen per-call via `provider` ("anthropic" or "gemini"),
default "anthropic" for backward compatibility with settings saved before
this option existed:
- **Anthropic Claude** — api.anthropic.com. Key format: starts with
  `sk-ant-...`, from console.anthropic.com. Paid, no free tier.
- **Google Gemini** — generativelanguage.googleapis.com. Key format: a
  plain alphanumeric string (no fixed prefix), from
  aistudio.google.com/apikey. Has a genuine free tier (rate-limited, no
  card required) — added specifically so this feature is usable without a
  paid key, per explicit request.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MODEL = "claude-sonnet-5"

# Item 16 follow-up (Live Testing Findings, Round 2) -- two real model picks
# in a row, each "confirmed" against Google's own docs at the time, broke
# within the same session, which is itself the real lesson here (see the
# Settings "Gemini model" field added below for the actual fix to the root
# problem, not just this one symptom):
# 1. "gemini-2.0-flash" was hardcoded originally and is now a genuinely
#    SHUT DOWN model (Google's model docs, "Previous models" / "Shut down").
#    This was the real root cause of a fresh key always failing "Test key"
#    as "rate limited" even after waiting -- a real quota clears after a
#    wait; a request against a decommissioned model never does.
# 2. Switched to "gemini-2.5-flash-lite" (confirmed Stable, generous free
#    tier) -- but a REAL live test against a real key came back
#    `404 "This model models/gemini-2.5-flash-lite is no longer available
#    to new users"` within the hour. Confirmed via Google's deprecations
#    page: the whole 2.5 generation is closed to *new* API keys ahead of
#    its Oct 16, 2026 shutdown, even though existing users/keys can still
#    use it until then -- a distinction no amount of "is this model
#    deprecated" doc-reading surfaces, only a real request from a real new
#    key does.
# Now "gemini-3.1-flash-lite" -- GA since May 7, 2026 (not brand-new/
# preview), confirmed genuine free tier, no card required, no shutdown
# date announced as of this fix. Given the demonstrated real volatility
# above, treat this as the best current answer, not a permanent one.
GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

REQUEST_TIMEOUT = 30
PERSONALIZATION_BATCH_SIZE = 15

PROVIDERS = ("anthropic", "gemini")
PROVIDER_LABELS = {
    "anthropic": "Anthropic Claude",
    "gemini": "Google Gemini (free tier available)",
}

# Item 15 of the Live Testing Findings pass (Round 2): "premium onboarding"
# for the API key field -- a direct link to each provider's real key-
# creation page, plus a plain-language billing note, so the user never has
# to already know where to go get one.
PROVIDER_KEY_URLS = {
    "anthropic": "https://console.anthropic.com/settings/keys",
    "gemini": "https://aistudio.google.com/apikey",
}

PROVIDER_BILLING_NOTES = {
    "anthropic": "Anthropic API usage is typically pay-as-you-go -- you may need to add "
                 "billing/credits in the Anthropic console before a saved key will work.",
    "gemini": "Google Gemini has a genuine free tier for typical use (no card required); "
              "heavier use may require enabling billing in Google AI Studio.",
}


def key_creation_url(provider: str) -> str:
    """The real key-creation page for `provider`, defaulting to Anthropic's
    if an unknown/legacy provider string is passed."""
    return PROVIDER_KEY_URLS.get(provider, PROVIDER_KEY_URLS["anthropic"])


def billing_note(provider: str) -> str:
    return PROVIDER_BILLING_NOTES.get(provider, PROVIDER_BILLING_NOTES["anthropic"])


class AIServiceError(Exception):
    """Raised for any failure calling the AI provider (auth, network, malformed output)."""


def _call_anthropic(api_key: str, system: str, user: str, max_tokens: int) -> str:
    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
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


def _call_gemini(api_key: str, system: str, user: str, max_tokens: int) -> str:
    try:
        response = requests.post(
            GEMINI_API_URL,
            params={"key": api_key},
            headers={"content-type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise AIServiceError("Request to Google Gemini timed out. Check your connection and try again.")
    except requests.exceptions.RequestException as exc:
        raise AIServiceError(f"Network error contacting Google Gemini: {exc}")

    if response.status_code in (400, 401, 403):
        # Gemini reports a bad/missing key as 400 or 403, not 401 — check the
        # body for the specific reason rather than assuming which one it is.
        body_lower = response.text.lower()
        if "api key" in body_lower or "api_key" in body_lower:
            raise AIServiceError("Invalid API key. Check the key saved in Settings.")
        raise AIServiceError(f"Google Gemini API error ({response.status_code}): {response.text[:200]}")
    if response.status_code == 429:
        # Previously a generic "wait a moment" message regardless of what
        # Google actually said -- real bug found while investigating a user
        # report of persistent 429s that didn't clear after waiting: this
        # discarded Gemini's own JSON error body, which for a real quota
        # error includes a specific `error.status` (e.g. "RESOURCE_EXHAUSTED")
        # and a real `error.message` naming which quota was hit. Surfacing
        # that now instead of guessing, so a genuine per-minute/per-day
        # limit reads differently from (and is now distinguishable from) any
        # other 429-shaped failure.
        detail = ""
        try:
            error_body = response.json().get("error", {})
            detail = error_body.get("message", "")
        except (ValueError, AttributeError):
            pass
        if detail:
            raise AIServiceError(f"Rate limited by Google Gemini: {detail}")
        raise AIServiceError("Rate limited by Google Gemini. Wait a moment and try again.")
    if response.status_code != 200:
        raise AIServiceError(f"Google Gemini API error ({response.status_code}): {response.text[:200]}")

    try:
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason")
            if reason:
                raise AIServiceError(f"Google Gemini blocked this request: {reason}")
            raise AIServiceError("Google Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
    except (ValueError, KeyError, IndexError) as exc:
        raise AIServiceError(f"Unexpected response from Google Gemini: {exc}")


def _call_ai(provider: str, api_key: str, system: str, user: str, max_tokens: int = 1024) -> str:
    if not api_key:
        provider_name = PROVIDER_LABELS.get(provider, provider)
        raise AIServiceError(f"No {provider_name} API key configured. Add one in Settings.")
    if provider == "gemini":
        return _call_gemini(api_key, system, user, max_tokens)
    if provider == "anthropic":
        return _call_anthropic(api_key, system, user, max_tokens)
    raise AIServiceError(f"Unknown AI provider: {provider!r}")


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


def validate_api_key(api_key: str, provider: str = "anthropic") -> bool:
    """Minimal round trip to confirm the key works.

    Raises AIServiceError with a human-readable reason on failure.
    """
    _call_ai(provider, api_key, system="Reply with exactly: OK", user="ping", max_tokens=8)
    return True


def generate_card_copy(product_description: str, api_key: str, style_names: List[str],
                        provider: str = "anthropic") -> Dict[str, Any]:
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
    raw = _call_ai(provider, api_key, system=system, user=product_description.strip(), max_tokens=600)
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
    provider: str = "anthropic",
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
            raw = _call_ai(provider, api_key, system=system, user=user, max_tokens=2000)
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


def generate_message_variations(
    brief: str, channel: str, api_key: str, count: int = 3,
    sample_variables: Optional[List[str]] = None, provider: str = "anthropic",
) -> List[Dict[str, str]]:
    """Draft `count` distinct outgoing-message variations from a short brief
    (product, tone, goal) — never a single forced output. Returns
    [{"label": str, "text": str, "subject": str}, ...]; "subject" is only
    meaningful when channel == "email" (empty string otherwise).

    Uses the app's own {variable} syntax (e.g. {name}, {amount}, or any
    custom column name) so results drop straight into the composer and
    substitute against real contacts completely unchanged — the AI is told
    exactly which variables are available so it doesn't invent ones that
    don't exist in the imported contact data.
    """
    if not brief.strip():
        raise AIServiceError("Describe what you want to say before generating.")

    available_vars = ", ".join(f"{{{v}}}" for v in (sample_variables or ["name"]))
    channel_guidance = (
        "WhatsApp message: short (under ~300 characters), casual, plain text, "
        "emoji used sparingly and naturally, no markdown."
        if channel == "whatsapp" else
        "Email: a short subject line plus a 2-4 paragraph plain-text body, "
        "professional but warm, no markdown, no HTML."
    )

    system = (
        f"You write outgoing marketing/notification messages for a small business "
        f"messaging app. Generate exactly {count} genuinely DIFFERENT variations "
        f"(different angle, tone, or structure each — not just reworded copies) for "
        f"this brief. {channel_guidance} "
        f"Personalize using ONLY these variables, exactly as written (do not invent "
        f"others): {available_vars}. "
        "Respond with ONLY a JSON array, no markdown fences, shaped exactly like: "
        '[{"label": "<3-word style label, e.g. \'Friendly & Casual\'>", '
        '"text": "<the message, with {variables} inline>", '
        '"subject": "<email subject line, or empty string if not email>"}, ...]'
    )
    raw = _call_ai(provider, api_key, system=system, user=brief.strip(), max_tokens=1500)
    data = _parse_json_response(raw)
    if not isinstance(data, list) or not data:
        raise AIServiceError("AI response wasn't a JSON array of variations.")
    return [
        {
            "label": str(item.get("label", f"Variation {i + 1}")),
            "text": str(item.get("text", "")),
            "subject": str(item.get("subject", "")),
        }
        for i, item in enumerate(data) if item.get("text")
    ]


# ── Item 34 of the multi-product generalization pass: push the AI features
# further -- subject-line optimizer, A/B variant generation, and a real,
# data-grounded campaign performance summary. (Item 34's other two asks --
# send-time recommendation and contact-list quality checks -- are pure
# heuristics with no AI call involved; see core/send_time_advisor.py and
# core/contact_quality.py respectively.) ──────────────────────────────────

def generate_subject_lines(
    email_body: str, api_key: str, count: int = 3, provider: str = "anthropic",
) -> List[Dict[str, str]]:
    """Given an already-drafted email body, suggest `count` alternative
    subject lines optimized for open rates, each with a short rationale
    (e.g. urgency, curiosity, personalization) -- building on the existing
    spam-word/subject-length warnings, which only ever flag problems, never
    suggest a better line. Returns [{"subject": str, "rationale": str}, ...].
    """
    if not email_body.strip():
        raise AIServiceError("Write the email body before optimizing the subject line.")

    system = (
        f"You are an email marketing copywriter. Given an email body, suggest exactly "
        f"{count} alternative SUBJECT LINES optimized for open rates -- each using a "
        "genuinely different psychological angle (e.g. urgency, curiosity, "
        "personalization, benefit-led, social proof) -- not minor rewordings of the "
        "same angle. Keep each subject line under 60 characters. If the body contains "
        "{variable} tokens (e.g. {name}), you may reuse them in a subject line exactly "
        "as written. Respond with ONLY a JSON array, no markdown fences, shaped exactly "
        'like: [{"subject": "<subject line>", "rationale": "<one short sentence on why '
        'this angle might perform well>"}, ...]'
    )
    raw = _call_ai(provider, api_key, system=system, user=email_body.strip(), max_tokens=500)
    data = _parse_json_response(raw)
    if not isinstance(data, list) or not data:
        raise AIServiceError("AI response wasn't a JSON array of subject lines.")
    return [
        {"subject": str(item.get("subject", "")), "rationale": str(item.get("rationale", ""))}
        for item in data if item.get("subject")
    ]


def generate_ab_variants(
    brief: str, channel: str, api_key: str,
    angle_a: str = "benefit-focused", angle_b: str = "urgency-focused",
    sample_variables: Optional[List[str]] = None, provider: str = "anthropic",
) -> List[Dict[str, str]]:
    """Generates exactly 2 messages from the SAME brief, deliberately
    written from 2 different, explicitly-named persuasion angles -- for a
    genuine A/B test of messaging strategy, not just a cosmetic reword of
    one idea (which is what generate_message_variations' generic "3
    different variations" can end up producing if left unconstrained).
    Returns [{"angle": angle_a, "text": ..., "subject": ...},
             {"angle": angle_b, "text": ..., "subject": ...}].
    """
    if not brief.strip():
        raise AIServiceError("Describe what you want to say before generating.")

    available_vars = ", ".join(f"{{{v}}}" for v in (sample_variables or ["name"]))
    channel_guidance = (
        "WhatsApp message: short (under ~300 characters), casual, plain text, no markdown."
        if channel == "whatsapp" else
        "Email: a short subject line plus a 2-4 paragraph plain-text body, no markdown, no HTML."
    )
    system = (
        "You write outgoing marketing/notification messages for a small business "
        "messaging app, for a real A/B test of MESSAGING STRATEGY (not tone or wording). "
        f"Write exactly 2 messages for the SAME brief: one written from a "
        f"\"{angle_a}\" angle, and one written from a \"{angle_b}\" angle -- the two must "
        "differ in actual persuasion strategy (what's emphasized, what's led with), not "
        f"just phrasing. {channel_guidance} Personalize using ONLY these variables, "
        f"exactly as written (do not invent others): {available_vars}. "
        "Respond with ONLY a JSON array of exactly 2 items, no markdown fences, shaped "
        f'exactly like: [{{"angle": "{angle_a}", "text": "<message, {{variables}} inline>", '
        f'"subject": "<email subject or empty string if not email>"}}, '
        f'{{"angle": "{angle_b}", "text": "...", "subject": "..."}}]'
    )
    raw = _call_ai(provider, api_key, system=system, user=brief.strip(), max_tokens=1200)
    data = _parse_json_response(raw)
    if not isinstance(data, list) or not data:
        raise AIServiceError("AI response wasn't a JSON array of A/B variants.")
    return [
        {
            "angle": str(item.get("angle", angle_a if i == 0 else angle_b)),
            "text": str(item.get("text", "")),
            "subject": str(item.get("subject", "")),
        }
        for i, item in enumerate(data) if item.get("text")
    ]


def summarize_campaign_performance(
    stats: Dict[str, Any], api_key: str, provider: str = "anthropic",
) -> str:
    """A plain-language summary + 1-2 concrete suggestions for the NEXT
    campaign, grounded entirely in this app's own real, already-logged
    send/bounce data for the campaign that just finished -- `stats` must
    come from the real DB (e.g. db_manager.get_campaign_bounce_stats plus
    the campaign row itself), never invented numbers. Callers are
    responsible for only calling this with real data."""
    required = {"campaign_name", "total_sent", "failed", "bounced"}
    missing = required - stats.keys()
    if missing:
        raise AIServiceError(f"Missing real campaign stats: {', '.join(sorted(missing))}")

    # The report dialog itself already frames "Delivered" as an assumption
    # until a real bounce check runs. The AI summary must use the SAME honest
    # framing -- an earlier version of this prompt let the model write things
    # like "every email was successfully delivered" and "reached all 20
    # recipients", which the data does not support (SMTP "250 OK" is
    # acceptance by the mail server, not proof of inbox delivery; a bounce
    # count of 0 means none have arrived YET, not that delivery is confirmed).
    bounce_status = stats.get("bounce_check_status", "not yet checked for real bounces")
    system = (
        "You are a plain-spoken marketing analyst reviewing ONE real completed email/"
        "WhatsApp campaign for a small business owner. You are given real, already-"
        "measured numbers for this campaign -- do not invent, estimate, or assume any "
        "number not given to you.\n\n"
        "CRITICAL - how to talk about these numbers honestly:\n"
        "- 'total_sent' means the mail server ACCEPTED the message for sending. It is "
        "NOT proof the message reached anyone's inbox.\n"
        "- 'bounced' is the count of bounce/failure notices received SO FAR. A value of "
        "0 means none have come back yet -- bounces can arrive hours later -- it does "
        "NOT mean delivery is confirmed.\n"
        "- NEVER write that messages were 'delivered', 'landed in inboxes', 'reached "
        "all recipients', or 'successfully delivered'. Say 'sent' or 'accepted for "
        "sending'. If you mention delivery at all, call it unconfirmed / an assumption "
        "and suggest re-checking for bounces in a few hours.\n\n"
        "Write a short (3-5 sentence) plain-language summary of how the campaign went "
        "using that honest framing, followed by exactly 1-2 concrete, specific "
        "suggestions for the next campaign based on these real numbers. No markdown, "
        "no headers, plain text only."
    )
    payload = dict(stats)
    payload.setdefault("note", (
        "total_sent = server-accepted, not confirmed delivered. "
        f"bounce status: {bounce_status}."))
    raw = _call_ai(provider, api_key, system=system, user=json.dumps(payload), max_tokens=500)
    text = raw.strip()
    if not text:
        raise AIServiceError("AI returned an empty summary.")

    # App-controlled caveat, prepended regardless of what the model wrote, so
    # the honest framing is guaranteed even if a model ignores the prompt.
    caveat = ("Note: \"sent\" means the mail server accepted the message — it is not "
              "confirmed inbox delivery, and bounces can still arrive later. Re-check "
              "for bounces in a few hours if you need confirmation.\n\n")
    return caveat + text
