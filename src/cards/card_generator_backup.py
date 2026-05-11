from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from database.bigquery_client import (
    get_latest_player_card_by_player_id,
    get_player_profile,
)


BASE_DIR = Path(__file__).resolve().parents[2]

TEMPLATE_PATH = BASE_DIR / "assets" / "templates" / "brz_card_template.png"
LOGO_PATH = BASE_DIR / "assets" / "logos" / "brz_logo.png"
FLAGS_DIR = BASE_DIR / "assets" / "flags"
PLACEHOLDERS_DIR = BASE_DIR / "assets" / "placeholders"
GENERATED_DIR = BASE_DIR / "assets" / "generated"
CANVAS_SIZE = 600

# Render multiplier.
# The template is small, so we render at 3x for better quality.
SCALE = 3


def _prepare_template_canvas(template: Image.Image) -> Image.Image:
    """
    Resize the template to the layout size used in Kittl.
    All coordinates were measured on a 600x600 canvas.
    """
    if template.size == (CANVAS_SIZE, CANVAS_SIZE):
        return template.convert("RGBA")

    return template.convert("RGBA").resize(
        (CANVAS_SIZE, CANVAS_SIZE),
        Image.Resampling.LANCZOS,
    )


def s(value: int) -> int:
    """
    Scale a coordinate or size value.
    """
    return value * SCALE


