from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "marketing" / "youtube-channel"
PROFILE_PATH = ROOT / "profile.png"
APP_ICON_PATH = ROOT / "src" / "assets" / "icons" / "app.png"

THUMBNAIL_SIZE = (1280, 720)
WATERMARK_SIZE = (320, 320)


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
    glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
    base.alpha_composite(glow)


def circle_mask(size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    return mask


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def contain_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    source = image.convert("RGBA")
    source.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - source.width) // 2
    y = (size[1] - source.height) // 2
    canvas.alpha_composite(source, (x, y))
    return canvas


def crop_profile(image: Image.Image, size: tuple[int, int], circular: bool = False) -> Image.Image:
    source = image.convert("RGBA")
    scale = max(size[0] / source.width, size[1] / source.height)
    resized = source.resize((int(source.width * scale), int(source.height * scale)), Image.Resampling.LANCZOS)
    left = max((resized.width - size[0]) // 2, 0)
    top = max((resized.height - size[1]) // 2, 0)
    cropped = resized.crop((left, top, left + size[0], top + size[1]))
    cropped.putalpha(circle_mask(size) if circular else rounded_mask(size, 44))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(cropped)
    return canvas


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_channel_description() -> Path:
    text = """Channel Name: Faraz Automation
Handle: @farazautomation

Channel Description:
Welcome to Faraz Automation.

This channel is focused on automation systems, AI workflows, product demos, business tools, and practical digital solutions built for real use.

Here you will find:
- software product demos
- automation workflow walkthroughs
- AI-assisted business tools
- YouTube-ready project showcases
- practical system ideas for modern teams and businesses

Built and presented by Muhammad Faraz.

Business and collaboration content will focus on clarity, performance, clean execution, and real-world value.
"""
    path = OUTPUT_DIR / "youtube-channel-description.txt"
    path.write_text(text, encoding="utf-8")
    return path


def create_watermark() -> Path:
    watermark = vertical_gradient(WATERMARK_SIZE, (10, 18, 28), (18, 32, 44)).convert("RGBA")
    add_glow(watermark, (220, 70), 90, (59, 130, 246), 80)
    add_glow(watermark, (70, 250), 100, (245, 158, 11), 70)
    draw = ImageDraw.Draw(watermark)
    draw.rounded_rectangle((18, 18, 302, 302), radius=86, fill=(9, 15, 23, 210), outline=(255, 255, 255, 44), width=2)

    profile = crop_profile(Image.open(PROFILE_PATH), (174, 174), circular=True)
    watermark.alpha_composite(profile, (38, 34))

    icon = contain_image(Image.open(APP_ICON_PATH), (72, 72))
    icon_shell = Image.new("RGBA", WATERMARK_SIZE, (0, 0, 0, 0))
    shell_draw = ImageDraw.Draw(icon_shell)
    shell_draw.rounded_rectangle((212, 38, 286, 112), radius=24, fill=(18, 26, 38, 235), outline=(255, 255, 255, 44), width=2)
    icon_shell.alpha_composite(icon, (213, 39))
    watermark.alpha_composite(icon_shell)

    badge_font = fit_font("FA", 78, 44, 30, bold=True)
    label_font = fit_font("Faraz Automation", 190, 24, 14, bold=True)
    draw.rounded_rectangle((50, 214, 270, 292), radius=30, fill=(13, 22, 34, 226), outline=(255, 255, 255, 34), width=2)
    draw.text((160, 241), "FA", font=badge_font, fill=(250, 251, 245, 255), anchor="mm")
    draw.text((160, 279), "Faraz Automation", font=label_font, fill=(225, 232, 239, 255), anchor="ms")

    path = OUTPUT_DIR / "youtube-watermark-final.png"
    watermark.save(path)
    return path


def create_thumbnail_template() -> Path:
    thumbnail = vertical_gradient(THUMBNAIL_SIZE, (8, 14, 22), (18, 31, 43)).convert("RGBA")
    add_glow(thumbnail, (1060, 110), 260, (59, 130, 246), 84)
    add_glow(thumbnail, (180, 640), 260, (245, 158, 11), 60)
    draw = ImageDraw.Draw(thumbnail)

    for x in range(0, THUMBNAIL_SIZE[0], 64):
        draw.line((x, 0, x, THUMBNAIL_SIZE[1]), fill=(255, 255, 255, 12), width=1)
    for y in range(0, THUMBNAIL_SIZE[1], 64):
        draw.line((0, y, THUMBNAIL_SIZE[0], y), fill=(255, 255, 255, 12), width=1)

    left_panel = (56, 84, 830, 640)
    draw.rounded_rectangle(left_panel, radius=40, fill=(9, 16, 24, 220), outline=(255, 255, 255, 28), width=2)
    eyebrow_font = fit_font("FARAZ AUTOMATION", 280, 28, 18, bold=True)
    draw.rounded_rectangle((88, 114, 390, 168), radius=24, fill=(17, 95, 89, 255))
    draw.text((112, 126), "FARAZ AUTOMATION", font=eyebrow_font, fill=(244, 248, 252, 255))

    title_font = fit_font("YOUR VIDEO TITLE", 660, 88, 50, bold=True)
    subtitle_font = fit_font("Replace this text for each upload", 560, 34, 22, bold=False)
    draw.text((86, 216), "YOUR VIDEO", font=title_font, fill=(247, 248, 243, 255))
    draw.text((86, 324), "TITLE", font=title_font, fill=(255, 189, 64, 255))
    draw.text((90, 456), "Replace this text for each upload", font=subtitle_font, fill=(205, 217, 228, 255))
    draw.text((90, 504), "Use this as your reusable YouTube thumbnail base.", font=subtitle_font, fill=(205, 217, 228, 255))

    pill_font = fit_font("MessageCannon Demo", 220, 26, 18, bold=True)
    pills = [
        ("Demo", (17, 94, 89, 255)),
        ("Automation", (124, 58, 237, 255)),
        ("AI", (180, 83, 9, 255)),
    ]
    pill_x = 88
    for label, color in pills:
        bbox = draw.textbbox((0, 0), label, font=pill_font)
        width = (bbox[2] - bbox[0]) + 42
        draw.rounded_rectangle((pill_x, 564, pill_x + width, 614), radius=24, fill=color)
        draw.text((pill_x + 21, 576), label, font=pill_font, fill=(250, 251, 245, 255))
        pill_x += width + 16

    profile = crop_profile(Image.open(PROFILE_PATH), (360, 460), circular=False)
    portrait_shell = Image.new("RGBA", THUMBNAIL_SIZE, (0, 0, 0, 0))
    shell_draw = ImageDraw.Draw(portrait_shell)
    shell_draw.rounded_rectangle((872, 62, 1218, 546), radius=54, fill=(10, 18, 28, 188), outline=(255, 255, 255, 38), width=2)
    portrait_shell.alpha_composite(profile, (882, 74))
    thumbnail.alpha_composite(portrait_shell)

    icon = contain_image(Image.open(APP_ICON_PATH), (126, 126))
    badge = Image.new("RGBA", THUMBNAIL_SIZE, (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge)
    badge_draw.rounded_rectangle((1014, 530, 1154, 670), radius=34, fill=(14, 22, 34, 228), outline=(255, 255, 255, 40), width=2)
    badge.alpha_composite(icon, (1021, 537))
    badge_draw.text((874, 648), "Powered by MessageCannon", font=fit_font("Powered by MessageCannon", 330, 32, 22, bold=True), fill=(250, 251, 245, 255))
    thumbnail.alpha_composite(badge)

    path = OUTPUT_DIR / "youtube-thumbnail-template-final.png"
    thumbnail.convert("RGB").save(path, quality=95)
    return path


def main() -> None:
    ensure_output_dir()
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Missing profile image: {PROFILE_PATH}")
    if not APP_ICON_PATH.exists():
        raise FileNotFoundError(f"Missing app icon: {APP_ICON_PATH}")

    description = create_channel_description()
    watermark = create_watermark()
    thumbnail = create_thumbnail_template()

    print(description)
    print(watermark)
    print(thumbnail)


if __name__ == "__main__":
    main()