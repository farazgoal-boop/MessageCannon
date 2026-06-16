from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
MARKETING = ROOT / "marketing"

FAMILY_SANS = "Trebuchet MS, Segoe UI, Arial, sans-serif"


ASSETS = {
    "base": {
        "icon": "../src/assets/icons/app.png",
        "profile": "../profile.png",
    },
    "alt": {
        "icon": "../../src/assets/icons/app.png",
        "profile": "../../profile.png",
    },
    "final": {
        "icon": "../../src/assets/icons/app.png",
        "profile": "../../profile.png",
    },
}


def line_text(lines: list[tuple[str, int, int, str, int]], x: int) -> str:
    return "\n  ".join(
        f'<text x="{x}" y="{y}" fill="{fill}" font-family="{FAMILY_SANS}" font-size="{size}" font-weight="{weight}">{text}</text>'
        for text, y, size, fill, weight in lines
    )


def chip_row(items: list[str], *, start_x: int, y: int, width: int, gap: int, colors: list[str], font_size: int) -> str:
    parts: list[str] = []
    for index, item in enumerate(items):
        x = start_x + index * (width + gap)
        parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="48" rx="18" fill="{colors[index]}" opacity="0.94"/>')
        parts.append(
            f'<text x="{x + width / 2}" y="{y + 31}" fill="#FFFFFF" font-family="{FAMILY_SANS}" font-size="{font_size}" font-weight="800" text-anchor="middle">{item}</text>'
        )
    return "\n  ".join(parts)


def hero_1280x720(
    *,
    aria: str,
    icon: str,
    profile: str,
    eyebrow: str,
    kicker: str,
    bg_start: str,
    bg_mid: str,
    bg_end: str,
    accent_start: str,
    accent_end: str,
    title: list[str],
    subtitle: list[str],
    chips: list[str],
    footer: str,
    portrait_label: str,
) -> str:
    return dedent(
        f"""
        <svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{aria}">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="{bg_start}"/>
              <stop offset="56%" stop-color="{bg_mid}"/>
              <stop offset="100%" stop-color="{bg_end}"/>
            </linearGradient>
            <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="{accent_start}"/>
              <stop offset="100%" stop-color="{accent_end}"/>
            </linearGradient>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="14" stdDeviation="22" flood-color="#05070F" flood-opacity="0.42"/>
            </filter>
            <clipPath id="portraitClip">
              <rect x="950" y="96" width="258" height="520" rx="32" ry="32"/>
            </clipPath>
          </defs>
          <rect width="1280" height="720" fill="url(#bg)"/>
          <circle cx="1140" cy="90" r="148" fill="{accent_start}" opacity="0.14"/>
          <circle cx="164" cy="646" r="208" fill="#FFFFFF" opacity="0.05"/>
          <path d="M0 568 L660 280 L1280 540 L1280 720 L0 720 Z" fill="#05070F" opacity="0.34"/>
          <path d="M0 112 L420 0 L840 0 L304 224 Z" fill="{accent_start}" opacity="0.14"/>
          <rect x="72" y="74" width="782" height="574" rx="34" fill="#FFFFFF" opacity="0.06"/>
          <g filter="url(#shadow)">
            <rect x="72" y="74" width="126" height="126" rx="30" fill="#05070F" opacity="0.9"/>
            <image href="{icon}" x="84" y="86" width="102" height="102" preserveAspectRatio="xMidYMid meet"/>
          </g>
          <text x="220" y="134" fill="#FFE7A8" font-family="{FAMILY_SANS}" font-size="23" font-weight="800" letter-spacing="2">{eyebrow}</text>
          <text x="220" y="168" fill="#D9E4EF" font-family="{FAMILY_SANS}" font-size="22" font-weight="600">{kicker}</text>
          {line_text([(title[0], 282, 76, '#FFFFFF', 900), (title[1], 360, 76, '#FFFFFF', 900), (title[2], 438, 74, '#FFFFFF', 900)], 72)}
          {line_text([(subtitle[0], 510, 28, '#F7E7F0', 600), (subtitle[1], 546, 28, '#F7E7F0', 600)], 78)}
          {chip_row(chips, start_x=78, y=594, width=180, gap=22, colors=['#173245', '#1C6B4D', '#7A5825'], font_size=19)}
          <text x="78" y="676" fill="#FFE8C2" font-family="{FAMILY_SANS}" font-size="22" font-weight="700">{footer}</text>
          <g filter="url(#shadow)">
            <rect x="950" y="96" width="258" height="520" rx="32" fill="#05070F" opacity="0.62"/>
            <rect x="972" y="118" width="214" height="42" rx="18" fill="url(#accent)" opacity="0.97"/>
            <text x="1079" y="146" fill="#1B1209" font-family="{FAMILY_SANS}" font-size="19" font-weight="900" text-anchor="middle">{portrait_label}</text>
            <image href="{profile}" x="950" y="96" width="258" height="520" preserveAspectRatio="xMidYMid meet" clip-path="url(#portraitClip)"/>
          </g>
        </svg>
        """
    ).strip() + "\n"


