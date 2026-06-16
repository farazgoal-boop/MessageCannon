from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


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


def crop_profile(image: Image.Image, size: tuple[int, int], circular: bool) -> Image.Image:
    source = image.convert("RGBA")
    scale = max(size[0] / source.width, size[1] / source.height)
    resized = source.resize((int(source.width * scale), int(source.height * scale)), Image.Resampling.LANCZOS)
    left = max((resized.width - size[0]) // 2, 0)
    top = max((resized.height - size[1]) // 2, 0)
    cropped = resized.crop((left, top, left + size[0], top + size[1]))
    cropped.putalpha(circle_mask(size) if circular else rounded_mask(size, radius=64))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(cropped)
    return canvas


def contain_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    source = image.convert("RGBA")
    source.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - source.width) // 2
    y = (size[1] - source.height) // 2
    canvas.alpha_composite(source, (x, y))
    return canvas


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


def subtitle_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    start_size: int,
    min_size: int,
    line_gap: int,
    fill: tuple[int, int, int, int],
) -> int:
    font = fit_font(text, max_width, start_size, min_size, bold=False)
    lines = wrap_text(draw, text, font, max_width)
    for index, line in enumerate(lines):
        draw.text((x, y + (index * line_gap)), line, font=font, fill=fill)
    return y + (len(lines) * line_gap)


def pill_row(draw: ImageDraw.ImageDraw, x: int, y: int, labels: list[tuple[str, tuple[int, int, int, int]]], start_size: int = 30) -> None:
    font = fit_font("MessageCannon", 250, start_size, 22, bold=True)
    current_x = x
    for label, color in labels:
        bbox = draw.textbbox((0, 0), label, font=font)
        width = (bbox[2] - bbox[0]) + 48
        draw.rounded_rectangle((current_x, y, current_x + width, y + 56), radius=28, fill=color)
        draw.text((current_x + 24, y + 12), label, font=font, fill=(250, 251, 245, 255))
        current_x += width + 18


