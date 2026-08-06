"""Item 34 (sub-item 2): send-time recommendation heuristic."""

from __future__ import annotations

from src.core.send_time_advisor import recommend_send_window


def test_email_recommendation_has_a_window_reason_and_disclaimer():
    rec = recommend_send_window("email")
    assert rec.channel == "email"
    assert rec.window_text
    assert rec.reason
    assert "not based on your own send history" in rec.disclaimer


def test_whatsapp_recommendation_differs_from_email():
    email_rec = recommend_send_window("email")
    wa_rec = recommend_send_window("whatsapp")
    assert wa_rec.channel == "whatsapp"
    assert wa_rec.window_text != email_rec.window_text


def test_channel_lookup_is_case_insensitive():
    assert recommend_send_window("WhatsApp").channel == "whatsapp"
    assert recommend_send_window("Email").channel == "email"


def test_unknown_channel_falls_back_to_email_rather_than_raising():
    rec = recommend_send_window("sms")
    assert rec.channel == "email"