def hero_1280x769(
    *,
    aria: str,
    icon: str,
    profile: str,
    eyebrow: str,
    kicker: str,
    bg_start: str,
    bg_mid: str,
    bg_end: str,
    accent_start: str,
    accent_end: str,
    title: list[str],
    subtitle: list[str],
    chips: list[str],
    footer: str,
    portrait_label: str,
) -> str:
    return dedent(
        f"""
        <svg width="1280" height="769" viewBox="0 0 1280 769" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{aria}">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="{bg_start}"/>
              <stop offset="56%" stop-color="{bg_mid}"/>
              <stop offset="100%" stop-color="{bg_end}"/>
            </linearGradient>
            <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="{accent_start}"/>
              <stop offset="100%" stop-color="{accent_end}"/>
            </linearGradient>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="14" stdDeviation="24" flood-color="#04070E" flood-opacity="0.44"/>
            </filter>
            <clipPath id="portraitClip">
              <rect x="934" y="92" width="254" height="556" rx="30" ry="30"/>
            </clipPath>
          </defs>
          <rect width="1280" height="769" fill="url(#bg)"/>
          <circle cx="1122" cy="90" r="160" fill="{accent_start}" opacity="0.14"/>
          <path d="M0 612 L1280 418 L1280 769 L0 769 Z" fill="#060910" opacity="0.34"/>
          <path d="M0 136 L520 0 L908 0 L320 236 Z" fill="{accent_start}" opacity="0.16"/>
          <rect x="72" y="72" width="778" height="620" rx="34" fill="#FFFFFF" opacity="0.06"/>
          <g filter="url(#shadow)">
            <rect x="72" y="72" width="122" height="122" rx="28" fill="#05070F" opacity="0.9"/>
            <image href="{icon}" x="84" y="84" width="98" height="98" preserveAspectRatio="xMidYMid meet"/>
          </g>
          <text x="214" y="126" fill="#FFE7A8" font-family="{FAMILY_SANS}" font-size="23" font-weight="800">{eyebrow}</text>
          <text x="214" y="160" fill="#D9E4EF" font-family="{FAMILY_SANS}" font-size="22" font-weight="600">{kicker}</text>
          {line_text([(title[0], 288, 68, '#FFFFFF', 900), (title[1], 362, 68, '#FFFFFF', 900), (title[2], 436, 68, '#FFFFFF', 900)], 72)}
          {line_text([(subtitle[0], 512, 27, '#F9ECF3', 600), (subtitle[1], 548, 27, '#F9ECF3', 600)], 76)}
          {chip_row(chips, start_x=76, y=604, width=184, gap=20, colors=['#173245', '#1C6B4D', '#7A5825'], font_size=18)}
          <text x="76" y="704" fill="#FFE6C7" font-family="{FAMILY_SANS}" font-size="21" font-weight="700">{footer}</text>
          <g filter="url(#shadow)">
            <rect x="934" y="92" width="254" height="556" rx="30" fill="#05070F" opacity="0.62"/>
            <rect x="954" y="118" width="214" height="42" rx="18" fill="url(#accent)" opacity="0.96"/>
            <text x="1061" y="146" fill="#1A120B" font-family="{FAMILY_SANS}" font-size="18" font-weight="900" text-anchor="middle">{portrait_label}</text>
            <image href="{profile}" x="934" y="92" width="254" height="556" preserveAspectRatio="xMidYMid meet" clip-path="url(#portraitClip)"/>
          </g>
        </svg>
        """
    ).strip() + "\n"


