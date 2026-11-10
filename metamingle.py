from PIL import Image, ImageDraw, ImageFont, ImageOps
from exif_api import get_exif_info
import io
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "font", "Saira_Semi_Condensed")
TEMPLATE_STYLES = ("bottom_only", "full_frame", "classic")
CANVAS_MODES = ("auto", "original", "ig", "4:5", "5:4")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
IG_RATIO = 4 / 5          # Instagram portrait post (width / height)
IG_LANDSCAPE_RATIO = 5 / 4  # Instagram landscape post (width / height)
IG_WIDTH = 1080           # Instagram's maximum post width in pixels

def ig_target_ratio(width, height):
	"""Instagram canvas for a photo: 5:4 for landscape photos, 4:5 for portrait and square ones."""
	return IG_LANDSCAPE_RATIO if width > height else IG_RATIO

def ig_crop_ratio(template_style="bottom_only", border_ratio=35, bottom_ratio=8, target_ratio=IG_RATIO):
	"""
	Width / height the PHOTO must have so that photo + borders come out at exactly
	target_ratio (4:5 portrait or 5:4 landscape) with no extra white padding.
	"""
	ratio = target_ratio * (1 + 1 / bottom_ratio)
	if template_style == "full_frame":
		# The frame width is based on the photo's shorter side
		portrait = ratio / (1 + 2 / border_ratio - 2 * target_ratio / border_ratio)
		if portrait <= 1:
			return portrait
		return target_ratio * (1 + 1 / bottom_ratio + 2 / border_ratio) - 2 / border_ratio
	return ratio

def center_crop_box(width, height, ratio):
	"""Largest centred (left, top, right, bottom) box with the given width / height ratio."""
	if width / height > ratio:
		crop_h = height
		crop_w = min(width, max(1, round(crop_h * ratio)))
	else:
		crop_w = width
		crop_h = min(height, max(1, round(crop_w / ratio)))
	left = (width - crop_w) // 2
	top = (height - crop_h) // 2
	return (left, top, left + crop_w, top + crop_h)

def _to_srgb(img, icc_profile):
	"""Convert an RGB image with an embedded non-sRGB profile (e.g. Adobe RGB) to sRGB."""
	if not icc_profile or img.mode != "RGB":
		return img
	try:
		from PIL import ImageCms
		source = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
		if "srgb" in ImageCms.getProfileDescription(source).lower():
			return img
		return ImageCms.profileToProfile(img, source, ImageCms.createProfile("sRGB"), outputMode="RGB")
	except Exception:
		return img