def base_banner(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    banner = vertical_gradient(BANNER_SIZE, top, bottom).convert("RGBA")
    grid = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(grid)
    for x in range(0, BANNER_SIZE[0], 72):
        draw.line((x, 0, x, BANNER_SIZE[1]), fill=(255, 255, 255, 16), width=1)
    for y in range(0, BANNER_SIZE[1], 72):
        draw.line((0, y, BANNER_SIZE[0], y), fill=(255, 255, 255, 16), width=1)
    banner.alpha_composite(grid)
    return banner


def base_logo(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    logo = vertical_gradient(LOGO_SIZE, top, bottom).convert("RGBA")
    draw = ImageDraw.Draw(logo)
    draw.ellipse((40, 40, 760, 760), fill=(9, 15, 23, 190), outline=(187, 199, 210, 80), width=3)
    draw.ellipse((84, 84, 716, 716), outline=(255, 255, 255, 28), width=2)
    return logo


def render_simple_banner(profile: Image.Image, icon: Image.Image) -> Path:
    banner = base_banner((10, 16, 24), (18, 32, 44))
    add_glow(banner, (1500, 220), 260, (59, 130, 246), 80)
    add_glow(banner, (260, 920), 280, (245, 158, 11), 48)
    draw = ImageDraw.Draw(banner)
    left, top = 292, 304
    draw.rounded_rectangle((left, top, left + 1040, top + 412), radius=48, fill=(8, 16, 26, 210), outline=(90, 118, 140, 88), width=2)
    eyebrow_font = fit_font("FARAZ AUTOMATION", 330, 30, 22, bold=True)
    draw.rounded_rectangle((left + 30, top + 30, left + 390, top + 92), radius=31, fill=(20, 86, 142, 255))
    draw.text((left + 56, top + 46), "FARAZ AUTOMATION", font=eyebrow_font, fill=(244, 248, 252, 255))
    faraz_font = fit_font("Faraz", 460, 118, 92, bold=True)
    auto_font = fit_font("Automation", 700, 118, 82, bold=True)
    title_y = top + 126
    draw.text((left + 34, title_y), "Faraz", font=faraz_font, fill=(247, 248, 243, 255))
    auto_y = title_y + draw.textbbox((0, 0), "Faraz", font=faraz_font)[3] + 2
    draw.text((left + 34, auto_y), "Automation", font=auto_font, fill=(255, 189, 64, 255))
    subtitle_end = subtitle_block(draw, "Automation systems, product demos, AI workflows, and real business tools built for modern teams.", left + 34, auto_y + draw.textbbox((0, 0), "Automation", font=auto_font)[3] + 18, 760, 38, 26, 46, (208, 219, 228, 255))
    pill_row(draw, left + 34, subtitle_end + 18, [("YouTube Demos", (17, 94, 89, 255)), ("MessageCannon", (124, 58, 237, 255)), ("AI Workflows", (180, 83, 9, 255))])
    shell = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shell)
    px, py = 1412, 192
    sdraw.rounded_rectangle((px - 22, py - 22, px + 544, py + 686), radius=82, fill=(10, 18, 29, 185), outline=(133, 164, 188, 100), width=2)
    shell.alpha_composite(profile.resize((520, 662), Image.Resampling.LANCZOS), (px, py))
    banner.alpha_composite(shell)
    lock = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(lock)
    ldraw.rounded_rectangle((1644, 836, 1830, 1022), radius=44, fill=(13, 19, 29, 228), outline=(255, 255, 255, 58), width=2)
    lock.alpha_composite(icon.resize((146, 146), Image.Resampling.LANCZOS), (1664, 856))
    ldraw.text((1476, 998), "Powered by", font=fit_font("Powered by", 200, 34, 24, bold=False), fill=(203, 214, 225, 255))
    ldraw.text((1476, 1042), "MessageCannon", font=fit_font("MessageCannon", 320, 54, 34, bold=True), fill=(247, 248, 243, 255))
    ldraw.text((1478, 1094), "Built by Muhammad Faraz", font=fit_font("Built by Muhammad Faraz", 328, 30, 22, bold=True), fill=(255, 189, 64, 255))
    banner.alpha_composite(lock)
    path = OUTPUT_DIR / "faraz-automation-youtube-banner-simple.png"
    banner.convert("RGB").save(path, quality=95)
    return path


def render_luxury_banner(profile: Image.Image, icon: Image.Image) -> Path:
    banner = base_banner((8, 11, 17), (26, 22, 13))
    add_glow(banner, (1580, 176), 320, (196, 154, 78), 88)
    add_glow(banner, (360, 920), 340, (120, 90, 34), 60)
    draw = ImageDraw.Draw(banner)
    left, top = 262, 250
    draw.rounded_rectangle((left, top, left + 1136, top + 492), radius=54, fill=(10, 13, 19, 224), outline=(181, 149, 91, 108), width=2)
    label_font = fit_font("FARAZ AUTOMATION", 360, 32, 22, bold=True)
    draw.rounded_rectangle((left + 34, top + 34, left + 412, top + 96), radius=31, fill=(125, 94, 38, 255))
    draw.text((left + 60, top + 50), "FARAZ AUTOMATION", font=label_font, fill=(252, 245, 232, 255))
    title_font = fit_font("Faraz Automation", 930, 118, 82, bold=True)
    draw.text((left + 42, top + 132), "Faraz Automation", font=title_font, fill=(244, 240, 231, 255))
    line_y = top + 278
    draw.rounded_rectangle((left + 44, line_y, left + 388, line_y + 8), radius=4, fill=(198, 159, 85, 255))
    subtitle_end = subtitle_block(draw, "Premium automation workflows, polished product demos, and business-ready digital systems.", left + 42, line_y + 34, 800, 42, 28, 48, (219, 210, 192, 255))
    pill_row(draw, left + 42, subtitle_end + 24, [("Premium Demos", (98, 71, 22, 255)), ("Faraz Automation", (123, 90, 35, 255)), ("Business Systems", (82, 63, 23, 255))], start_size=28)
    shell = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shell)
    px, py = 1402, 168
    sdraw.rounded_rectangle((px - 26, py - 26, px + 584, py + 744), radius=88, fill=(16, 13, 11, 215), outline=(191, 160, 101, 100), width=2)
    shell.alpha_composite(profile.resize((556, 716), Image.Resampling.LANCZOS), (px, py))
    banner.alpha_composite(shell)
    lock = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(lock)
    ldraw.rounded_rectangle((1646, 846, 1832, 1032), radius=42, fill=(21, 18, 17, 232), outline=(191, 160, 101, 88), width=2)
    lock.alpha_composite(icon.resize((144, 144), Image.Resampling.LANCZOS), (1667, 867))
    ldraw.text((1486, 1002), "Signature Product", font=fit_font("Signature Product", 260, 34, 22, bold=False), fill=(216, 205, 186, 255))
    ldraw.text((1486, 1042), "MessageCannon", font=fit_font("MessageCannon", 310, 52, 32, bold=True), fill=(247, 240, 230, 255))
    ldraw.text((1488, 1090), "Built by Muhammad Faraz", font=fit_font("Built by Muhammad Faraz", 324, 30, 21, bold=True), fill=(221, 178, 97, 255))
    banner.alpha_composite(lock)
    path = OUTPUT_DIR / "faraz-automation-youtube-banner-luxury.png"
    banner.convert("RGB").save(path, quality=95)
    return path