def linkedin_1584x396(
    *,
    aria: str,
    icon: str,
    profile: str,
    eyebrow: str,
    kicker: str,
    bg_start: str,
    bg_mid: str,
    bg_end: str,
    accent_start: str,
    accent_end: str,
    title: str,
    subtitle: str,
    band: str,
    footer: str,
) -> str:
    return dedent(
        f"""
        <svg width="1584" height="396" viewBox="0 0 1584 396" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{aria}">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="{bg_start}"/>
              <stop offset="56%" stop-color="{bg_mid}"/>
              <stop offset="100%" stop-color="{bg_end}"/>
            </linearGradient>
            <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="{accent_start}"/>
              <stop offset="100%" stop-color="{accent_end}"/>
            </linearGradient>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="10" stdDeviation="20" flood-color="#04070E" flood-opacity="0.36"/>
            </filter>
            <clipPath id="portraitClip">
              <circle cx="1320" cy="196" r="104"/>
            </clipPath>
          </defs>
          <rect width="1584" height="396" fill="url(#bg)"/>
          <circle cx="1468" cy="42" r="156" fill="{accent_start}" opacity="0.14"/>
          <path d="M0 292 L622 112 L1584 272 L1584 396 L0 396 Z" fill="#04070E" opacity="0.30"/>
          <g filter="url(#shadow)">
            <rect x="56" y="52" width="100" height="100" rx="24" fill="#05070F" opacity="0.88"/>
            <image href="{icon}" x="66" y="62" width="80" height="80" preserveAspectRatio="xMidYMid meet"/>
          </g>
          <text x="184" y="94" fill="#FFE7A8" font-family="{FAMILY_SANS}" font-size="21" font-weight="800" letter-spacing="2">{eyebrow}</text>
          <text x="184" y="126" fill="#D9E4EF" font-family="{FAMILY_SANS}" font-size="20" font-weight="600">{kicker}</text>
          <text x="56" y="208" fill="#FFFFFF" font-family="{FAMILY_SANS}" font-size="76" font-weight="900">{title}</text>
          <text x="58" y="252" fill="#E9EEF6" font-family="{FAMILY_SANS}" font-size="27" font-weight="600">{subtitle}</text>
          <rect x="58" y="278" width="868" height="52" rx="18" fill="url(#accent)"/>
          <text x="492" y="311" fill="#17120A" font-family="{FAMILY_SANS}" font-size="23" font-weight="900" text-anchor="middle">{band}</text>
          <text x="58" y="362" fill="#FFE6C3" font-family="{FAMILY_SANS}" font-size="21" font-weight="700">{footer}</text>
          <circle cx="1320" cy="196" r="128" fill="#04070E" opacity="0.44"/>
          <circle cx="1320" cy="196" r="104" fill="{accent_start}" opacity="0.16"/>
          <image href="{profile}" x="1216" y="92" width="208" height="208" preserveAspectRatio="xMidYMid meet" clip-path="url(#portraitClip)"/>
        </svg>
        """
    ).strip() + "\n"


