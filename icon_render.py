"""Renders the dynamic tray icon: a colored square with the glucose value."""
from PIL import Image, ImageDraw, ImageFont

STATUS_COLORS = {
    "urgent_low": "#e05252",
    "urgent_high": "#e05252",
    "low": "#e0a030",
    "high": "#e0a030",
    "stale": "#888888",
    "unknown": "#888888",
    "error": "#888888",
    "normal": "#3a3a3a",
}

_FONT_CACHE = {}


def _font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(name, size)
            _FONT_CACHE[size] = font
            return font
        except OSError:
            continue
    try:
        font = ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        font = ImageFont.load_default()  # older Pillow: fixed small bitmap font
    _FONT_CACHE[size] = font
    return font


def make_icon_image(text, status, size=64):
    """text: short label to draw, e.g. '112', '--', '?'."""
    color = STATUS_COLORS.get(status, STATUS_COLORS["normal"])
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = size // 6
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=color)

    font_size = size if len(text) <= 2 else int(size * 2 / len(text))
    font_size = max(10, min(font_size, size))
    font = _font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - text_w) / 2 - bbox[0]
    y = (size - text_h) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill="#ffffff")
    return img
