from pathlib import Path

from PIL import Image, ImageDraw


def create_portugal_flag(output_path: str) -> None:
    """
    Create a simplified Portugal flag asset for the BRz Cards MVP.

    This is not an official detailed flag because it does not include
    the coat of arms. It is only a temporary visual asset.
    """
    width = 240
    height = 160

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    green_width = int(width * 0.4)

    # Portugal flag simplified: green field on the left, red field on the right.
    draw.rectangle((0, 0, green_width, height), fill=(0, 102, 0))
    draw.rectangle((green_width, 0, width, height), fill=(255, 0, 0))

    # Simplified yellow circle to suggest the central coat of arms area.
    circle_radius = 28
    circle_center_x = green_width
    circle_center_y = height // 2

    draw.ellipse(
        (
            circle_center_x - circle_radius,
            circle_center_y - circle_radius,
            circle_center_x + circle_radius,
            circle_center_y + circle_radius,
        ),
        fill=(255, 204, 0),
        outline=(255, 255, 255),
        width=3,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)

    print(f"Flag created: {output}")


def main() -> None:
    create_portugal_flag("assets/flags/pt.png")


if __name__ == "__main__":
    main()