def facebook_1640x624(
    *,
    aria: str,
    icon: str,
    profile: str,
    eyebrow: str,
    kicker: str,
    bg_start: str,
    bg_mid: str,
    bg_end: str,
    accent_start: str,
    accent_end: str,
    title1: str,
    title2: str,
    subtitle1: str,
    subtitle2: str,
    chips: list[str],
    footer: str,
    portrait_label: str,
) -> str:
    return dedent(
        f"""
        <svg width="1640" height="624" viewBox="0 0 1640 624" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{aria}">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="{bg_start}"/>
              <stop offset="56%" stop-color="{bg_mid}"/>
              <stop offset="100%" stop-color="{bg_end}"/>
            </linearGradient>
            <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="{accent_start}"/>
              <stop offset="100%" stop-color="{accent_end}"/>
            </linearGradient>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="14" stdDeviation="24" flood-color="#05070F" flood-opacity="0.42"/>
            </filter>
            <clipPath id="portraitClip">
              <rect x="1180" y="84" width="300" height="458" rx="32" ry="32"/>
            </clipPath>
          </defs>
          <rect width="1640" height="624" fill="url(#bg)"/>
          <circle cx="1458" cy="80" r="168" fill="{accent_start}" opacity="0.14"/>
          <circle cx="150" cy="566" r="210" fill="#FFFFFF" opacity="0.05"/>
          <path d="M0 498 L742 236 L1640 500 L1640 624 L0 624 Z" fill="#05070F" opacity="0.34"/>
          <path d="M0 112 L560 0 L940 0 L308 240 Z" fill="{accent_start}" opacity="0.15"/>
          <rect x="70" y="74" width="1034" height="476" rx="32" fill="#FFFFFF" opacity="0.06"/>
          <g filter="url(#shadow)">
            <rect x="80" y="92" width="130" height="130" rx="30" fill="#05070F" opacity="0.88"/>
            <image href="{icon}" x="92" y="104" width="106" height="106" preserveAspectRatio="xMidYMid meet"/>
          </g>
          <text x="236" y="142" fill="#FFE7A8" font-family="{FAMILY_SANS}" font-size="24" font-weight="800" letter-spacing="2">{eyebrow}</text>
          <text x="236" y="176" fill="#D9E4EF" font-family="{FAMILY_SANS}" font-size="22" font-weight="600">{kicker}</text>
          <text x="80" y="280" fill="#FFFFFF" font-family="{FAMILY_SANS}" font-size="82" font-weight="900">{title1}</text>
          <text x="80" y="356" fill="#FFFFFF" font-family="{FAMILY_SANS}" font-size="82" font-weight="900">{title2}</text>
          <text x="84" y="414" fill="#F7E8F1" font-family="{FAMILY_SANS}" font-size="29" font-weight="600">{subtitle1}</text>
          <text x="84" y="448" fill="#F7E8F1" font-family="{FAMILY_SANS}" font-size="29" font-weight="600">{subtitle2}</text>
          {chip_row(chips, start_x=80, y=468, width=198, gap=26, colors=['#173245', '#1C6B4D', '#7A5825'], font_size=21)}
          <text x="84" y="556" fill="#FBE4C0" font-family="{FAMILY_SANS}" font-size="23" font-weight="700">{footer}</text>
          <g filter="url(#shadow)">
            <rect x="1180" y="84" width="300" height="458" rx="32" fill="#05070F" opacity="0.62"/>
            <rect x="1206" y="112" width="212" height="42" rx="18" fill="url(#accent)" opacity="0.97"/>
            <text x="1312" y="140" fill="#17120A" font-family="{FAMILY_SANS}" font-size="19" font-weight="900" text-anchor="middle">{portrait_label}</text>
            <image href="{profile}" x="1180" y="84" width="300" height="458" preserveAspectRatio="xMidYMid meet" clip-path="url(#portraitClip)"/>
          </g>
        </svg>
        """
    ).strip() + "\n"


