"""
Item 34 (sub-item 2) of the multi-product generalization pass: a send-time
recommendation for Compose.

Deliberately NOT AI-driven and NOT based on any per-user historical data --
this app has no open/click tracking (a documented, known gap), so any
"send-time" claim beyond general industry best practice would be
fabricated. This is a plain, static heuristic, always shown with an
explicit disclaimer that it's general guidance, not a claim based on this
user's own send history.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SendTimeRecommendation:
    channel: str
    window_text: str
    reason: str
    disclaimer: str


# General, widely-cited industry best-practice windows (not this app's own
# measured data -- there is nothing in this app that measures open/click
# times per recipient). Deliberately broad, not a fake precise number.
_RECOMMENDATIONS = {
    "email": SendTimeRecommendation(
        channel="email",
        window_text="Tuesday–Thursday, 10am–12pm (recipient's local time)",
        reason="Widely-cited general best practice: mid-morning on a mid-week day "
               "tends to see higher open rates than Monday mornings, Friday "
               "afternoons, or weekends, when inboxes are more crowded.",
        disclaimer="This is a general industry heuristic, not based on your own "
                   "send history — this app doesn't yet track opens/clicks per "
                   "recipient to give you a personalized recommendation.",
    ),
    "whatsapp": SendTimeRecommendation(
        channel="whatsapp",
        window_text="Weekday mornings (9am–11am) or early evenings (6pm–8pm), "
                     "recipient's local time",
        reason="General best practice for personal messaging apps: business hours "
               "or just after work tend to get faster reads than late night or "
               "very early morning, when a message risks feeling intrusive.",
        disclaimer="This is a general industry heuristic, not based on your own "
                   "send history — this app doesn't yet track read times per "
                   "recipient to give you a personalized recommendation.",
    ),
}


def recommend_send_window(channel: str) -> SendTimeRecommendation:
    """Returns a general best-practice send-time window for `channel`
    ("email" or "whatsapp", case-insensitive). Falls back to the email
    recommendation for an unrecognized channel string rather than raising —
    this is advisory UI copy, not a hard gate on sending."""
    return _RECOMMENDATIONS.get(channel.lower().strip(), _RECOMMENDATIONS["email"])
