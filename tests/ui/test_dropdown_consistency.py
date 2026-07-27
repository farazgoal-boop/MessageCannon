"""Item 26 of the Final Premium Polish Pass: force visual consistency across
every real dropdown/select element in the app.

Full audit inventory (confirmed via `grep -rn "CTkOptionMenu(" src/ui` --
only two files contain any: main_window.py and setup_wizard.py; nothing in
card_creator_tab.py since Item 11.3 already replaced its Card Template
picker with a visual thumbnail gallery, not a dropdown):

  1. Compose -> WhatsApp panel "Template" dropdown       (self.template_menu)
  2. Compose -> Email panel "Template" dropdown           (self.em_template_menu)
  3. Settings -> System Experience "Theme selector"       (self.theme_menu)
  4. Settings -> SMTP "Provider" preset dropdown          (self.smtp_provider_menu)
  5. Settings -> AI Cards "AI provider" dropdown           (self.ai_provider_menu)
  6. Setup Wizard -> Email step "Provider" dropdown        (not app-attribute; a
     fresh SetupWizard instance, checked separately below)

Real inconsistency found before writing any fix: dropdowns 1-4 used
`fg_color=T.BG_SURFACE, button_color=T.BG_SURFACE` -- flush with their own
parent card's own T.BG_SURFACE background, so the closed selector had no
visible boundary at all and didn't read as a real input the way its sibling
CTkEntry fields (all `fg_color=T.BG_INNER`, the Design System's own
documented "sunken, nested" token) did. Dropdowns 5 and (setup wizard's own)
6 already used the correct `fg_color=T.BG_INNER` pattern -- used as the
reference to bring 1-4 into line with, rather than inventing a new style.
`corner_radius` needed no fix: none of these sites ever override it, so they
already inherit one single CTk default uniformly.

A 5th and 6th CTkOptionMenu pair (`self.report_period_menu`/
`self.report_format_menu`, "Period"/"Export Format" in `_build_reports_view`)
were found and given the identical styling fix at the source level, then
discovered -- by grepping the whole repo for the method's own name -- to be
completely unreachable: `_build_reports_view` is never called from
`_create_ui` (which builds exactly campaigns-home/contacts/compose/
history/settings, plus Cards separately) or anywhere else in the codebase,
including tests. This is a real, previously-undocumented dead-code finding,
not part of Item 26's own scope to resolve (wiring it in or deleting it is a
separate decision) -- flagged here explicitly per this project's standing
"don't silently touch/hide dead code" discipline, and deliberately excluded
from the "every real, user-reachable dropdown must match" assertions below
since a user can never actually see these two widgets today. See
`test_reports_view_is_still_unreachable_dead_code` below, which exists so
the *next* change to this area has to consciously decide to either wire the
view in for real or remove it, rather than this fact silently rotting again.

Item 9's "Insert variable ▾" command-pill menus (`_build_insert_variable_menu`,
2 call sites in Compose) are a deliberate, different pattern -- a compact
pill-styled action menu (badge colors, immediately resets to a placeholder
after each pick), not a persistent settings-style selector -- and are
excluded from the "all dropdowns must match" rule on purpose, not
overlooked; asserted explicitly below so a future pass doesn't "fix" it by
accident.
"""

from __future__ import annotations

STANDARD_DROPDOWN_ATTRS = [
    "template_menu",
    "em_template_menu",
    "theme_menu",
    "smtp_provider_menu",
    "ai_provider_menu",
]


def _style_key(menu, option_name):
    """Every call site in this app passes a bare (light, dark) token (e.g.
    T.BG_INNER) straight through to CTk's own constructor -- CTk widgets
    store and resolve that tuple natively (see theme.py's own module
    docstring: "CTk widgets accept the tuple directly and resolve it
    themselves"), so `.cget()` hands the exact same tuple back unchanged.
    Comparing it directly is exactly equivalent to comparing which token
    each widget was built with."""
    return menu.cget(option_name)