FILES: dict[Path, str] = {
    MARKETING / "youtube-thumbnail.svg": hero_1280x720(
        aria="MessageCannon YouTube Thumbnail",
        icon=ASSETS["base"]["icon"],
        profile=ASSETS["base"]["profile"],
        eyebrow="MESSAGECANNON",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#1B1028",
        bg_mid="#5E1742",
        bg_end="#A61E4D",
        accent_start="#FF9F1C",
        accent_end="#FFD166",
        title=["WHATSAPP", "CAMPAIGN", "DESKTOP APP"],
        subtitle=["Launch branded outreach flows with contact import, session save,", "clean delivery reporting, and a desktop UI that looks client ready."],
        chips=["Import Fast", "Send Safer", "Track Results"],
        footer="Built for demos, product pages, and polished automation showcases.",
        portrait_label="FOUNDER PRESENCE",
    ),
    MARKETING / "upwork-cover.svg": hero_1280x720(
        aria="MessageCannon Upwork Cover",
        icon=ASSETS["base"]["icon"],
        profile=ASSETS["base"]["profile"],
        eyebrow="MESSAGECANNON",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#14213D",
        bg_mid="#2A4F6E",
        bg_end="#4B728D",
        accent_start="#2EC4B6",
        accent_end="#CBF3F0",
        title=["PREMIUM", "OUTREACH", "WORKSPACE"],
        subtitle=["Show campaign control, session persistence, and reporting clarity", "inside one premium desktop flow built for strong client perception."],
        chips=["Client Ready", "Clean UX", "Live Reports"],
        footer="Made for Upwork covers, sales pitches, and polished product positioning.",
        portrait_label="FOUNDER TRUST",
    ),
    MARKETING / "linkedin-banner.svg": linkedin_1584x396(
        aria="MessageCannon LinkedIn Banner",
        icon=ASSETS["base"]["icon"],
        profile=ASSETS["base"]["profile"],
        eyebrow="MESSAGECANNON",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#1B1028",
        bg_mid="#5E1742",
        bg_end="#A61E4D",
        accent_start="#FF9F1C",
        accent_end="#FFD166",
        title="MessageCannon",
        subtitle="Campaign software with premium desktop UX, delivery reporting, and stronger founder-led branding.",
        band="IMPORT CONTACTS  •  SEND SMARTER  •  TRACK RESULTS",
        footer="Built to make outreach products look cleaner, stronger, and easier to trust.",
    ),
    MARKETING / "fiverr-gig-cover.svg": hero_1280x769(
        aria="MessageCannon Fiverr Gig Cover",
        icon=ASSETS["base"]["icon"],
        profile=ASSETS["base"]["profile"],
        eyebrow="MESSAGECANNON OFFER",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#1B1028",
        bg_mid="#5E1742",
        bg_end="#A61E4D",
        accent_start="#FF9F1C",
        accent_end="#FFD166",
        title=["I WILL BUILD", "A WHATSAPP", "DESKTOP APP"],
        subtitle=["Premium campaign software visuals with clearer hierarchy,", "better offer framing, and cleaner reporting-focused product messaging."],
        chips=["Premium Look", "Clear Offer", "Track Results"],
        footer="Ideal for Fiverr gig covers, client demos, and productized service pages.",
        portrait_label="HUMAN TRUST",
    ),
    MARKETING / "facebook-banner.svg": facebook_1640x624(
        aria="MessageCannon Facebook Banner",
        icon=ASSETS["base"]["icon"],
        profile=ASSETS["base"]["profile"],
        eyebrow="MESSAGECANNON",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#1B1028",
        bg_mid="#5E1742",
        bg_end="#A61E4D",
        accent_start="#FF9F1C",
        accent_end="#FFD166",
        title1="WHATSAPP CAMPAIGN",
        title2="DESKTOP APP",
        subtitle1="Built for branded outreach workflows, cleaner automation screens,",
        subtitle2="and reporting views that feel ready for real client work.",
        chips=["Import Contacts", "Launch Flows", "Track Results"],
        footer="Persistent sessions, delivery analytics, and premium desktop control in one workspace.",
        portrait_label="FOUNDER PRESENCE",
    ),
    MARKETING / "alt-premium" / "youtube-thumbnail-luxury.svg": hero_1280x720(
        aria="MessageCannon Luxury YouTube Thumbnail",
        icon=ASSETS["alt"]["icon"],
        profile=ASSETS["alt"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Luxury WhatsApp campaign desktop app",
        bg_start="#0B132B",
        bg_mid="#1C2541",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title=["LUXURY", "OUTREACH", "WORKSPACE"],
        subtitle=["Present session memory, delivery reporting, and polished desktop UX", "in a founder-led layout designed to feel premium on first view."],
        chips=["Trust Signal", "Premium UX", "Clear Reports"],
        footer="Built for agency demos, premium offers, and high-trust software branding.",
        portrait_label="FOUNDER PRESENCE",
    ),
    MARKETING / "alt-premium" / "upwork-cover-sales.svg": hero_1280x720(
        aria="MessageCannon Luxury Upwork Sales Cover",
        icon=ASSETS["alt"]["icon"],
        profile=ASSETS["alt"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Luxury WhatsApp campaign desktop app",
        bg_start="#0A1128",
        bg_mid="#1F2041",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title=["PREMIUM", "CAMPAIGN", "SOFTWARE"],
        subtitle=["Use a sharper luxury layout to sell clean automation workflows,", "stronger visual trust, and premium-looking reporting dashboards."],
        chips=["Sales Ready", "Human Brand", "Premium UI"],
        footer="Made for Upwork sales art, polished proposals, and higher-value positioning.",
        portrait_label="FOUNDER TRUST",
    ),
    MARKETING / "alt-premium" / "linkedin-banner-luxury.svg": linkedin_1584x396(
        aria="MessageCannon Luxury LinkedIn Banner",
        icon=ASSETS["alt"]["icon"],
        profile=ASSETS["alt"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Luxury WhatsApp campaign desktop app",
        bg_start="#0B132B",
        bg_mid="#1C2541",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title="MessageCannon",
        subtitle="Corporate-grade campaign software with premium desktop polish and a stronger founder-led signal.",
        band="TRUSTED LOOK  •  PREMIUM UX  •  HIGHER VALUE FEEL",
        footer="A luxury banner system for polished profiles, software branding, and premium outreach demos.",
    ),
    MARKETING / "alt-premium" / "fiverr-gig-cover-sales.svg": hero_1280x769(
        aria="MessageCannon Luxury Fiverr Sales Cover",
        icon=ASSETS["alt"]["icon"],
        profile=ASSETS["alt"]["profile"],
        eyebrow="PREMIUM FIVERR OFFER",
        kicker="Luxury WhatsApp campaign desktop app",
        bg_start="#111827",
        bg_mid="#253047",
        bg_end="#3F1D2E",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title=["I WILL BUILD", "A WHATSAPP", "AUTOMATION APP"],
        subtitle=["Luxury sales-direction artwork with cleaner spacing, better copy,", "and a premium human signal that supports higher-ticket positioning."],
        chips=["Sell Better", "Look Premium", "Show Value"],
        footer="Optimized for Fiverr offers, polished proposals, and premium service presentation.",
        portrait_label="TRUST SIGNAL",
    ),
    MARKETING / "alt-premium" / "facebook-banner-luxury.svg": facebook_1640x624(
        aria="MessageCannon Luxury Facebook Banner",
        icon=ASSETS["alt"]["icon"],
        profile=ASSETS["alt"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Luxury WhatsApp campaign desktop app",
        bg_start="#0B132B",
        bg_mid="#1C2541",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title1="PREMIUM WHATSAPP",
        title2="OUTREACH SOFTWARE",
        subtitle1="Luxury visual direction for founders who want campaign software",
        subtitle2="to look expensive, organized, and immediately trustworthy.",
        chips=["Founder Brand", "Clean Visuals", "Premium Pitch"],
        footer="Built for polished company pages, premium demos, and high-trust digital storefronts.",
        portrait_label="FOUNDER PRESENCE",
    ),
    MARKETING / "final-polish" / "youtube-thumbnail-final.svg": hero_1280x720(
        aria="Faraz Automation YouTube Thumbnail",
        icon=ASSETS["final"]["icon"],
        profile=ASSETS["final"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#0B132B",
        bg_mid="#1C2541",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title=["MESSAGECANNON", "WHATSAPP", "DESKTOP APP"],
        subtitle=["Show session persistence, live delivery reporting, and a cleaner", "campaign workflow inside a founder-led premium product presentation."],
        chips=["Human Brand", "Clean Flow", "Track Reads"],
        footer="Polished for YouTube thumbnails, demo covers, and software launch visuals.",
        portrait_label="FOUNDER PRESENCE",
    ),
    MARKETING / "final-polish" / "upwork-cover-final.svg": hero_1280x720(
        aria="Faraz Automation Upwork Cover",
        icon=ASSETS["final"]["icon"],
        profile=ASSETS["final"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#0A1128",
        bg_mid="#1F2041",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title=["PREMIUM", "CAMPAIGN", "WORKSPACE"],
        subtitle=["A cleaner final-polish cover for product showcases, proposals,", "and founder-led software branding that feels organized and premium."],
        chips=["Founder Led", "Premium UX", "Ready To Demo"],
        footer="Built to look sharper on Upwork, portfolios, and premium service pages.",
        portrait_label="FOUNDER PRESENCE",
    ),
    MARKETING / "final-polish" / "linkedin-banner-final.svg": linkedin_1584x396(
        aria="Faraz Automation LinkedIn Banner",
        icon=ASSETS["final"]["icon"],
        profile=ASSETS["final"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#0B132B",
        bg_mid="#1C2541",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title="MessageCannon",
        subtitle="Premium outreach software with founder branding, cleaner UI, and stronger reporting clarity.",
        band="SESSION SAVE  •  CLEANER UX  •  FOUNDER PRESENCE",
        footer="Final-polish branding for LinkedIn headers, launch posts, and trust-first product positioning.",
    ),
    MARKETING / "final-polish" / "fiverr-cover-final.svg": hero_1280x769(
        aria="Faraz Automation Fiverr Cover",
        icon=ASSETS["final"]["icon"],
        profile=ASSETS["final"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#0F172A",
        bg_mid="#1E293B",
        bg_end="#4C1D95",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title=["I WILL BUILD", "A WHATSAPP", "DESKTOP APP"],
        subtitle=["Final-polish service art with tighter messaging, clearer value,", "and a founder-led premium look that reads better at first glance."],
        chips=["Strong Design", "Clear Offer", "Premium Feel"],
        footer="Ideal for Fiverr covers, portfolio graphics, and premium marketplace branding.",
        portrait_label="TRUST SIGNAL",
    ),
    MARKETING / "final-polish" / "facebook-banner-final.svg": facebook_1640x624(
        aria="Faraz Automation Facebook Banner",
        icon=ASSETS["final"]["icon"],
        profile=ASSETS["final"]["profile"],
        eyebrow="FARAZ AUTOMATION",
        kicker="Premium WhatsApp campaign desktop app",
        bg_start="#0B132B",
        bg_mid="#1C2541",
        bg_end="#3A506B",
        accent_start="#F6D365",
        accent_end="#FFF3C4",
        title1="MESSAGECANNON",
        title2="PREMIUM DESKTOP UI",
        subtitle1="Founder-led WhatsApp campaign software with cleaner visual hierarchy,",
        subtitle2="stronger copy, and a more balanced high-trust presentation.",
        chips=["Clear Message", "Safe Layout", "Founder Brand"],
        footer="Refined for Facebook pages, product promos, and polished outreach branding.",
        portrait_label="FOUNDER PRESENCE",
    ),
}


def main() -> None:
    for path, content in FILES.items():
        path.write_text(content, encoding="utf-8")
        print(f"updated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
