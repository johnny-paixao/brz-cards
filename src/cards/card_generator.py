from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


CARD_WIDTH = 768
CARD_HEIGHT = 1080


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Load a Windows system font. Falls back to Pillow default if unavailable.
    """
    font_path = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"

    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        return ImageFont.load_default()


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    """
    Draw centered text horizontally.
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (CARD_WIDTH - text_width) // 2
    draw.text((x, y), text, font=font, fill=fill)


def get_tier_colors(tier: str | None) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """
    Return background and border colors based on the player tier.
    """
    tier_normalized = (tier or "").upper()

    if tier_normalized == "ELITE":
        return (222, 178, 72), (255, 232, 150)

    if tier_normalized == "LEGENDARY":
        return (90, 45, 160), (218, 190, 255)

    if tier_normalized == "GOLD":
        return (190, 145, 45), (245, 210, 120)

    if tier_normalized == "SILVER":
        return (150, 150, 155), (230, 230, 235)

    return (130, 85, 45), (210, 160, 95)


def safe_int(value: object, default: int = 0) -> int:
    """
    Convert a value to int safely.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def generate_player_card(card_data: dict, output_path: str | Path) -> Path:
    """
    Generate a BRz Esports player card image from card score data.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    display_name = str(card_data.get("display_name", "Unknown"))
    overall = safe_int(card_data.get("overall_brz"))
    role = str(card_data.get("role") or "RIFLER").upper()
    tier = str(card_data.get("tier") or "BRONZE").upper()

    aim = safe_int(card_data.get("aim"))
    impact = safe_int(card_data.get("impact"))
    utility = safe_int(card_data.get("utility"))
    consistency = safe_int(card_data.get("consistency"))
    clutch = safe_int(card_data.get("clutch"))
    experience = safe_int(card_data.get("experience"))
    matches_analyzed = safe_int(card_data.get("matches_analyzed"))

    background_color, border_color = get_tier_colors(tier)

    image = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), (18, 18, 22))
    draw = ImageDraw.Draw(image)

    # Main card shape
    margin = 48
    draw.rounded_rectangle(
        (margin, margin, CARD_WIDTH - margin, CARD_HEIGHT - margin),
        radius=44,
        fill=background_color,
        outline=border_color,
        width=8,
    )

    # Inner panel
    draw.rounded_rectangle(
        (88, 220, CARD_WIDTH - 88, 830),
        radius=32,
        fill=(28, 28, 34),
        outline=(255, 255, 255),
        width=2,
    )

    # Fonts
    font_overall = load_font(96, bold=True)
    font_role = load_font(34, bold=True)
    font_title = load_font(58, bold=True)
    font_subtitle = load_font(26, bold=False)
    font_attr = load_font(34, bold=True)
    font_footer = load_font(22, bold=False)

    # Header
    draw.text((105, 95), str(overall), font=font_overall, fill=(20, 20, 24))
    draw.text((112, 185), role, font=font_role, fill=(20, 20, 24))

    draw.text((CARD_WIDTH - 255, 112), "BRz", font=font_title, fill=(20, 20, 24))
    draw.text((CARD_WIDTH - 255, 172), "ESPORTS", font=font_subtitle, fill=(20, 20, 24))

    # Player placeholder area
    draw.ellipse(
        (CARD_WIDTH // 2 - 110, 275, CARD_WIDTH // 2 + 110, 495),
        fill=(55, 55, 65),
        outline=border_color,
        width=5,
    )
    draw_centered_text(draw, "CS2", 350, load_font(58, bold=True), border_color)

    # Player name
    draw_centered_text(draw, display_name.upper(), 545, font_title, (255, 255, 255))
    draw_centered_text(draw, tier, 615, font_role, border_color)

    # Attributes
    attrs = [
        ("AIM", aim),
        ("IMP", impact),
        ("UTL", utility),
        ("CON", consistency),
        ("CLT", clutch),
        ("EXP", experience),
    ]

    left_x = 135
    right_x = 430
    start_y = 700
    row_gap = 72

    for index, (label, value) in enumerate(attrs):
        x = left_x if index % 2 == 0 else right_x
        y = start_y + (index // 2) * row_gap

        draw.text((x, y), f"{value:02d}", font=font_attr, fill=border_color)
        draw.text((x + 75, y + 6), label, font=font_attr, fill=(255, 255, 255))

    # Footer
    footer_text = f"{matches_analyzed} partidas analisadas • score BRz"
    draw_centered_text(draw, footer_text, 910, font_footer, (25, 25, 30))
    draw_centered_text(draw, "Data provided by Leetify / FACEIT when available", 942, font_footer, (25, 25, 30))

    image.save(output_path)

    return output_path