def add_exif_watermark(image_path, output_path=None, logo_path=None, template_style="bottom_only",
                        text_color=(0, 0, 0),
                        border_ratio=35,     # border ratio (image dimension divided by this value)
                        bottom_ratio=8,      # bottom border height ratio (image height divided by this value)
                        font_ratio=5,        # font size ratio (bottom border height divided by this value)
                        logo_ratio=3.5,      # logo size ratio (bottom border height divided by this value)
                        padding_ratio=6,     # spacing ratio between logo and text (bottom border height divided by this value)
                        canvas_ratio="auto", # "ig": 4:5 for portrait / 5:4 for landscape, "4:5" / "5:4": always that canvas,
                                             # "auto": portrait/square -> 4:5 and landscape untouched, "original": never pad
                        crop_box=None,       # (left, top, right, bottom) in pixels of the upright photo
                        crop_ratio=None,     # centred crop to this width / height, or "ig" for the Instagram crop
                                             # matching the photo's orientation (ignored when crop_box is given)
                        output_width=None):  # downscale the result to this width (e.g. 1080 for Instagram)
	"""
	Add a watermark containing EXIF information and proportionally scaled borders to an image.
	Automatically handles EXIF orientation, optional cropping, padding to an Instagram
	canvas (4:5 portrait or 5:4 landscape) and downscaling to a target width.
	"""
	if canvas_ratio not in CANVAS_MODES:
		raise ValueError(f"canvas_ratio must be one of {CANVAS_MODES}, got {canvas_ratio!r}")

	# Get EXIF information
	exif_info = get_exif_info(image_path)

	if output_path is None:
		file_name, file_ext = os.path.splitext(image_path)
		output_path = f"{file_name}_watermarked{file_ext}"

	# Open original image
	img = Image.open(image_path)
	icc_profile = img.info.get("icc_profile")

	# [FIX] 自動根據 EXIF 資訊轉正照片 (解決直式照片變橫的問題)
	img = ImageOps.exif_transpose(img)

	# Flatten transparency / palette images onto white so they can be pasted and saved as JPEG
	if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
		rgba = img.convert("RGBA")
		flattened = Image.new("RGB", rgba.size, (255, 255, 255))
		flattened.paste(rgba, mask=rgba.split()[-1])
		img = flattened
	elif img.mode != "RGB":
		img = img.convert("RGB")

	# Optional crop (manual box first, otherwise a centred crop to the requested ratio)
	if crop_box:
		left, top, right, bottom = (int(round(v)) for v in crop_box)
		left, top = max(0, left), max(0, top)
		right, bottom = min(img.width, right), min(img.height, bottom)
		if right - left >= 1 and bottom - top >= 1:
			img = img.crop((left, top, right, bottom))
	elif crop_ratio:
		if crop_ratio == "ig":
			# 依照片方向自動選擇: 直式 -> 4:5, 橫式 -> 5:4 (指定畫布時以畫布為準)
			if canvas_ratio == "4:5":
				crop_target = IG_RATIO
			elif canvas_ratio == "5:4":
				crop_target = IG_LANDSCAPE_RATIO
			else:
				crop_target = ig_target_ratio(img.width, img.height)
			crop_ratio = ig_crop_ratio(template_style, border_ratio, bottom_ratio, crop_target)
		img = img.crop(center_crop_box(img.width, img.height, crop_ratio))

	img = _to_srgb(img, icc_profile)

	width, height = img.size

	# Calculate actual dimensions based on image size and ratio parameters
	border_width = int(min(width, height) // border_ratio)
	bottom_height = int(height / bottom_ratio)

	# 成品畫布比例: 直式 4:5 / 橫式 5:4 (None 表示不補白)
	if canvas_ratio == "4:5":
		target_ratio = IG_RATIO
	elif canvas_ratio == "5:4":
		target_ratio = IG_LANDSCAPE_RATIO
	elif canvas_ratio == "ig":
		target_ratio = ig_target_ratio(width, height)
	elif canvas_ratio == "auto" and height >= width:
		target_ratio = IG_RATIO
	else:
		target_ratio = None

	if target_ratio == IG_RATIO and width > height:
		# 橫式照片放進 4:5 畫布: 文字區依畫布高度計算，字才不會太小
		frame = 2 * border_width if template_style == "full_frame" else 0
		bottom_height = max(bottom_height, int((width + frame) / IG_RATIO / (bottom_ratio + 1)))

	# 1. Calculate the "Content" dimensions (Image + Watermark area)
	if template_style == "full_frame":
		content_width = width + 2 * border_width
		content_height = height + 2 * border_width + bottom_height
		# Original paste position relative to content
		base_img_x = border_width
		base_img_y = border_width
		# Original bottom bar start Y relative to content
		base_bottom_start_y = height + border_width
	else:  # "bottom_only" or "classic"
		content_width = width
		content_height = height + bottom_height
		base_img_x = 0
		base_img_y = 0
		base_bottom_start_y = height

	# 2. Logic for 4:5 Aspect Ratio
	final_width = content_width
	final_height = content_height
	offset_x = 0
	offset_y = 0

	if target_ratio:
		current_ratio = content_width / content_height

		if current_ratio < target_ratio:
			# 情況 A: 照片太細長 (例如 2:3 或 9:16) -> 增加左右白邊
			final_height = content_height
			final_width = int(round(final_height * target_ratio))
			# 計算左右需要補多少白邊才能置中
			offset_x = (final_width - content_width) // 2

		elif current_ratio > target_ratio:
			# 情況 B: 照片太寬 (例如正方形 1:1 或橫式) -> 增加上下白邊
			final_width = content_width
			final_height = int(round(final_width / target_ratio))
			# 計算上下需要補多少白邊才能置中
			offset_y = (final_height - content_height) // 2

	# Create new image with white background (Final canvas)
	new_img = Image.new('RGB', (final_width, final_height), (255, 255, 255))

	# Paste original image (Content Position + Offset)
	paste_x = base_img_x + offset_x
	paste_y = base_img_y + offset_y
	new_img.paste(img, (paste_x, paste_y))

	# Create drawing object
	draw = ImageDraw.Draw(new_img)

	# Calculate font size
	font_size = max(1, int(bottom_height / font_ratio))

	# Select font
	def load_fonts(size):
		try:
			regular = ImageFont.truetype(os.path.join(FONT_DIR, "SairaSemiCondensed-Regular.ttf"), size)
			bold = ImageFont.truetype(os.path.join(FONT_DIR, "SairaSemiCondensed-Bold.ttf"), size)
		except OSError:
			try:
				regular = ImageFont.load_default(size=size)
			except TypeError:
				regular = ImageFont.load_default()
			bold = regular
		return regular, bold

	if not os.path.isfile(os.path.join(FONT_DIR, "SairaSemiCondensed-Regular.ttf")):
		print(f"Warning: fonts not found in {FONT_DIR}, falling back to the default font")
	font_regular, font_bold = load_fonts(font_size)

	# Calculate padding
	padding = int(bottom_height // padding_ratio)

	# Get EXIF text information
	brand = exif_info['brand']
	camera_model = exif_info['camera_model']
	focal_length = exif_info['focal_length']
	aperture = exif_info['aperture']
	shutter_speed = exif_info['shutter_speed']
	iso = exif_info['iso']
	lens_model = exif_info['lens_model']
	time_text = exif_info.get('time', 'Unknown')
	author = exif_info['author']

	# Update bottom starting position with offset
	current_bottom_y = base_bottom_start_y + offset_y

	# Draw different layouts
	if template_style == "classic":
		# Classic template layout
		
		# Calculate left and right positions
		bottom_margin = padding
		# 文字跟隨照片邊緣 (加上 offset_x)
		left_x = bottom_margin + offset_x 
		
		# Left area - First line: Parameter information
		param_text = f"{focal_length}  {aperture}  {shutter_speed}  {iso}"
		left_y = current_bottom_y + 1.5*padding
		draw.text((left_x, left_y), param_text, font=font_bold, fill=text_color)
		
		# Left area - Second line: Time information
		if time_text != 'Unknown':
			time_y = left_y + font_size + padding // 2
			draw.text((left_x, time_y), time_text, font=font_regular, fill=text_color)
		
		# Calculate text widths
		try:
			param_text_width = draw.textlength(param_text, font=font_bold)
			time_text_width = draw.textlength(time_text, font=font_regular) if time_text != 'Unknown' else 0
		except AttributeError:
			param_text_width = font_bold.getlength(param_text)
			time_text_width = font_regular.getlength(time_text) if time_text != 'Unknown' else 0
			
		max_text_width = max(param_text_width, time_text_width)
		left_text_space = max_text_width + 2 * padding
		
		has_lens_info = lens_model != "Unknown"
		camera_text = " ".join(part for part in (brand, camera_model) if part != "Unknown") or "Unknown"
		line2_text = lens_model if has_lens_info else author
		
		try:
			camera_text_width = draw.textlength(camera_text, font=font_bold)
			lens_text_width = draw.textlength(line2_text, font=font_regular)
		except AttributeError:
			camera_text_width = font_bold.getlength(camera_text)
			lens_text_width = font_regular.getlength(line2_text)
		
		# Right margin calculation
		right_margin = bottom_margin
		camera_right_x = final_width - right_margin - offset_x
		camera_x = camera_right_x - max(camera_text_width, lens_text_width)
		
		# Logo Logic
		logo_height = 0
		if logo_path and os.path.exists(logo_path):
			try:
				logo = Image.open(logo_path).convert("RGBA")
				logo_max_height = int(bottom_height/1.5)
				logo_ratio_size = logo_max_height / logo.height
				logo_new_width = int(logo.width * logo_ratio_size)
				logo_new_height = logo_max_height
				logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
				
				camera_left_x = camera_x
				min_separator_distance = padding * 2
				logo_right_x = camera_left_x - min_separator_distance
				logo_x = int(logo_right_x - logo_new_width)
				
				# Ensure logo doesn't overlap with left text
				min_logo_x = int(left_x + left_text_space) 
				logo_x = max(logo_x, min_logo_x)
				
				logo_y = current_bottom_y + (bottom_height - logo_new_height) // 2
				
				if logo.mode == 'RGBA':
					new_img.paste(logo, (logo_x, logo_y), logo)
				else:
					new_img.paste(logo, (logo_x, logo_y))
			except Exception as e:
				print(f"Error adding logo: {str(e)}")
		
		# Draw camera information
		lens_x = camera_right_x - lens_text_width
		lens_y = left_y + font_size + padding // 2
		
		draw.text((camera_x, left_y), camera_text, font=font_bold, fill=text_color)
		draw.text((lens_x, lens_y), line2_text, font=font_regular, fill=text_color)
		
		# Separator line
		separator_x = camera_x - padding
		separator_y1 = current_bottom_y + padding
		separator_y2 = current_bottom_y + bottom_height - padding
		draw.line([(separator_x, separator_y1), (separator_x, separator_y2)], fill=text_color, width=2)
		
	elif template_style == "bottom_only" or template_style == "full_frame":
		# Centered styles
		
		shot_text = "Shot on "
		camera_model_text = camera_model
		line2 = f"{focal_length}  {aperture}  {shutter_speed}  {iso}"

		# Load logo (resized later, once the final scale is known)
		logo = None
		if logo_path and os.path.exists(logo_path):
			try:
				logo = Image.open(logo_path).convert("RGBA")
			except Exception as e:
				print(f"Error adding logo: {str(e)}")

		def ink_extent(text, font):
			"""Pixels above / below the baseline actually covered by the text."""
			try:
				_, top, _, bottom = font.getbbox(text, anchor="ls")
				return max(0, -top), max(0, bottom)
			except (AttributeError, TypeError, ValueError):
				return font.size, 0

		def measure(scale):
			"""Sizes of every element of the block at the given scale."""
			size = max(1, int(font_size * scale))
			regular, bold = load_fonts(size)
			asc1 = max(ink_extent(shot_text, regular)[0], ink_extent(camera_model_text, bold)[0])
			desc1 = max(ink_extent(shot_text, regular)[1], ink_extent(camera_model_text, bold)[1])
			asc2, desc2 = ink_extent(line2, regular)
			logo_h = max(1, int(bottom_height / logo_ratio * scale)) if logo else 0
			logo_gap = int(padding * 0.75 * scale) if logo else 0
			line_gap = int(padding * 0.6 * scale)
			total = logo_h + logo_gap + asc1 + desc1 + line_gap + asc2 + desc2
			return dict(regular=regular, bold=bold, asc1=asc1, desc1=desc1, asc2=asc2, desc2=desc2,
						logo_h=logo_h, logo_gap=logo_gap, line_gap=line_gap, total=total)

		# The block (logo + two text lines) must fit inside the bottom bar with a margin
		margin = max(1, padding // 2)
		available = max(1, bottom_height - 2 * margin)
		scale = 1.0
		layout = measure(scale)
		for _ in range(6):
			if layout["total"] <= available:
				break
			scale *= available / layout["total"] * 0.98
			layout = measure(scale)
		font_regular, font_bold = layout["regular"], layout["bold"]

		# Centre the block vertically in the bottom bar
		y = current_bottom_y + max(margin, (bottom_height - layout["total"]) // 2)

		if logo:
			logo_new_height = layout["logo_h"]
			logo_new_width = max(1, int(logo.width * logo_new_height / logo.height))
			# Never let a very wide logo run past the canvas
			max_logo_width = final_width - 2 * padding
			if logo_new_width > max_logo_width > 0:
				logo_new_width = max_logo_width
				shrunk_height = max(1, int(logo.height * logo_new_width / logo.width))
				y += (logo_new_height - shrunk_height) // 2
				logo_new_height = shrunk_height
			logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
			new_img.paste(logo, ((final_width - logo_new_width) // 2, int(y)), logo)
			y += logo_new_height + layout["logo_gap"]

		# Line 1: "Shot on <model>", centred on the FINAL width, drawn on its baseline
		shot_text_width = font_regular.getlength(shot_text)
		camera_model_width = font_bold.getlength(camera_model_text)
		text_start_x = (final_width - shot_text_width - camera_model_width) / 2
		baseline1 = y + layout["asc1"]
		draw.text((text_start_x, baseline1), shot_text, font=font_regular, fill=text_color, anchor="ls")
		draw.text((text_start_x + shot_text_width, baseline1), camera_model_text, font=font_bold, fill=text_color, anchor="ls")

		# Line 2: shooting parameters
		baseline2 = baseline1 + layout["desc1"] + layout["line_gap"] + layout["asc2"]
		text_width = font_regular.getlength(line2)
		draw.text(((final_width - text_width) / 2, baseline2), line2, font=font_regular, fill=text_color, anchor="ls")

	# Downscale to the requested width (never upscale)
	if output_width and final_width > output_width:
		output_width = int(output_width)
		if target_ratio:
			output_height = int(round(output_width / target_ratio))
		else:
			output_height = max(1, int(round(final_height * output_width / final_width)))
		new_img = new_img.resize((output_width, output_height), Image.LANCZOS)

	if os.path.splitext(output_path)[1].lower() in (".jpg", ".jpeg"):
		new_img.save(output_path, quality=95, subsampling=0)
	else:
		new_img.save(output_path)

	return output_path

def collect_images(paths, exclude_suffix=None):
	"""Expand files / folders into a sorted list of image files (folders are not searched recursively)."""
	found = []
	for path in paths:
		if os.path.isdir(path):
			candidates = [os.path.join(path, name) for name in sorted(os.listdir(path))]
		else:
			candidates = [path]
		for candidate in candidates:
			stem, ext = os.path.splitext(os.path.basename(candidate))
			if ext.lower() not in IMAGE_EXTENSIONS or not os.path.isfile(candidate):
				continue
			# Skip files produced by an earlier run so a folder can be processed twice
			if exclude_suffix and stem.endswith(exclude_suffix):
				continue
			if candidate not in found:
				found.append(candidate)
	return found

def batch_process(image_paths, output_dir=None, suffix="_IG", progress=None, **options):
	"""
	Watermark several images with the same settings.

	Output files are written as <name><suffix>.jpg into output_dir (or next to each source).
	progress(done, total, path) is called before each image and once at the end.
	Returns a list of (source_path, output_path or None, error message or None).
	"""
	results = []
	total = len(image_paths)
	if output_dir:
		os.makedirs(output_dir, exist_ok=True)
	for index, image_path in enumerate(image_paths):
		if progress:
			progress(index, total, image_path)
		stem = os.path.splitext(os.path.basename(image_path))[0]
		target_dir = output_dir or os.path.dirname(os.path.abspath(image_path))
		output_path = os.path.join(target_dir, f"{stem}{suffix}.jpg")
		try:
			add_exif_watermark(image_path=image_path, output_path=output_path, **options)
			results.append((image_path, output_path, None))
		except Exception as e:
			results.append((image_path, None, str(e)))
	if progress:
		progress(total, total, None)
	return results

def parse_color(value):
	"""Parse an "R,G,B" string into a tuple of three 0-255 integers."""
	import argparse
	try:
		parts = tuple(int(p.strip()) for p in value.split(","))
	except ValueError:
		raise argparse.ArgumentTypeError(f"invalid color '{value}', expected R,G,B (e.g. 0,0,0)")
	if len(parts) != 3 or any(p < 0 or p > 255 for p in parts):
		raise argparse.ArgumentTypeError(f"invalid color '{value}', expected three values between 0 and 255")
	return parts

def positive_number(value):
	import argparse
	try:
		number = float(value)
	except ValueError:
		raise argparse.ArgumentTypeError(f"'{value}' is not a number")
	if number <= 0:
		raise argparse.ArgumentTypeError(f"'{value}' must be greater than 0")
	return number

def parse_crop(value):
	"""Parse --crop: "none", "ig" or a ratio such as "3:2" / "1:1" / "1.5"."""
	import argparse
	text = value.strip().lower()
	if text in ("none", "ig"):
		return text
	try:
		if ":" in text:
			w, h = text.split(":", 1)
			ratio = float(w) / float(h)
		else:
			ratio = float(text)
	except (ValueError, ZeroDivisionError):
		raise argparse.ArgumentTypeError(f"invalid crop '{value}', expected none, ig or a ratio like 3:2")
	if ratio <= 0:
		raise argparse.ArgumentTypeError(f"invalid crop '{value}', ratio must be greater than 0")
	return ratio

def main(argv=None):
	import argparse
	import sys

	parser = argparse.ArgumentParser(description="Add an EXIF information watermark to one or more photos.")
	parser.add_argument("images", nargs="+", metavar="IMAGE", help="Input image files and/or folders")
	parser.add_argument("-o", "--output", help="Output file (single image) or output folder (several images / a folder)")
	parser.add_argument("-l", "--logo", help="Path to the camera logo image")
	parser.add_argument("-t", "--template", choices=TEMPLATE_STYLES, default="bottom_only",
						help="Watermark template style (default: bottom_only)")
	parser.add_argument("-br", "--border-ratio", type=positive_number, default=35, help="Border ratio (default: 35)")
	parser.add_argument("-bh", "--bottom-ratio", type=positive_number, default=8, help="Bottom border height ratio (default: 8)")
	parser.add_argument("-fr", "--font-ratio", type=positive_number, default=5, help="Font size ratio (default: 5)")
	parser.add_argument("-lr", "--logo-ratio", type=positive_number, default=3.5, help="Logo size ratio (default: 3.5)")
	parser.add_argument("-pr", "--padding-ratio", type=positive_number, default=6, help="Spacing ratio (default: 6)")
	parser.add_argument("-c", "--color", type=parse_color, default=(0, 0, 0), help='Text color in RGB format (default: "0,0,0")')
	parser.add_argument("--ig", action="store_true",
						help=f"Instagram preset: same as --crop ig --canvas ig --width {IG_WIDTH} "
							 "(portrait photos become 4:5, landscape photos 5:4)")
	parser.add_argument("--crop", type=parse_crop, default=None,
						help='Centred crop before watermarking: "ig" (photo + border = exactly 4:5 for portrait / 5:4 for landscape, '
							 'or the ratio given by --canvas), a ratio like 3:2, or "none" (default)')
	parser.add_argument("--canvas", choices=CANVAS_MODES, default=None,
						help='Final canvas: "ig" = 4:5 for portrait and 5:4 for landscape photos, "4:5" / "5:4" force one of them, '
							 '"auto" pads only portrait/square photos to 4:5 (default), "original" never pads')
	parser.add_argument("--width", type=int, default=None, help=f"Downscale the result to this width in pixels (e.g. {IG_WIDTH})")
	parser.add_argument("--suffix", default=None, help="File name suffix for batch output (default: _watermarked, or _IG with --ig)")
	args = parser.parse_args(argv)

	if args.logo and not os.path.isfile(args.logo):
		parser.error(f"logo not found: {args.logo}")
	if args.width is not None and args.width <= 0:
		parser.error("--width must be greater than 0")
	for path in args.images:
		if not os.path.exists(path):
			parser.error(f"image not found: {path}")

	crop = args.crop if args.crop is not None else ("ig" if args.ig else "none")
	canvas = args.canvas or ("ig" if args.ig else "auto")
	width = args.width or (IG_WIDTH if args.ig else None)
	suffix = args.suffix or ("_IG" if args.ig else "_watermarked")

	if crop == "ig":
		crop_ratio = "ig"    # resolved per photo from its orientation
	elif crop == "none":
		crop_ratio = None
	else:
		crop_ratio = crop

	options = dict(
		logo_path=args.logo,
		template_style=args.template,
		text_color=args.color,
		border_ratio=args.border_ratio,
		bottom_ratio=args.bottom_ratio,
		font_ratio=args.font_ratio,
		logo_ratio=args.logo_ratio,
		padding_ratio=args.padding_ratio,
		canvas_ratio=canvas,
		crop_ratio=crop_ratio,
		output_width=width,
	)

	single_file = len(args.images) == 1 and os.path.isfile(args.images[0])
	if single_file:
		output_path = args.output
		if output_path is None and (args.ig or args.suffix):
			stem = os.path.splitext(args.images[0])[0]
			output_path = f"{stem}{suffix}.jpg"
		try:
			output = add_exif_watermark(image_path=args.images[0], output_path=output_path, **options)
		except Exception as e:
			print(f"Error: {e}", file=sys.stderr)
			return 1
		print(f"Saved: {output}")
		return 0

	images = collect_images(args.images, exclude_suffix=suffix)
	if not images:
		print("Error: no image files found", file=sys.stderr)
		return 1

	def report(done, total, path):
		if path:
			print(f"[{done + 1}/{total}] {os.path.basename(path)}")

	results = batch_process(images, output_dir=args.output, suffix=suffix, progress=report, **options)
	failed = [(src, err) for src, _, err in results if err]
	for src, err in failed:
		print(f"Error: {src}: {err}", file=sys.stderr)
	print(f"Done: {len(results) - len(failed)} saved, {len(failed)} failed")
	return 1 if failed else 0

if __name__ == "__main__":
	raise SystemExit(main())