def box(x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    """
    Scale a box from template coordinates.
    """
    return (s(x), s(y), s(w), s(h))


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Load a readable Windows font. Fallback to Pillow default.
    """
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/verdana.ttf",
    ]

    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size=s(size))
        except Exception:
            continue

    return ImageFont.load_default()


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str = "white",
    stroke_width: int = 1,
    stroke_fill: str = "#062b25",
) -> None:
    """
    Draw text with a subtle stroke for readability.
    """
    x, y = xy

    draw.text(
        (s(x), s(y)),
        text,
        font=font,
        fill=fill,
        stroke_width=s(stroke_width),
        stroke_fill=stroke_fill,
    )


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    center_x: int,
    y: int,
    font: ImageFont.ImageFont,
    fill: str = "white",
    stroke_width: int = 1,
    stroke_fill: str = "#062b25",
) -> None:
    """
    Draw centered text using unscaled coordinates.
    """
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=s(stroke_width))
    text_width = bbox[2] - bbox[0]
    x = s(center_x) - (text_width // 2)

    draw.text(
        (x, s(y)),
        text,
        font=font,
        fill=fill,
        stroke_width=s(stroke_width),
        stroke_fill=stroke_fill,
    )


def _download_image(url: str) -> Image.Image | None:
    """
    Download an image from URL and return it as RGBA.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception:
        return None


def _load_flag(country_code: str | None) -> Image.Image | None:
    """
    Load flag from assets/flags.
    Example: PT -> assets/flags/pt.png
    """
    if not country_code:
        return None

    flag_path = FLAGS_DIR / f"{country_code.lower()}.png"

    if not flag_path.exists():
        return None

    return Image.open(flag_path).convert("RGBA")


def _load_logo() -> Image.Image | None:
    """
    Load BRz logo.
    """
    if not LOGO_PATH.exists():
        return None

    return Image.open(LOGO_PATH).convert("RGBA")


def _load_player_image(profile: dict) -> Image.Image | None:
    """
    Image priority:
    1. local photo_path
    2. FACEIT avatar URL
    3. Steam avatar URL
    4. placeholder
    """
    photo_path = profile.get("photo_path")
    faceit_avatar_url = profile.get("faceit_avatar_url")
    steam_avatar_url = profile.get("steam_avatar_url")

    if photo_path:
        local_path = BASE_DIR / photo_path
        if local_path.exists():
            return Image.open(local_path).convert("RGBA")

    if faceit_avatar_url:
        image = _download_image(faceit_avatar_url)
        if image:
            return image

    if steam_avatar_url:
        image = _download_image(steam_avatar_url)
        if image:
            return image

    placeholder_path = PLACEHOLDERS_DIR / "default_avatar.png"

    if placeholder_path.exists():
        return Image.open(placeholder_path).convert("RGBA")

    return None


def _paste_fitted(
    base: Image.Image,
    image: Image.Image,
    target_box: tuple[int, int, int, int],
) -> None:
    """
    Paste image fitted inside target box.
    target_box = scaled x, y, width, height.
    """
    x, y, w, h = target_box
    fitted = ImageOps.fit(image, (w, h), method=Image.Resampling.LANCZOS)
    base.alpha_composite(fitted, (x, y))


def _paste_circle_avatar(
    base: Image.Image,
    image: Image.Image,
    x: int,
    y: int,
    size: int,
) -> None:
    """
    Paste a circular avatar with a BRz-style border.
    This is better for Steam/FACEIT avatars than using a huge square image.
    """
    scaled_size = s(size)
    fitted = ImageOps.fit(
        image,
        (scaled_size, scaled_size),
        method=Image.Resampling.LANCZOS,
    )

    mask = Image.new("L", (scaled_size, scaled_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, scaled_size - 1, scaled_size - 1), fill=255)

    avatar_layer = Image.new("RGBA", (scaled_size, scaled_size), (0, 0, 0, 0))
    avatar_layer.paste(fitted, (0, 0), mask)

    # Border
    border_size = s(8)
    border_layer = Image.new(
        "RGBA",
        (scaled_size + border_size * 2, scaled_size + border_size * 2),
        (0, 0, 0, 0),
    )
    border_draw = ImageDraw.Draw(border_layer)

    border_draw.ellipse(
        (0, 0, border_layer.size[0] - 1, border_layer.size[1] - 1),
        fill=(207, 188, 32, 255),
    )
    border_draw.ellipse(
        (
            border_size,
            border_size,
            border_layer.size[0] - border_size - 1,
            border_layer.size[1] - border_size - 1,
        ),
        fill=(8, 38, 48, 255),
    )

    border_layer.alpha_composite(avatar_layer, (border_size, border_size))

    base.alpha_composite(border_layer, (s(x) - border_size, s(y) - border_size))


def generate_player_card(player_id: str) -> str:
    """
    Generate the BRz player card using the BRz template.
    """
    profile = get_player_profile(player_id)

    if not profile:
        raise ValueError(f"Player profile not found for player_id={player_id}")

    card_data = get_latest_player_card_by_player_id(player_id)

    if not card_data:
        raise ValueError(f"No card score found for player_id={player_id}")

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    template = Image.open(TEMPLATE_PATH).convert("RGBA")

    # Upscale template for better final quality.
    original_width, original_height = template.size
    template = template.resize(
        (original_width * SCALE, original_height * SCALE),
        Image.Resampling.LANCZOS,
    )

    draw = ImageDraw.Draw(template)

    # Fonts tuned for 338x505 base template rendered at 3x.
    font_overall = _load_font(46, bold=True)
    font_role = _load_font(12, bold=True)
    font_name = _load_font(19, bold=True)

    font_stat_value = _load_font(27, bold=True)
    font_stat_label = _load_font(18, bold=True)

    # Data
    display_name = str(profile.get("display_name") or "Unknown")
    country_code = str(profile.get("country_code") or "PT")

    overall = str(card_data.get("overall_brz", 0))
    role = str(card_data.get("role") or "RIFLER").upper()

    aim = str(card_data.get("aim", 0))
    impact = str(card_data.get("impact", 0))
    utility = str(card_data.get("utility", 0))
    consistency = str(card_data.get("consistency", 0))
    clutch = str(card_data.get("clutch", 0))
    experience = str(card_data.get("experience", 0))

    # Layout coordinates in original template units.
    # Template base size expected: 338x505.
    overall_x = 30
    overall_y = 98

    role_center_x = 56
    role_y = 146

    flag_box = box(27, 179, 55, 37)
    logo_box = box(25, 248, 60, 60)

    avatar_x = 116
    avatar_y = 92
    avatar_size = 126

    name_center_x = 169
    name_y = 312

    left_value_x = 34
    left_label_x = 104

    right_label_x = 190
    right_value_x = 270

    stat_y_1 = 355
    stat_y_2 = 408
    stat_y_3 = 458

    # Player avatar
    player_image = _load_player_image(profile)

    if player_image:
        _paste_circle_avatar(
            base=template,
            image=player_image,
            x=avatar_x,
            y=avatar_y,
            size=avatar_size,
        )

    # Flag
    flag_image = _load_flag(country_code)

    if flag_image:
        _paste_fitted(template, flag_image, flag_box)

    # BRz logo
    logo_image = _load_logo()

    if logo_image:
        _paste_fitted(template, logo_image, logo_box)

    # Overall + role
    _draw_text(draw, (overall_x, overall_y), overall, font_overall, stroke_width=1)
    _draw_centered_text(draw, role, role_center_x, role_y, font_role, stroke_width=1)

    # Name
    _draw_centered_text(draw, display_name, name_center_x, name_y, font_name, stroke_width=1)

    # Stats left
    _draw_text(draw, (left_value_x, stat_y_1), aim, font_stat_value, stroke_width=1)
    _draw_text(draw, (left_label_x, stat_y_1 + 8), "AIM", font_stat_label, stroke_width=1)

    _draw_text(draw, (left_value_x, stat_y_2), impact, font_stat_value, stroke_width=1)
    _draw_text(draw, (left_label_x, stat_y_2 + 8), "IMP", font_stat_label, stroke_width=1)

    _draw_text(draw, (left_value_x, stat_y_3), utility, font_stat_value, stroke_width=1)
    _draw_text(draw, (left_label_x, stat_y_3 + 8), "UTL", font_stat_label, stroke_width=1)

    # Stats right
    _draw_text(draw, (right_label_x, stat_y_1 + 8), "CON", font_stat_label, stroke_width=1)
    _draw_text(draw, (right_value_x, stat_y_1), consistency, font_stat_value, stroke_width=1)

    _draw_text(draw, (right_label_x, stat_y_2 + 8), "CLT", font_stat_label, stroke_width=1)
    _draw_text(draw, (right_value_x, stat_y_2), clutch, font_stat_value, stroke_width=1)

    _draw_text(draw, (right_label_x, stat_y_3 + 8), "EXP", font_stat_label, stroke_width=1)
    _draw_text(draw, (right_value_x, stat_y_3), experience, font_stat_value, stroke_width=1)

    output_path = GENERATED_DIR / f"{player_id}_card.png"
    template.save(output_path)

    return str(output_path)