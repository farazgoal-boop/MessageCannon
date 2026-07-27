"""Item 15 of the Live Testing Findings pass (Round 2): premium onboarding
for the AI API key field in Settings -- a real "Get an API key →" link that
opens the correct provider's key-creation page in the default browser
(dynamic on the "AI provider" dropdown selection), a plain-language helper
line, and a pay-as-you-go/billing note.
"""

from __future__ import annotations

import customtkinter as ctk

import src.core.ai_service as ai_service


def test_key_creation_url_is_correct_per_provider():
    assert ai_service.key_creation_url("anthropic") == "https://console.anthropic.com/settings/keys"
    assert ai_service.key_creation_url("gemini") == "https://aistudio.google.com/apikey"
    # Unknown/legacy provider string falls back to Anthropic's page rather
    # than raising or returning an empty/broken URL.
    assert ai_service.key_creation_url("something-unknown") == ai_service.key_creation_url("anthropic")


def test_billing_note_is_real_text_per_provider():
    anthropic_note = ai_service.billing_note("anthropic")
    gemini_note = ai_service.billing_note("gemini")
    assert "pay-as-you-go" in anthropic_note.lower() or "billing" in anthropic_note.lower()
    assert "free tier" in gemini_note.lower()
    assert anthropic_note != gemini_note


def _find_button_by_text(widget, text):
    if isinstance(widget, ctk.CTkButton):
        try:
            if widget.cget("text") == text:
                return widget
        except Exception:
            pass
    for child in widget.winfo_children():
        found = _find_button_by_text(child, text)
        if found is not None:
            return found
    return None


def _all_label_text(widget) -> str:
    text = ""
    try:
        text += str(widget.cget("text"))
    except Exception:
        pass
    for child in widget.winfo_children():
        text += _all_label_text(child)
    return text


def test_get_api_key_button_opens_correct_provider_page(app, monkeypatch):
    """Real proof: clicking the actual button in the real Settings view
    calls webbrowser.open with the right URL for whichever provider is
    currently selected -- for both Anthropic and Gemini."""
    import src.ui.main_window as mw_mod

    opened_urls = []
    monkeypatch.setattr(mw_mod.webbrowser, "open", lambda url: opened_urls.append(url))

    original_provider = app._ai_provider.get()
    try:
        app._show_view("Settings")
        app.update()
        button = _find_button_by_text(app.view_containers["Settings"], "Get an API key →")
        assert button is not None, "expected a real 'Get an API key →' button in Settings"

        app._ai_provider.set("anthropic")
        button._command()
        assert opened_urls[-1] == "https://console.anthropic.com/settings/keys"

        app._ai_provider.set("gemini")
        button._command()
        assert opened_urls[-1] == "https://aistudio.google.com/apikey"
    finally:
        app._ai_provider.set(original_provider)


def test_helper_line_and_billing_note_are_present_in_settings(app):
    original_provider = app._ai_provider.get()
    try:
        app._show_view("Settings")
        app.update()
        page_text = _all_label_text(app.view_containers["Settings"])
        assert "create an account and generate a key" in page_text.lower()

        app._ai_provider.set("gemini")
        app._ai_billing_note_var.set(ai_service.billing_note("gemini"))
        app.update()
        assert "free tier" in app._ai_billing_note_var.get().lower()
    finally:
        app._ai_provider.set(original_provider)
        app._ai_billing_note_var.set(ai_service.billing_note(original_provider))


def test_provider_switch_updates_billing_note_live(app):
    """The billing note must actually refresh when the provider dropdown
    changes -- drives the real _on_provider_change callback via the
    dropdown's own stored command, not a simulated equivalent."""
    original_provider = app._ai_provider.get()
    try:
        app._show_view("Settings")
        app.update()

        app.ai_provider_menu._command("Anthropic Claude")
        app.update()
        assert app._ai_provider.get() == "anthropic"
        note_after_anthropic = app._ai_billing_note_var.get()
        assert note_after_anthropic == ai_service.billing_note("anthropic")

        app.ai_provider_menu._command("Google Gemini (free tier available)")
        app.update()
        assert app._ai_provider.get() == "gemini"
        note_after_gemini = app._ai_billing_note_var.get()
        assert note_after_gemini == ai_service.billing_note("gemini")
        assert note_after_gemini != note_after_anthropic
    finally:
        app.ai_provider_menu._command(ai_service.PROVIDER_LABELS.get(original_provider, "Anthropic Claude"))
        app.update()
