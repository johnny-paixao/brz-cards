from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from database.bigquery_client import (
    get_latest_player_card_by_player_id,
    get_player_profile,
)


BASE_DIR = Path(__file__).resolve().parents[2]

ASSETS_DIR = BASE_DIR / "assets"
TEMPLATES_DIR = ASSETS_DIR / "templates"
LOGOS_DIR = ASSETS_DIR / "logos"
FLAGS_DIR = ASSETS_DIR / "flags"
PLAYERS_DIR = ASSETS_DIR / "players"
PLACEHOLDERS_DIR = ASSETS_DIR / "placeholders"
GENERATED_DIR = ASSETS_DIR / "generated"
FONTS_DIR = ASSETS_DIR / "fonts"
FACEIT_LEVELS_DIR = ASSETS_DIR / "faceit_levels"

TEMPLATE_PATH = TEMPLATES_DIR / "brz_card_template.png"
LOGO_PATH = LOGOS_DIR / "brz_logo.png"

FONT_OVERALL_PATH = FONTS_DIR / "Anton-Regular.ttf"
FONT_MAIN_PATH = FONTS_DIR / "Montserrat-ExtraBold.ttf"
FONT_STATS_PATH = FONTS_DIR / "Montserrat-Bold.ttf"

CANVAS_SIZE = 600

GENERATED_DIR.mkdir(parents=True, exist_ok=True)


BOXES = {
    "logo": {"x": 88, "y": 265, "w": 123, "h": 123},
    "flag": {"x": 109, "y": 210, "w": 81, "h": 54},
    "role": {"x": 109, "y": 173, "w": 81, "h": 30},
    "overall": {"x": 109, "y": 89, "w": 81, "h": 81},
    "name": {"x": 225, "y": 349, "w": 249, "h": 49},
    "faceit_level": {"x": 270, "y": 520, "w": 60, "h": 60},
    "player_photo": {"x": 215, "y": 57, "w": 263, "h": 343},

    "aim": {"x": 229, "y": 414, "w": 41, "h": 33},
    "imp": {"x": 229, "y": 448, "w": 41, "h": 33},
    "utl": {"x": 229, "y": 482, "w": 41, "h": 33},

    "con": {"x": 410, "y": 414, "w": 41, "h": 33},
    "clt": {"x": 410, "y": 448, "w": 41, "h": 33},
    "exp": {"x": 410, "y": 482, "w": 41, "h": 33},
}


def _prepare_template_canvas(template: Image.Image) -> Image.Image:
    """
    The template file may be 800x800, but all layout coordinates were
    measured on a 600x600 Kittl canvas.

    Therefore, before drawing anything, we resize the template to 600x600.
    """
    template = template.convert("RGBA")

    if template.size == (CANVAS_SIZE, CANVAS_SIZE):
        return template

    return template.resize(
        (CANVAS_SIZE, CANVAS_SIZE),
        Image.Resampling.LANCZOS,
    )


def _font_candidates(kind: str) -> list[Path | str]:
    """
    Font priority:
    1. Project fonts inside assets/fonts
    2. Common Windows fonts
    """
    if kind == "overall":
        return [
            FONT_OVERALL_PATH,
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]

    if kind == "stats":
        return [
            FONT_STATS_PATH,
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]

    return [
        FONT_MAIN_PATH,
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ]


