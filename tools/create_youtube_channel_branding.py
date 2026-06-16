from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "marketing" / "youtube-channel"
PROFILE_PATH = ROOT / "profile.png"
APP_ICON_PATH = ROOT / "src" / "assets" / "icons" / "app.png"

BANNER_SIZE = (2048, 1152)
LOGO_SIZE = (800, 800)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FONT_NOTES = load_font(20, bold=False)


def fit_font(text: str, max_width: int, start_size: int, min_size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    probe = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(probe)
    for size in range(start_size, min_size - 1, -2):
        font = load_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
    return load_font(min_size, bold=bold)


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top[index] * (1.0 - ratio) + bottom[index] * ratio) for index in range(3))
        draw.line((0, y, width, y), fill=color)
    return image


def add_glow(base: Image.Image, center: tuple[int, int], radius: int, color: tuple[int, int, int], alpha: int) -> None:
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=60))
    base.alpha_composite(glow)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def circle_mask(size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    return mask


def contain_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGBA")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas


def crop_profile(image: Image.Image, size: tuple[int, int], circular: bool) -> Image.Image:
    source = image.convert("RGBA")
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))

    scale = max(size[0] / source.width, size[1] / source.height)
    resized = source.resize((int(source.width * scale), int(source.height * scale)), Image.Resampling.LANCZOS)
    left = max((resized.width - size[0]) // 2, 0)
    top = max((resized.height - size[1]) // 2, 0)
    cropped = resized.crop((left, top, left + size[0], top + size[1]))

    if circular:
        cropped.putalpha(circle_mask(size))
    else:
        cropped.putalpha(rounded_mask(size, radius=64))
    canvas.alpha_composite(cropped)
    return canvas


def draw_soft_grid(draw: ImageDraw.ImageDraw, size: tuple[int, int], spacing: int, color: tuple[int, int, int, int]) -> None:
    width, height = size
    for x in range(0, width, spacing):
        draw.line((x, 0, x, height), fill=color, width=1)
    for y in range(0, height, spacing):
        draw.line((0, y, width, y), fill=color, width=1)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_banner() -> Path:
    banner = vertical_gradient(BANNER_SIZE, (7, 14, 22), (18, 31, 43)).convert("RGBA")
    add_glow(banner, (1560, 250), 320, (59, 130, 246), 90)
    add_glow(banner, (420, 920), 360, (245, 158, 11), 55)

    overlay = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw_soft_grid(draw, BANNER_SIZE, spacing=72, color=(255, 255, 255, 16))

    safe_left = 320
    safe_top = 280
    safe_width = 1235
    text_panel_width = 900

    title_faraz_font = fit_font("Faraz", 620, start_size=122, min_size=96, bold=True)
    title_auto_font = fit_font("Automation", 760, start_size=122, min_size=88, bold=True)
    subtitle_font = fit_font(
        "Automation systems, product demos, AI workflows, and real business tools built for modern teams.",
        760,
        start_size=40,
        min_size=28,
        bold=False,
    )
    pill_font = fit_font("MessageCannon", 250, start_size=32, min_size=24, bold=True)
    eyebrow_font = fit_font("FARAZ AUTOMATION", 340, start_size=32, min_size=24, bold=True)
    product_title_font = fit_font("MessageCannon", 320, start_size=54, min_size=34, bold=True)
    byline_font = fit_font("Built by Muhammad Faraz", 360, start_size=32, min_size=22, bold=True)

    draw.rounded_rectangle((safe_left - 22, safe_top - 74, safe_left + text_panel_width, safe_top + 378), radius=42, fill=(8, 16, 26, 190), outline=(90, 118, 140, 88), width=2)
    draw.rounded_rectangle((safe_left, safe_top - 26, safe_left + 352, safe_top + 34), radius=30, fill=(16, 84, 139, 255))
    draw.text((safe_left + 28, safe_top - 12), "FARAZ AUTOMATION", font=eyebrow_font, fill=(240, 248, 255, 255))

    title_y = safe_top + 42
    draw.text((safe_left, title_y), "Faraz", font=title_faraz_font, fill=(250, 251, 245, 255))
    faraz_height = draw.textbbox((0, 0), "Faraz", font=title_faraz_font)[3]
    auto_y = title_y + faraz_height + 6
    draw.text((safe_left, auto_y), "Automation", font=title_auto_font, fill=(255, 187, 56, 255))

    subtitle_lines = wrap_text(
        draw,
        "Automation systems, product demos, AI workflows, and real business tools built for modern teams.",
        subtitle_font,
        max_width=780,
    )
    subtitle_y = auto_y + draw.textbbox((0, 0), "Automation", font=title_auto_font)[3] + 22
    for index, line in enumerate(subtitle_lines):
        draw.text((safe_left, subtitle_y + (index * 48)), line, font=subtitle_font, fill=(205, 217, 228, 255))

    pills = [
        ("YouTube Demos", (17, 94, 89, 255)),
        ("MessageCannon", (124, 58, 237, 255)),
        ("AI Workflows", (180, 83, 9, 255)),
    ]
    pill_x = safe_left
    pill_y = subtitle_y + (len(subtitle_lines) * 48) + 30
    for label, color in pills:
        bbox = draw.textbbox((0, 0), label, font=pill_font)
        width = (bbox[2] - bbox[0]) + 48
        draw.rounded_rectangle((pill_x, pill_y, pill_x + width, pill_y + 56), radius=28, fill=color)
        draw.text((pill_x + 24, pill_y + 12), label, font=pill_font, fill=(250, 251, 245, 255))
        pill_x += width + 18

    profile = crop_profile(Image.open(PROFILE_PATH), (580, 720), circular=False)
    portrait_back = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    portrait_draw = ImageDraw.Draw(portrait_back)
    portrait_x = 1380
    portrait_y = 176
    portrait_draw.rounded_rectangle((portrait_x - 24, portrait_y - 24, portrait_x + 604, portrait_y + 744), radius=80, fill=(11, 20, 32, 180), outline=(133, 164, 188, 100), width=2)
    portrait_back.alpha_composite(profile, (portrait_x, portrait_y))
    add_glow(portrait_back, (portrait_x + 250, portrait_y + 120), 180, (255, 255, 255), 60)
    banner.alpha_composite(overlay)
    banner.alpha_composite(portrait_back)

    app_icon = contain_image(Image.open(APP_ICON_PATH), (170, 170))
    icon_x = 1660
    icon_y = 820
    badge = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge)
    badge_draw.rounded_rectangle((icon_x - 26, icon_y - 26, icon_x + 206, icon_y + 206), radius=48, fill=(13, 19, 29, 220), outline=(255, 255, 255, 64), width=2)
    badge.alpha_composite(app_icon, (icon_x, icon_y))
    product_block_left = 1502
    badge_draw.text((product_block_left, 960), "Powered by", font=subtitle_font, fill=(203, 214, 225, 255))
    badge_draw.text((product_block_left, 1008), "MessageCannon", font=product_title_font, fill=(250, 251, 245, 255))
    badge_draw.text((product_block_left + 4, 1070), "Built by Muhammad Faraz", font=byline_font, fill=(255, 187, 56, 255))
    banner.alpha_composite(badge)

    output_path = OUTPUT_DIR / "faraz-automation-youtube-banner.png"
    banner.convert("RGB").save(output_path, quality=95)
    return output_path


def render_logo() -> Path:
    size = LOGO_SIZE
    logo = vertical_gradient(size, (9, 16, 24), (20, 34, 45)).convert("RGBA")
    add_glow(logo, (540, 180), 200, (59, 130, 246), 100)
    add_glow(logo, (230, 650), 220, (245, 158, 11), 80)
    draw = ImageDraw.Draw(logo)
    draw.ellipse((40, 40, 760, 760), fill=(9, 15, 23, 190), outline=(187, 199, 210, 80), width=3)
    draw.ellipse((84, 84, 716, 716), outline=(255, 255, 255, 28), width=2)

    portrait = crop_profile(Image.open(PROFILE_PATH), (470, 470), circular=True)
    logo.alpha_composite(portrait, (165, 92))

    plate = Image.new("RGBA", size, (0, 0, 0, 0))
    plate_draw = ImageDraw.Draw(plate)
    badge_font = fit_font("FA", 120, start_size=58, min_size=42, bold=True)
    plate_draw.rounded_rectangle((242, 598, 558, 698), radius=46, fill=(10, 23, 37, 225), outline=(255, 255, 255, 40), width=2)
    plate_draw.text((350, 618), "FA", font=badge_font, fill=(250, 251, 245, 255))
    logo.alpha_composite(plate)

    icon = contain_image(Image.open(APP_ICON_PATH), (150, 150))
    badge = Image.new("RGBA", size, (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge)
    badge_draw.rounded_rectangle((590, 74, 744, 228), radius=42, fill=(18, 26, 38, 235), outline=(255, 255, 255, 55), width=2)
    badge.alpha_composite(icon, (592, 76))
    logo.alpha_composite(badge)

    output_path = OUTPUT_DIR / "faraz-automation-youtube-logo.png"
    logo.convert("RGB").save(output_path, quality=95)
    return output_path


def write_notes() -> Path:
    notes_path = OUTPUT_DIR / "channel-branding-notes.txt"
    notes = """Channel Name: Faraz Automation
Handle Suggestion: @farazautomation
Fallback Handle: @farazautomationhq

Tagline:
Automation systems, AI workflows, product demos, and practical digital tools.

Assets:
- faraz-automation-youtube-banner.png
- faraz-automation-youtube-logo.png

Design Direction:
- Uses your real profile cutout from profile.png
- Includes Faraz Automation as the main identity
- Integrates the MessageCannon icon as a product signature
- Keeps important text inside the central YouTube safe area
"""
    notes_path.write_text(notes, encoding="utf-8")
    return notes_path


def main() -> None:
    ensure_output_dir()
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Missing profile image: {PROFILE_PATH}")
    if not APP_ICON_PATH.exists():
        raise FileNotFoundError(f"Missing app icon: {APP_ICON_PATH}")

    banner = render_banner()
    logo = render_logo()
    notes = write_notes()
    print(banner)
    print(logo)
    print(notes)


if __name__ == "__main__":
    main()