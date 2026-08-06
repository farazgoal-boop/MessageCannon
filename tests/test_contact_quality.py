"""Item 34 (sub-item 4): contact-list quality check (role-based addresses)."""

from __future__ import annotations

from src.core.contact_quality import flag_low_quality_emails, is_role_based_address


def test_is_role_based_address_matches_common_prefixes():
    assert is_role_based_address("info@example.com")
    assert is_role_based_address("NoReply@example.com")
    assert is_role_based_address("support@example.co.uk")


def test_is_role_based_address_does_not_match_a_real_looking_name():
    assert not is_role_based_address("sarah.jones@example.com")
    assert not is_role_based_address("mfaraz@example.com")


def test_is_role_based_address_handles_bad_input_without_raising():
    assert not is_role_based_address("")
    assert not is_role_based_address(None)
    assert not is_role_based_address("not-an-email")


def test_flag_low_quality_emails_flags_only_role_based_ones():
    emails = ["sarah@example.com", "info@example.com", "noreply@example.com"]
    flags = flag_low_quality_emails(emails)
    flagged = {f.email for f in flags}
    assert flagged == {"info@example.com", "noreply@example.com"}
    assert all("lower open/reply" in f.reason for f in flags)


def test_flag_low_quality_emails_deduplicates_case_insensitively():
    emails = ["info@example.com", "INFO@example.com", "Info@Example.com"]
    flags = flag_low_quality_emails(emails)
    assert len(flags) == 1


def test_flag_low_quality_emails_returns_empty_for_a_clean_list():
    emails = ["alice@example.com", "bob@example.com"]
    assert flag_low_quality_emails(emails) == []
