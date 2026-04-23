#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


APP_NAME = "Nova Image Scout"
ICON_NAME = "NovaImageScout"


def lerp_channel(start: int, end: int, ratio: float) -> int:
    return int(start + ((end - start) * ratio))


def build_gradient_background(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (15, 17, 23, 255))
    pixels = image.load()

    top = (32, 56, 110)
    middle = (57, 132, 255)
    bottom = (25, 203, 255)

    for y in range(size):
        ratio = y / (size - 1)
        if ratio < 0.55:
            local = ratio / 0.55
            color = tuple(lerp_channel(top[index], middle[index], local) for index in range(3))
        else:
            local = (ratio - 0.55) / 0.45
            color = tuple(lerp_channel(middle[index], bottom[index], local) for index in range(3))

        for x in range(size):
            pixels[x, y] = (*color, 255)

    return image


def draw_icon(size: int = 1024) -> Image.Image:
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (size * 0.12, size * 0.08, size * 0.86, size * 0.82),
        fill=(134, 198, 255, 84),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size * 0.05))
    icon.alpha_composite(glow)

    shell = build_gradient_background(size)
    shell_mask = Image.new("L", (size, size), 0)
    shell_mask_draw = ImageDraw.Draw(shell_mask)
    shell_mask_draw.rounded_rectangle(
        (size * 0.06, size * 0.06, size * 0.94, size * 0.94),
        radius=size * 0.22,
        fill=255,
    )
    icon.paste(shell, (0, 0), shell_mask)

    inner = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner_draw = ImageDraw.Draw(inner)
    inner_draw.rounded_rectangle(
        (size * 0.2, size * 0.22, size * 0.72, size * 0.68),
        radius=size * 0.09,
        fill=(14, 19, 30, 220),
        outline=(226, 238, 255, 96),
        width=max(8, size // 64),
    )
    inner_draw.rectangle(
        (size * 0.24, size * 0.31, size * 0.68, size * 0.35),
        fill=(91, 164, 255, 160),
    )
    inner_draw.polygon(
        [
            (size * 0.26, size * 0.59),
            (size * 0.39, size * 0.44),
            (size * 0.50, size * 0.53),
            (size * 0.60, size * 0.40),
            (size * 0.68, size * 0.59),
        ],
        fill=(95, 214, 255, 180),
    )
    inner_draw.ellipse(
        (size * 0.55, size * 0.29, size * 0.63, size * 0.37),
        fill=(255, 248, 214, 220),
    )
    icon.alpha_composite(inner)

    magnifier = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mag_draw = ImageDraw.Draw(magnifier)
    stroke = max(16, size // 38)
    mag_draw.ellipse(
        (size * 0.42, size * 0.42, size * 0.78, size * 0.78),
        outline=(242, 248, 255, 255),
        width=stroke,
    )
    mag_draw.line(
        [(size * 0.71, size * 0.71), (size * 0.87, size * 0.87)],
        fill=(242, 248, 255, 255),
        width=stroke,
        joint="curve",
    )
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight)
    highlight_draw.ellipse(
        (size * 0.47, size * 0.45, size * 0.64, size * 0.57),
        fill=(255, 255, 255, 70),
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(radius=size * 0.018))
    magnifier.alpha_composite(highlight)
    icon.alpha_composite(magnifier)

    return icon


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    generated_dir = project_dir / "packaging" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    png_path = generated_dir / f"{ICON_NAME}.png"
    icns_path = generated_dir / f"{ICON_NAME}.icns"
    ico_path = generated_dir / f"{ICON_NAME}.ico"

    canvas = draw_icon()
    canvas.save(png_path)
    canvas.save(icns_path)
    canvas.save(ico_path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Created icon assets for {APP_NAME}: {icns_path}")


if __name__ == "__main__":
    main()
