"""
Draw the MetaMingle app icon and save it as icon.ico (all Windows sizes) and icon.png (preview).

    python make_icon.py

The design mirrors what the app makes: a photo in a white 4:5 frame with an
information bar at the bottom, on a rounded dark-blue tile.
"""
import os
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024                       # master drawing size; smaller sizes are scaled from it
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

TILE_TOP = (31, 52, 84)        # tile gradient
TILE_BOTTOM = (16, 27, 46)
SKY_TOP = (255, 179, 92)       # sunset sky gradient
SKY_BOTTOM = (240, 98, 120)
SUN = (255, 236, 179)
MOUNTAIN_BACK = (120, 70, 120)
MOUNTAIN_FRONT = (52, 46, 92)
SNOW = (255, 246, 240)
TEXT_DARK = (40, 40, 48)
TEXT_LIGHT = (150, 150, 158)
ACCENT = (232, 66, 66)         # the little "brand logo" dot


def vertical_gradient(size, top, bottom):
	w, h = size
	grad = Image.new("RGB", (1, h))
	for y in range(h):
		t = y / max(1, h - 1)
		grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
	return grad.resize((w, h))


def rounded_mask(size, radius):
	mask = Image.new("L", size, 0)
	ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
	return mask


def draw_icon(detail=True):
	"""Return the icon at S x S. detail=False drops the text lines for tiny sizes."""
	icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))

	# Rounded tile
	tile = vertical_gradient((S, S), TILE_TOP, TILE_BOTTOM).convert("RGBA")
	icon.paste(tile, (0, 0), rounded_mask((S, S), int(S * 0.22)))

	# White 4:5 card with a soft shadow
	card_h = int(S * 0.80)
	card_w = int(card_h * 0.8)
	cx, cy = (S - card_w) // 2, int(S * 0.095)
	shadow = Image.new("L", (S, S), 0)
	ImageDraw.Draw(shadow).rounded_rectangle((cx, cy + S * 0.025, cx + card_w, cy + card_h + S * 0.025),
										 radius=int(S * 0.03), fill=150)
	shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.025))
	icon.paste(Image.new("RGBA", (S, S), (0, 0, 0, 255)), (0, 0), shadow)
	ImageDraw.Draw(icon).rounded_rectangle((cx, cy, cx + card_w, cy + card_h), radius=int(S * 0.03), fill=(255, 255, 255, 255))

	# Photo inside the card (top part), bottom bar below it
	margin = int(card_w * 0.07)
	bar_h = int(card_h * (0.20 if detail else 0.16))
	px1, py1 = cx + margin, cy + margin
	px2, py2 = cx + card_w - margin, cy + card_h - bar_h
	pw, ph = px2 - px1, py2 - py1

	photo = vertical_gradient((pw, ph), SKY_TOP, SKY_BOTTOM).convert("RGBA")
	d = ImageDraw.Draw(photo)
	sun_r = pw * 0.14
	sun_c = (pw * 0.68, ph * 0.36)
	d.ellipse((sun_c[0] - sun_r, sun_c[1] - sun_r, sun_c[0] + sun_r, sun_c[1] + sun_r), fill=SUN)
	# Back range
	d.polygon([(-pw * 0.1, ph), (pw * 0.30, ph * 0.42), (pw * 0.55, ph * 0.70), (pw * 0.78, ph * 0.50),
			   (pw * 1.1, ph * 0.85), (pw * 1.1, ph)], fill=MOUNTAIN_BACK)
	# Front peak with snow cap
	peak = (pw * 0.36, ph * 0.52)
	left, right = (-pw * 0.05, ph), (pw * 0.85, ph)
	d.polygon([left, peak, right], fill=MOUNTAIN_FRONT)
	snow_t = 0.30
	sl = (peak[0] + (left[0] - peak[0]) * snow_t, peak[1] + (left[1] - peak[1]) * snow_t)
	sr = (peak[0] + (right[0] - peak[0]) * snow_t, peak[1] + (right[1] - peak[1]) * snow_t)
	notch = (peak[0] + pw * 0.02, sl[1] - ph * 0.03)
	d.polygon([peak, sr, (peak[0] + pw * 0.10, sr[1] - ph * 0.04), notch,
			   (peak[0] - pw * 0.08, sl[1] - ph * 0.02), sl], fill=SNOW)
	icon.paste(photo, (px1, py1))

	# Bottom information bar: brand dot + two text lines (like the Bottom Only template)
	draw = ImageDraw.Draw(icon)
	bar_cy = py2 + bar_h / 2
	if detail:
		dot_r = bar_h * 0.13
		draw.ellipse((S / 2 - dot_r, py2 + bar_h * 0.20 - dot_r * 0.2,
					  S / 2 + dot_r, py2 + bar_h * 0.20 + dot_r * 1.8), fill=ACCENT)
		line_h = bar_h * 0.11
		for i, (width, color) in enumerate(((0.46, TEXT_DARK), (0.62, TEXT_LIGHT))):
			y = py2 + bar_h * (0.52 + i * 0.22)
			draw.rounded_rectangle((S / 2 - card_w * width / 2, y, S / 2 + card_w * width / 2, y + line_h),
								   radius=line_h / 2, fill=color)
	else:
		line_h = bar_h * 0.22
		draw.rounded_rectangle((S / 2 - card_w * 0.25, bar_cy - line_h / 2, S / 2 + card_w * 0.25, bar_cy + line_h / 2),
							   radius=line_h / 2, fill=TEXT_DARK)
	return icon


def main():
	full = draw_icon(detail=True)
	simple = draw_icon(detail=False)
	frames = []
	for size in ICO_SIZES:
		source = full if size >= 48 else simple
		frames.append(source.resize((size, size), Image.LANCZOS))
	ico_path = os.path.join(HERE, "icon.ico")
	frames[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=frames[:-1])
	png_path = os.path.join(HERE, "icon.png")
	full.resize((512, 512), Image.LANCZOS).save(png_path)
	print(f"Saved {ico_path} and {png_path}")


if __name__ == "__main__":
	main()