def test_every_standard_dropdown_shares_identical_style(app):
    menus = {name: getattr(app, name) for name in STANDARD_DROPDOWN_ATTRS}
    reference = menus[STANDARD_DROPDOWN_ATTRS[0]]
    for option in ("fg_color", "button_color", "button_hover_color",
                   "text_color", "dropdown_fg_color", "dropdown_hover_color",
                   "dropdown_text_color"):
        expected = _style_key(reference, option)
        for name, menu in menus.items():
            actual = _style_key(menu, option)
            assert actual == expected, (
                f"{name}.{option} = {actual!r}, expected {expected!r} "
                f"(matching {STANDARD_DROPDOWN_ATTRS[0]}) -- dropdowns must "
                f"share one consistent style, per Item 26")


def test_standard_dropdown_trigger_is_not_flush_with_a_surface_card(app):
    """The real bug this item fixed: a dropdown's closed/trigger fill must
    differ from a plain T.BG_SURFACE card background so it reads as a real
    input, matching sibling CTkEntry fields -- not blend invisibly into its
    own parent card the way all of these dropdowns did before this fix."""
    import src.ui.theme as T
    for name in STANDARD_DROPDOWN_ATTRS:
        menu = getattr(app, name)
        assert menu.cget("fg_color") != T.BG_SURFACE, (
            f"{name}'s closed-state fill matches T.BG_SURFACE exactly -- "
            f"it will blend invisibly into any card built with that same "
            f"background, the literal Item 26 bug")
        assert menu.cget("fg_color") == T.BG_INNER


def test_insert_variable_pill_menu_is_a_deliberate_documented_exception(app):
    """Item 9's compact "Insert variable ▾" menus intentionally use a
    different, pill/badge-styled pattern (T.BADGE_BG fill) -- confirm that's
    still true and not accidentally normalized to the standard dropdown
    style by a future pass, since the two serve different UI roles (a
    one-shot command menu vs. a persistent settings selector).

    text_color is T.ACCENT_TEXT, not plain T.ACCENT -- Item 27's systemic
    contrast sweep found plain T.ACCENT text measures only 2.61:1 against
    T.BADGE_BG in Dark mode (a real WCAG fail) and corrected every such site
    app-wide, this pill included; that's a real fix, not a regression from
    Item 26's own "leave the pill's distinct pattern alone" intent, which
    was specifically about fg_color/hover styling, not this contrast bug."""
    menu = app._build_insert_variable_menu(app, ["Name", "Email"], lambda *_: None)
    import src.ui.theme as T
    assert menu.cget("fg_color") == T.BADGE_BG
    assert menu.cget("text_color") == T.ACCENT_TEXT
    menu.destroy()


def test_setup_wizard_provider_dropdown_already_matches_the_standard_style(app):
    """The Setup Wizard's own SMTP Provider dropdown was already using the
    correct T.BG_INNER pattern before this item (one of the two existing
    "right" examples used as the reference for fixing the rest) --
    confirmed directly against a real, rendered wizard instance rather than
    just re-reading the source."""
    import customtkinter as ctk
    from src.ui.setup_wizard import SetupWizard
    import src.ui.theme as T

    wizard = SetupWizard(app, force_restart=True)
    app.update()
    wizard.channels = ["Email"]
    wizard.channel_index = 0
    wizard.substep = "email_creds"
    wizard._render()
    app.update()

    found = []

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkOptionMenu):
                found.append(child)
            walk(child)

    walk(wizard.content)
    assert found, "expected to find the Provider dropdown in the wizard's email_creds step"
    provider_menu = found[0]
    assert provider_menu.cget("fg_color") == T.BG_INNER
    assert provider_menu.cget("button_color") == T.BG_INNER

    wizard.destroy()


def test_reports_view_is_still_unreachable_dead_code(app):
    """Documents a real, incidental finding from this item's audit:
    `_build_reports_view` (owner of `report_period_menu`/`report_format_menu`,
    styled identically to every other dropdown at the source level, see
    module docstring) is never invoked anywhere in the app -- confirmed by
    the attribute genuinely not existing on a real, fully-initialized
    MainWindow. This isn't a regression to fix here; it's flagged so the
    next person touching this area makes a conscious choice (wire it in, or
    delete it) instead of rediscovering it by accident."""
    assert not hasattr(app, "report_period_menu")
    assert not hasattr(app, "report_format_menu")