def render_personal_banner(profile: Image.Image, icon: Image.Image) -> Path:
    banner = base_banner((7, 14, 22), (18, 31, 43))
    add_glow(banner, (1560, 250), 320, (59, 130, 246), 90)
    add_glow(banner, (420, 920), 360, (245, 158, 11), 55)
    draw = ImageDraw.Draw(banner)
    left, top = 320, 280
    draw.rounded_rectangle((left - 22, top - 74, left + 900, top + 378), radius=42, fill=(8, 16, 26, 190), outline=(90, 118, 140, 88), width=2)
    eyebrow_font = fit_font("FARAZ AUTOMATION", 340, 32, 24, bold=True)
    draw.rounded_rectangle((left, top - 26, left + 352, top + 34), radius=30, fill=(16, 84, 139, 255))
    draw.text((left + 28, top - 12), "FARAZ AUTOMATION", font=eyebrow_font, fill=(240, 248, 255, 255))
    faraz_font = fit_font("Faraz", 620, 122, 96, bold=True)
    auto_font = fit_font("Automation", 760, 122, 88, bold=True)
    title_y = top + 42
    draw.text((left, title_y), "Faraz", font=faraz_font, fill=(250, 251, 245, 255))
    auto_y = title_y + draw.textbbox((0, 0), "Faraz", font=faraz_font)[3] + 6
    draw.text((left, auto_y), "Automation", font=auto_font, fill=(255, 187, 56, 255))
    subtitle_end = subtitle_block(draw, "Automation systems, product demos, AI workflows, and real business tools built for modern teams.", left, auto_y + draw.textbbox((0, 0), "Automation", font=auto_font)[3] + 22, 780, 38, 28, 48, (205, 217, 228, 255))
    pill_row(draw, left, subtitle_end + 30, [("YouTube Demos", (17, 94, 89, 255)), ("MessageCannon", (124, 58, 237, 255)), ("AI Workflows", (180, 83, 9, 255))])
    shell = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shell)
    px, py = 1380, 176
    sdraw.rounded_rectangle((px - 24, py - 24, px + 604, py + 744), radius=80, fill=(11, 20, 32, 180), outline=(133, 164, 188, 100), width=2)
    shell.alpha_composite(profile.resize((580, 720), Image.Resampling.LANCZOS), (px, py))
    banner.alpha_composite(shell)
    lock = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(lock)
    ldraw.rounded_rectangle((1634, 794, 1866, 1026), radius=48, fill=(13, 19, 29, 220), outline=(255, 255, 255, 64), width=2)
    lock.alpha_composite(icon.resize((170, 170), Image.Resampling.LANCZOS), (1660, 820))
    ldraw.text((1502, 960), "Powered by", font=fit_font("Powered by", 180, 36, 24, bold=False), fill=(203, 214, 225, 255))
    ldraw.text((1502, 1008), "MessageCannon", font=fit_font("MessageCannon", 320, 54, 34, bold=True), fill=(250, 251, 245, 255))
    ldraw.text((1506, 1070), "Built by Muhammad Faraz", font=fit_font("Built by Muhammad Faraz", 360, 32, 22, bold=True), fill=(255, 187, 56, 255))
    banner.alpha_composite(lock)
    path = OUTPUT_DIR / "faraz-automation-youtube-banner.png"
    banner.convert("RGB").save(path, quality=95)
    return path


def render_simple_logo(profile: Image.Image, icon: Image.Image) -> Path:
    logo = base_logo((10, 16, 24), (18, 32, 44))
    add_glow(logo, (540, 180), 200, (59, 130, 246), 100)
    add_glow(logo, (230, 650), 220, (245, 158, 11), 80)
    logo.alpha_composite(profile.resize((470, 470), Image.Resampling.LANCZOS), (165, 92))
    plate = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(plate)
    pdraw.rounded_rectangle((242, 598, 558, 698), radius=46, fill=(10, 23, 37, 225), outline=(255, 255, 255, 40), width=2)
    pdraw.text((350, 618), "FA", font=fit_font("FA", 120, 58, 42, bold=True), fill=(250, 251, 245, 255))
    logo.alpha_composite(plate)
    icon_holder = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    idraw = ImageDraw.Draw(icon_holder)
    idraw.rounded_rectangle((590, 74, 744, 228), radius=42, fill=(18, 26, 38, 235), outline=(255, 255, 255, 55), width=2)
    icon_holder.alpha_composite(icon.resize((150, 150), Image.Resampling.LANCZOS), (592, 76))
    logo.alpha_composite(icon_holder)
    path = OUTPUT_DIR / "faraz-automation-youtube-logo-simple.png"
    logo.convert("RGB").save(path, quality=95)
    return path


