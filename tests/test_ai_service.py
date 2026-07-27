"""Coverage for the multi-provider AI abstraction added in Item 3 of the
Live Testing Findings pass: Anthropic Claude was previously the only
option; Google Gemini (genuine free tier, no card required) was added
alongside it, chosen per-call via a `provider` argument that threads
through every public function in this module and every real call site
(Settings "Test key", Compose "Generate with AI", Card Creator AI
generation/personalization)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core import ai_service
from src.core.ai_service import AIServiceError


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or str(json_data)

    def json(self):
        return self._json_data


def test_missing_key_names_the_provider(monkeypatch):
    with pytest.raises(AIServiceError, match="Google Gemini"):
        ai_service._call_ai("gemini", "", "sys", "user")
    with pytest.raises(AIServiceError, match="Anthropic Claude"):
        ai_service._call_ai("anthropic", "", "sys", "user")


def test_unknown_provider_raises():
    with pytest.raises(AIServiceError, match="Unknown AI provider"):
        ai_service._call_ai("some-other-provider", "key", "sys", "user")


def test_anthropic_dispatch_hits_the_right_url_and_headers(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(200, {"content": [{"type": "text", "text": "hi"}]})

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    result = ai_service._call_ai("anthropic", "sk-ant-real", "sys", "user")

    assert result == "hi"
    assert captured["url"] == ai_service.ANTHROPIC_API_URL
    assert captured["headers"]["x-api-key"] == "sk-ant-real"
    assert captured["json"]["model"] == ai_service.ANTHROPIC_MODEL


def test_gemini_dispatch_hits_the_right_url_with_key_as_param(monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None, **kw):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        return _FakeResponse(200, {
            "candidates": [{"content": {"parts": [{"text": "hello from gemini"}]}}]
        })

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    result = ai_service._call_ai("gemini", "some-gemini-key", "sys", "user")

    assert result == "hello from gemini"
    assert captured["url"] == ai_service.GEMINI_API_URL
    assert captured["params"] == {"key": "some-gemini-key"}
    assert captured["json"]["system_instruction"]["parts"][0]["text"] == "sys"


def test_gemini_bad_key_gives_real_invalid_key_message(monkeypatch):
    def fake_post(*a, **k):
        return _FakeResponse(400, {"error": {"message": "API key not valid"}},
                              text='{"error": {"message": "API key not valid"}}')

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    with pytest.raises(AIServiceError, match="Invalid API key"):
        ai_service._call_ai("gemini", "bad-key", "sys", "user")


def test_gemini_rate_limit_gives_real_message(monkeypatch):
    def fake_post(*a, **k):
        return _FakeResponse(429, {}, text="rate limited")

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    with pytest.raises(AIServiceError, match="Rate limited by Google Gemini"):
        ai_service._call_ai("gemini", "a-key", "sys", "user")


def test_gemini_rate_limit_surfaces_real_quota_detail_when_present(monkeypatch):
    """Real bug found while investigating a user report of persistent 429s
    that never cleared even after waiting: the old code discarded Gemini's
    own JSON error body on a 429, always showing the same generic "wait a
    moment" text regardless of what Google actually said. A real quota
    error's body names the specific quota hit -- that must now surface."""
    def fake_post(*a, **k):
        return _FakeResponse(
            429,
            {"error": {"status": "RESOURCE_EXHAUSTED",
                       "message": "You exceeded your current quota, please check your plan "
                                  "and billing details."}},
            text='{"error": {"message": "You exceeded your current quota"}}',
        )

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    with pytest.raises(AIServiceError, match="exceeded your current quota"):
        ai_service._call_ai("gemini", "a-key", "sys", "user")


def test_gemini_model_is_not_a_model_confirmed_broken_this_session():
    """gemini-2.0-flash was confirmed shut down (Google's own model docs).
    gemini-2.5-flash-lite was the first fix, but a real live test against a
    real key came back a 404 "no longer available to new users" within the
    hour -- Google closes new-key access to a model generation ahead of its
    actual shutdown date, a distinction no amount of "is this deprecated"
    doc-reading surfaces on its own. Locks in the real, currently-working
    model (gemini-3.1-flash-lite, GA since May 2026) and guards against
    silently regressing to either known-broken value."""
    assert ai_service.GEMINI_MODEL == "gemini-3.1-flash-lite"
    assert ai_service.GEMINI_MODEL not in ("gemini-2.0-flash", "gemini-2.5-flash-lite")


def test_gemini_no_candidates_reports_block_reason(monkeypatch):
    def fake_post(*a, **k):
        return _FakeResponse(200, {"promptFeedback": {"blockReason": "SAFETY"}})

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    with pytest.raises(AIServiceError, match="SAFETY"):
        ai_service._call_ai("gemini", "a-key", "sys", "user")


@pytest.mark.parametrize("fn,args,expected_provider", [
    (ai_service.validate_api_key, ("key",), "gemini"),
    (ai_service.generate_message_variations, ("a brief", "whatsapp", "key"), "gemini"),
])
def test_public_functions_thread_provider_through(monkeypatch, fn, args, expected_provider):
    captured = {}

    def fake_call_ai(provider, api_key, system, user, max_tokens=1024):
        captured["provider"] = provider
        if fn is ai_service.validate_api_key:
            return "OK"
        return '[{"label": "A", "text": "hi {name}", "subject": ""}]'

    monkeypatch.setattr(ai_service, "_call_ai", fake_call_ai)
    fn(*args, provider="gemini")
    assert captured["provider"] == "gemini"


def test_generate_card_copy_threads_provider_through(monkeypatch):
    captured = {}

    def fake_call_ai(provider, api_key, system, user, max_tokens=1024):
        captured["provider"] = provider
        return '{"icon": "🎉", "tagline": "t", "description": "d", "features": [], ' \
               '"price": "", "old_price": "", "price_note": "", "style_name": "Dark"}'

    monkeypatch.setattr(ai_service, "_call_ai", fake_call_ai)
    ai_service.generate_card_copy("a product", "key", ["Dark"], provider="gemini")
    assert captured["provider"] == "gemini"


def test_default_provider_is_anthropic_for_backward_compatibility(monkeypatch):
    captured = {}

    def fake_call_ai(provider, api_key, system, user, max_tokens=1024):
        captured["provider"] = provider
        return "OK"

    monkeypatch.setattr(ai_service, "_call_ai", fake_call_ai)
    ai_service.validate_api_key("key")  # no provider arg
    assert captured["provider"] == "anthropic"