def _load_font(kind: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _font_candidates(kind):
        try:
            if isinstance(candidate, Path):
                if not candidate.exists():
                    continue

                return ImageFont.truetype(str(candidate), size=size)

            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    kind: str,
    max_w: int,
    max_h: int,
    start_size: int,
    min_size: int = 10,
    stroke_width: int = 0,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Reduce font size until the text fits inside the target box.
    """
    size = start_size

    while size >= min_size:
        font = _load_font(kind, size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)

        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        if text_w <= max_w and text_h <= max_h:
            return font

        size -= 1

    return _load_font(kind, min_size)


def _box_center(box: dict) -> tuple[float, float]:
    return (
        box["x"] + box["w"] / 2,
        box["y"] + box["h"] / 2,
    )


def _load_local_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _download_image(url: str) -> Image.Image | None:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception:
        return None


def _load_flag(country_code: str | None) -> Image.Image | None:
    if not country_code:
        country_code = "PT"

    flag_path = FLAGS_DIR / f"{country_code.lower()}.png"

    if not flag_path.exists():
        flag_path = FLAGS_DIR / "pt.png"

    if not flag_path.exists():
        return None

    return _load_local_image(flag_path)


def _load_logo() -> Image.Image | None:
    if not LOGO_PATH.exists():
        return None

    return _load_local_image(LOGO_PATH)


def _load_faceit_level_badge(level: int) -> Image.Image | None:
    """
    Load FACEIT level badge from assets/faceit_levels/{level}.png
    """
    print(f"[DEBUG] FACEIT level recebido: {level}")

    if not level or level < 1:
        print("[DEBUG] FACEIT level inválido")
        return None

    badge_path = FACEIT_LEVELS_DIR / f"{level}.png"
    print(f"[DEBUG] procurando badge em: {badge_path}")

    if not badge_path.exists():
        print("[DEBUG] badge não encontrada")
        return None

    print("[DEBUG] badge encontrada com sucesso")
    return Image.open(badge_path).convert("RGBA")


def _load_player_image(profile: dict) -> tuple[Image.Image | None, str | None]:
    """
    Image priority:
    1. photo_path from BigQuery
    2. assets/players/{player_id}.png
    3. assets/players/{player_id}.jpg
    4. assets/players/{player_id}.jpeg
    5. FACEIT avatar URL
    6. Steam avatar URL
    7. placeholder
    """
    player_id = profile.get("player_id")
    photo_path = profile.get("photo_path")
    faceit_avatar_url = profile.get("faceit_avatar_url")
    steam_avatar_url = profile.get("steam_avatar_url")

    if photo_path:
        local_path = BASE_DIR / photo_path

        if local_path.exists():
            return _load_local_image(local_path), "local"

    if player_id:
        local_candidates = [
            PLAYERS_DIR / f"{player_id}.png",
            PLAYERS_DIR / f"{player_id}.jpg",
            PLAYERS_DIR / f"{player_id}.jpeg",
        ]

        for local_path in local_candidates:
            if local_path.exists():
                return _load_local_image(local_path), "local"

    if faceit_avatar_url:
        image = _download_image(faceit_avatar_url)

        if image:
            return image, "avatar"

    if steam_avatar_url:
        image = _download_image(steam_avatar_url)

        if image:
            return image, "avatar"

    placeholder_path = PLACEHOLDERS_DIR / "default_avatar.png"

    if placeholder_path.exists():
        return _load_local_image(placeholder_path), "avatar"

    return None, None


def _paste_contain(base: Image.Image, image: Image.Image, box: dict) -> None:
    """
    Paste image inside the box preserving the whole image.
    Best for logos, badges and local cutout/player photos.
    """
    img = image.copy()
    img.thumbnail((box["w"], box["h"]), Image.Resampling.LANCZOS)

    x = box["x"] + (box["w"] - img.width) // 2
    y = box["y"] + (box["h"] - img.height) // 2

    base.alpha_composite(img, (x, y))


def _paste_cover(base: Image.Image, image: Image.Image, box: dict) -> None:
    """
    Fill the box completely, cropping if needed.
    Best for square avatars from Steam/FACEIT.
    """
    fitted = ImageOps.fit(
        image,
        (box["w"], box["h"]),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    base.alpha_composite(fitted, (box["x"], box["y"]))


def _paste_player_photo_bottom_aligned(
    base: Image.Image,
    image: Image.Image,
    box: dict,
    zoom: float = 1.00,
    x_offset: int = 0,
    y_offset: int = 0,
) -> None:
    """
    Paste player photo larger and bottom-aligned.
    This version does not clip the photo inside the box.
    """
    img = image.copy()

    scale = max(box["w"] / img.width, box["h"] / img.height)
    scale *= zoom

    new_w = int(img.width * scale)
    new_h = int(img.height * scale)

    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    x = box["x"] + (box["w"] - new_w) // 2 + x_offset
    y = box["y"] + box["h"] - new_h + y_offset

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.alpha_composite(img, (x, y))
    base.alpha_composite(layer)


def _paste_player_photo_framed(
    base: Image.Image,
    image: Image.Image,
    box: dict,
    scale_factor: float = 0.90,
    x_shift: int = 12,
    y_shift: int = 0,
) -> None:
    """
    Paste local community photo smaller, better framed, and visually shifted
    a bit to the right.

    This avoids the player looking too large.
    """
    img = image.copy()

    # Fit whole player inside the box instead of overscaling.
    scale = min(box["w"] / img.width, box["h"] / img.height)
    scale *= scale_factor

    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))

    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Center horizontally, then move a bit to the right.
    x = box["x"] + (box["w"] - new_w) // 2 + x_shift

    # Keep the player resting on the bottom area.
    y = box["y"] + box["h"] - new_h + y_shift

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.alpha_composite(img, (x, y))
    base.alpha_composite(layer)


def _get_faceit_badge_visual_box(size: int = 60) -> dict:
    """
    Create a bigger visual box centered on the original FACEIT level anchor.
    The template circle is bigger than the old 41x41 area, so this helps the
    badge appear centered and more visible.
    """
    src = BOXES["faceit_level"]

    cx = src["x"] + src["w"] / 2
    cy = src["y"] + src["h"] / 2

    return {
        "x": int(cx - size / 2),
        "y": int(cy - size / 2),
        "w": size,
        "h": size,
    }


def _crop_final_card_sides(image: Image.Image, crop_each_side: int = 40) -> Image.Image:
    """
    Crop left and right sides equally.
    Example: 600x600 -> 520x600 if crop_each_side=40
    """
    w, h = image.size

    if crop_each_side <= 0:
        return image

    if crop_each_side * 2 >= w:
        return image

    return image.crop((crop_each_side, 0, w - crop_each_side, h))

def _paste_image_in_box(
    base: Image.Image,
    image: Image.Image,
    box: dict,
    mode: str,
) -> None:
    if mode == "cover":
        _paste_cover(base, image, box)
        return

    _paste_contain(base, image, box)


def _paste_faceit_badge_emphasized(
    base: Image.Image,
    image: Image.Image,
    box: dict,
    render_size: int = 54,
) -> None:
    """
    Paste FACEIT badge centered in the bottom circle with more visual impact.
    The measured box is 41x41, but the rendered badge can be slightly bigger
    to look stronger inside the circle.
    """
    badge = image.copy()
    badge.thumbnail((render_size, render_size), Image.Resampling.LANCZOS)

    cx, cy = _box_center(box)

    # soft golden glow behind the badge
    glow_size = render_size + 14
    glow = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (0, 0, glow_size - 1, glow_size - 1),
        fill=(255, 190, 40, 80),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(6))

    glow_x = int(cx - glow.width / 2)
    glow_y = int(cy - glow.height / 2)

    badge_x = int(cx - badge.width / 2)
    badge_y = int(cy - badge.height / 2)

    base.alpha_composite(glow, (glow_x, glow_y))
    base.alpha_composite(badge, (badge_x, badge_y))


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: dict,
    kind: str,
    start_size: int,
    fill: tuple[int, int, int] = (255, 255, 255),
    stroke_fill: tuple[int, int, int] = (5, 22, 18),
    stroke_width: int = 2,
    min_size: int = 10,
) -> None:
    font = _fit_font(
        draw=draw,
        text=text,
        kind=kind,
        max_w=box["w"],
        max_h=box["h"],
        start_size=start_size,
        min_size=min_size,
        stroke_width=stroke_width,
    )

    cx, cy = _box_center(box)

    draw.text(
        (cx, cy),
        text,
        font=font,
        fill=fill,
        anchor="mm",
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def _draw_left_aligned_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: dict,
    kind: str,
    start_size: int,
    fill: tuple[int, int, int] = (255, 255, 255),
    stroke_fill: tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 0,
    min_size: int = 10,
    left_padding: int = 0,
) -> None:
    font = _fit_font(
        draw=draw,
        text=text,
        kind=kind,
        max_w=box["w"] - left_padding,
        max_h=box["h"],
        start_size=start_size,
        min_size=min_size,
        stroke_width=stroke_width,
    )

    x = box["x"] + left_padding
    y = box["y"] + box["h"] / 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        anchor="lm",
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _make_vertical_gradient(
    size: tuple[int, int],
    top_color: tuple[int, int, int],
    middle_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> Image.Image:
    width, height = size
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = gradient.load()

    for y in range(height):
        t = y / max(height - 1, 1)

        if t < 0.45:
            local_t = t / 0.45
            r = _lerp(top_color[0], middle_color[0], local_t)
            g = _lerp(top_color[1], middle_color[1], local_t)
            b = _lerp(top_color[2], middle_color[2], local_t)
        else:
            local_t = (t - 0.45) / 0.55
            r = _lerp(middle_color[0], bottom_color[0], local_t)
            g = _lerp(middle_color[1], bottom_color[1], local_t)
            b = _lerp(middle_color[2], bottom_color[2], local_t)

        for x in range(width):
            pixels[x, y] = (r, g, b, 255)

    return gradient


def _draw_overall_gold(
    base_img: Image.Image,
    text: str,
    box: dict,
    start_size: int = 76,
) -> Image.Image:
    """
    Draw overall with a strong golden effect:
    - dark shadow
    - golden glow
    - metallic gradient
    - golden outline
    """
    dummy_draw = ImageDraw.Draw(base_img)

    font = _fit_font(
        draw=dummy_draw,
        text=text,
        kind="overall",
        max_w=box["w"],
        max_h=box["h"],
        start_size=start_size,
        min_size=36,
        stroke_width=2,
    )

    cx, cy = _box_center(box)

    text_mask = Image.new("L", base_img.size, 0)
    mask_draw = ImageDraw.Draw(text_mask)
    mask_draw.text(
        (cx, cy),
        text,
        font=font,
        fill=255,
        anchor="mm",
        stroke_width=2,
        stroke_fill=255,
    )

    shadow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.text(
        (cx + 3, cy + 4),
        text,
        font=font,
        fill=(55, 30, 0, 220),
        anchor="mm",
        stroke_width=4,
        stroke_fill=(25, 15, 0, 230),
    )

    glow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))

    glow_specs = [
        (22, 110, (255, 170, 25)),
        (12, 155, (255, 214, 70)),
        (5, 210, (255, 244, 180)),
    ]

    for blur_radius, alpha, color in glow_specs:
        blurred = text_mask.filter(ImageFilter.GaussianBlur(blur_radius))
        colored = Image.new("RGBA", base_img.size, color + (0,))
        colored.putalpha(blurred.point(lambda p: int(p * alpha / 255)))
        glow_layer = Image.alpha_composite(glow_layer, colored)

    gradient = _make_vertical_gradient(
        base_img.size,
        top_color=(255, 250, 205),
        middle_color=(255, 215, 70),
        bottom_color=(202, 125, 15),
    )

    fill_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    fill_layer.paste(gradient, (0, 0), text_mask)

    outline_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    outline_draw = ImageDraw.Draw(outline_layer)
    outline_draw.text(
        (cx, cy),
        text,
        font=font,
        fill=(255, 255, 255, 0),
        anchor="mm",
        stroke_width=2,
        stroke_fill=(125, 78, 0, 230),
    )

    highlight_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight_layer)
    highlight_draw.text(
        (cx - 1, cy - 2),
        text,
        font=font,
        fill=(255, 255, 245, 80),
        anchor="mm",
    )

    result = Image.alpha_composite(base_img.convert("RGBA"), shadow_layer)
    result = Image.alpha_composite(result, glow_layer)
    result = Image.alpha_composite(result, fill_layer)
    result = Image.alpha_composite(result, outline_layer)
    result = Image.alpha_composite(result, highlight_layer)

    return result


def _draw_faceit_level_number(
    base_img: Image.Image,
    text: str,
    box: dict,
    start_size: int = 30,
) -> Image.Image:
    """
    Draw FACEIT level number only when the real level exists.
    This function should never receive a fake fallback value.
    """
    if not text:
        return base_img

    dummy_draw = ImageDraw.Draw(base_img)

    font = _fit_font(
        draw=dummy_draw,
        text=text,
        kind="main",
        max_w=box["w"],
        max_h=box["h"],
        start_size=start_size,
        min_size=14,
        stroke_width=1,
    )

    cx, cy = _box_center(box)

    glow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    for offset in range(1, 5):
        glow_draw.text(
            (cx, cy),
            text,
            font=font,
            fill=(255, 210, 50, 40),
            anchor="mm",
            stroke_width=offset,
            stroke_fill=(255, 180, 0, 60),
        )

    text_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    text_draw.text(
        (cx, cy),
        text,
        font=font,
        fill=(255, 225, 60),
        anchor="mm",
        stroke_width=1,
        stroke_fill=(95, 45, 0),
    )

    result = Image.alpha_composite(base_img, glow_layer)
    result = Image.alpha_composite(result, text_layer)

    return result


def _parse_faceit_level(value) -> int | None:
    """
    Parse FACEIT level safely.

    The card must not invent a FACEIT level.
    If the value is missing or invalid, return None.
    """
    if value in (None, ""):
        return None

    try:
        level = int(value)
    except (TypeError, ValueError):
        return None

    if 1 <= level <= 10:
        return level

    return None


def _build_player_data(profile: dict, card_data: dict) -> dict:
    faceit_level = _parse_faceit_level(profile.get("faceit_level"))

    return {
        "player_id": profile.get("player_id"),
        "name": profile.get("display_name") or "Unknown",
        "country_code": profile.get("country_code") or "PT",
        "faceit_level": faceit_level,
        "overall": card_data.get("overall_brz") or 0,
        "role": card_data.get("role") or "RIFLER",
        "aim": card_data.get("aim") or 0,
        "imp": card_data.get("impact") or 0,
        "utl": card_data.get("utility") or 0,
        "con": card_data.get("consistency") or 0,
        "clt": card_data.get("clutch") or 0,
        "exp": card_data.get("experience") or 0,
    }


def _render_card(
    template: Image.Image,
    profile: dict,
    player_data: dict,
) -> Image.Image:
    base = template.convert("RGBA")

    # 1) Player photo first, behind all text/logo/flag elements.
    player_image, image_source = _load_player_image(profile)

    if player_image:
        if image_source == "local":
            _paste_player_photo_bottom_aligned(
                base=base,
                image=player_image,
                box=BOXES["player_photo"],
                zoom=1.0,
                x_offset=10,
                y_offset=0,
            )
        else:
            _paste_image_in_box(
                base=base,
                image=player_image,
                box=BOXES["player_photo"],
                mode="cover",
            )

    # 2) Static BRz logo.
    logo = _load_logo()

    if logo:
        _paste_image_in_box(
            base=base,
            image=logo,
            box=BOXES["logo"],
            mode="contain",
        )

    # 3) Dynamic flag.
    flag = _load_flag(player_data["country_code"])

    if flag:
        _paste_image_in_box(
            base=base,
            image=flag,
            box=BOXES["flag"],
            mode="cover",
        )

    # 4) Overall with strong gold effect.
    base = _draw_overall_gold(
        base_img=base,
        text=str(player_data["overall"]),
        box=BOXES["overall"],
        start_size=76,
    )

    draw = ImageDraw.Draw(base)

    # 5) Role.
    _draw_centered_text(
        draw=draw,
        text=str(player_data["role"]).upper(),
        box=BOXES["role"],
        kind="main",
        start_size=24,
        fill=(255, 255, 255),
        stroke_fill=(4, 24, 18),
        stroke_width=2,
        min_size=12,
    )

    # 6) Player name.
    # Uppercase, left aligned, no black contour.
    _draw_left_aligned_text(
        draw=draw,
        text=str(player_data["name"]).upper(),
        box=BOXES["name"],
        kind="main",
        start_size=42,
        fill=(255, 255, 255),
        stroke_fill=(0, 0, 0),
        stroke_width=0,
        min_size=18,
        left_padding=0,
    )

    # 7) Dynamic stat values only.
    # Stat labels are already static in the template.
    stat_style = {
        "kind": "stats",
        "start_size": 31,
        "fill": (255, 255, 255),
        "stroke_fill": (4, 24, 18),
        "stroke_width": 2,
        "min_size": 14,
    }

    for stat_key in ["aim", "imp", "utl", "con", "clt", "exp"]:
        _draw_centered_text(
            draw=draw,
            text=str(player_data[stat_key]),
            box=BOXES[stat_key],
            **stat_style,
        )

    # Dynamic Faceit level.
    faceit_level = player_data.get("faceit_level")

    if faceit_level is not None:
        faceit_badge = _load_faceit_level_badge(int(faceit_level))

        if faceit_badge:
            bbox = faceit_badge.getbbox()
            if bbox:
                faceit_badge = faceit_badge.crop(bbox)

            badge_box = BOXES["faceit_level"]

            faceit_badge = faceit_badge.resize(
                (badge_box["w"], badge_box["h"]),
                Image.Resampling.LANCZOS,
            )

            base.alpha_composite(
                faceit_badge,
                (badge_box["x"], badge_box["y"]),
            )
        else:
            base = _draw_faceit_level_number(
                base_img=base,
                text=str(faceit_level),
                box=BOXES["faceit_level"],
                start_size=34,
            )
    return base

def generate_player_card(
    player_id: str,
    output_path: str | Path | None = None,
) -> str:
    """
    Generate the final BRz player card from BigQuery data.
    """
    profile = get_player_profile(player_id)

    if not profile:
        raise ValueError(f"Player profile not found for player_id={player_id}")

    card_data = get_latest_player_card_by_player_id(player_id)

    if not card_data:
        raise ValueError(f"No card score found for player_id={player_id}")

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    template = _prepare_template_canvas(_load_local_image(TEMPLATE_PATH))
    player_data = _build_player_data(profile, card_data)

    card = _render_card(
        template=template,
        profile=profile,
        player_data=player_data,
    )
    card = _crop_final_card_sides(card, 40)

    if output_path is None:
        output_path = GENERATED_DIR / f"{player_id}_card.png"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    card.save(output_path)

    return str(output_path)


def generate_player_card_preview() -> str:
    """
    Generate a preview using real BigQuery data.

    This intentionally does not hardcode FACEIT level, stats, role or name.
    If faceit_level is missing in BigQuery, nothing will be drawn in the
    FACEIT level area.
    """
    return generate_player_card(
        player_id="brz_johnny",
        output_path=GENERATED_DIR / "preview_card.png",
    )