def render_luxury_logo(profile: Image.Image, icon: Image.Image) -> Path:
    logo = base_logo((9, 10, 14), (33, 26, 15))
    add_glow(logo, (538, 190), 220, (195, 152, 78), 100)
    add_glow(logo, (210, 650), 230, (126, 94, 32), 80)
    logo.alpha_composite(profile.resize((454, 454), Image.Resampling.LANCZOS), (173, 102))
    plate = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(plate)
    pdraw.rounded_rectangle((248, 594, 552, 692), radius=46, fill=(25, 18, 12, 230), outline=(201, 165, 95, 70), width=2)
    pdraw.text((350, 616), "FA", font=fit_font("FA", 120, 56, 42, bold=True), fill=(247, 239, 227, 255))
    logo.alpha_composite(plate)
    icon_holder = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    idraw = ImageDraw.Draw(icon_holder)
    idraw.rounded_rectangle((596, 74, 742, 220), radius=40, fill=(24, 18, 15, 238), outline=(201, 165, 95, 70), width=2)
    icon_holder.alpha_composite(icon.resize((142, 142), Image.Resampling.LANCZOS), (598, 76))
    logo.alpha_composite(icon_holder)
    path = OUTPUT_DIR / "faraz-automation-youtube-logo-luxury.png"
    logo.convert("RGB").save(path, quality=95)
    return path


def render_personal_logo(profile: Image.Image, icon: Image.Image) -> Path:
    logo = base_logo((9, 16, 24), (20, 34, 45))
    add_glow(logo, (540, 180), 200, (59, 130, 246), 100)
    add_glow(logo, (230, 650), 220, (245, 158, 11), 80)
    logo.alpha_composite(profile.resize((470, 470), Image.Resampling.LANCZOS), (165, 92))
    plate = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(plate)
    pdraw.rounded_rectangle((242, 598, 558, 698), radius=46, fill=(10, 23, 37, 225), outline=(255, 255, 255, 40), width=2)
    pdraw.text((350, 618), "FA", font=fit_font("FA", 120, 58, 42, bold=True), fill=(250, 251, 245, 255))
    logo.alpha_composite(plate)
    icon_holder = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    idraw = ImageDraw.Draw(icon_holder)
    idraw.rounded_rectangle((590, 74, 744, 228), radius=42, fill=(18, 26, 38, 235), outline=(255, 255, 255, 55), width=2)
    icon_holder.alpha_composite(icon.resize((150, 150), Image.Resampling.LANCZOS), (592, 76))
    logo.alpha_composite(icon_holder)
    path = OUTPUT_DIR / "faraz-automation-youtube-logo.png"
    logo.convert("RGB").save(path, quality=95)
    return path


def write_notes() -> Path:
    notes_path = OUTPUT_DIR / "channel-branding-notes.txt"
    notes = """Primary Personal Brand Set:
- faraz-automation-youtube-banner.png
- faraz-automation-youtube-logo.png

Additional Variants:
- faraz-automation-youtube-banner-simple.png
- faraz-automation-youtube-logo-simple.png
- faraz-automation-youtube-banner-luxury.png
- faraz-automation-youtube-logo-luxury.png

Suggested Channel Name: Faraz Automation
Suggested Handle: @farazautomation
Fallback Handle: @farazautomationhq
"""
    notes_path.write_text(notes, encoding="utf-8")
    return notes_path


def main() -> None:
    ensure_output_dir()
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Missing profile image: {PROFILE_PATH}")
    if not APP_ICON_PATH.exists():
        raise FileNotFoundError(f"Missing app icon: {APP_ICON_PATH}")

    profile_banner = crop_profile(Image.open(PROFILE_PATH), (580, 720), circular=False)
    profile_logo = crop_profile(Image.open(PROFILE_PATH), (470, 470), circular=True)
    app_icon = contain_image(Image.open(APP_ICON_PATH), (170, 170))

    outputs = [
        render_personal_banner(profile_banner, app_icon),
        render_personal_logo(profile_logo, contain_image(Image.open(APP_ICON_PATH), (150, 150))),
        render_simple_banner(crop_profile(Image.open(PROFILE_PATH), (520, 662), circular=False), contain_image(Image.open(APP_ICON_PATH), (146, 146))),
        render_simple_logo(profile_logo, contain_image(Image.open(APP_ICON_PATH), (150, 150))),
        render_luxury_banner(crop_profile(Image.open(PROFILE_PATH), (556, 716), circular=False), contain_image(Image.open(APP_ICON_PATH), (144, 144))),
        render_luxury_logo(crop_profile(Image.open(PROFILE_PATH), (454, 454), circular=True), contain_image(Image.open(APP_ICON_PATH), (142, 142))),
        write_notes(),
    ]

    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()