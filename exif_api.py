import math
from PIL import Image
from PIL.ExifTags import TAGS
from fractions import Fraction
from datetime import datetime

EXIF_IFD_POINTER = 0x8769

def _to_text(value):
	"""Convert an EXIF value to a clean string (handles bytes and NUL padding)."""
	if isinstance(value, bytes):
		value = value.decode('utf-8', errors='replace')
	return str(value).replace('\x00', '').strip()

def _to_fraction(value):
	"""Convert an EXIF rational (IFDRational, (num, den) tuple or number) to a Fraction, or None."""
	try:
		if isinstance(value, tuple):
			if len(value) != 2:
				return None
			return Fraction(int(value[0]), int(value[1]))
		numerator = getattr(value, 'numerator', None)
		denominator = getattr(value, 'denominator', None)
		if numerator is not None and denominator is not None:
			return Fraction(int(numerator), int(denominator))
		return Fraction(str(float(value))).limit_denominator(100000)
	except (ZeroDivisionError, ValueError, TypeError, OverflowError):
		return None

def _format_number(value):
	"""Format a number without a trailing '.0' (4.0 -> '4', 2.8 -> '2.8')."""
	return f"{round(float(value), 1):g}"

def _format_shutter(fraction):
	"""Format an exposure time: 1/200s for fast speeds, 2.5s for long exposures."""
	if fraction >= 1:
		return f"{_format_number(fraction)}s"
	if fraction.numerator == 1:
		return f"1/{fraction.denominator}s"
	reciprocal = 1 / fraction
	if reciprocal >= 4:
		return f"1/{round(reciprocal)}s"
	return f"{_format_number(fraction)}s"

def _read_exif(image):
	"""Return a {tag name: value} dict merging the main IFD and the Exif sub-IFD."""
	raw = image.getexif()
	if not raw:
		return {}
	merged = dict(raw)
	try:
		merged.update(raw.get_ifd(EXIF_IFD_POINTER))
	except Exception:
		pass
	return {TAGS.get(tag_id, tag_id): value for tag_id, value in merged.items()}

def get_exif_info(image_path):
	"""
	Extract EXIF information from an image and return photographic parameters as a dictionary.

	Args:
		image_path (str): Path to the image file

	Returns:
		dict: Dictionary containing photographic parameters
	"""
	result = {
		"brand": "Unknown",
		"camera_model": "Unknown",
		"aperture": "Unknown",
		"shutter_speed": "Unknown",
		"iso": "Unknown",
		"focal_length": "Unknown",
		"equivalent_focal_length": "Unknown",
		"lens_model": "Unknown",
		"time": "Unknown",
		"author": "@robbb",
		# Removed raw_exif because it may contain non-serializable values
	}

	try:
		with Image.open(image_path) as image:
			exif = _read_exif(image)

		if not exif:
			return result

		# 1. Aperture (F-Number)
		aperture = _to_fraction(exif.get('FNumber'))
		if aperture:
			result["aperture"] = f"f/{_format_number(aperture)}"

		# 2. Shutter Speed (Exposure Time) — convert to fractional seconds format
		shutter = _to_fraction(exif.get('ExposureTime'))
		if shutter:
			result["shutter_speed"] = _format_shutter(shutter)

		# 3. ISO Sensitivity
		iso = exif.get('ISOSpeedRatings', exif.get('PhotographicSensitivity'))
		if isinstance(iso, (tuple, list)):
			iso = iso[0] if iso else None
		if iso is not None:
			result["iso"] = f"ISO{iso}"

		# 4. Camera Information
		make = _to_text(exif.get('Make', ''))
		if make:
			result["brand"] = make

		model = _to_text(exif.get('Model', ''))
		if model:
			result["camera_model"] = model

		# 5. Lens Focal Length (including equivalent full-frame focal length)
		focal_length = _to_fraction(exif.get('FocalLength'))
		if focal_length:
			result["focal_length"] = f"{_format_number(focal_length)}mm"

			equivalent = exif.get('FocalLengthIn35mmFilm')
			if isinstance(equivalent, (int, float)) and equivalent > 0:
				result["equivalent_focal_length"] = f"{_format_number(equivalent)}mm"
			else:
				# Default to a 1.5× crop factor for Sony/Nikon/Fuji, 1.6× for Canon
				crop_factor = 1.6 if 'canon' in make.lower() else 1.5
				result["equivalent_focal_length"] = f"{math.ceil(float(focal_length) * crop_factor)}mm"

		# 6. Lens Model
		lens_model = exif.get('LensModel') or exif.get('LensInfo') or exif.get('Lens')
		if lens_model and isinstance(lens_model, (str, bytes)):
			lens_model = _to_text(lens_model)
			if lens_model:
				result["lens_model"] = lens_model

		# 7. Photo Capture Time
		date_time = exif.get('DateTimeOriginal') or exif.get('DateTime') or exif.get('DateTimeDigitized')
		if date_time:
			date_time = _to_text(date_time)
			try:
				dt = datetime.strptime(date_time, '%Y:%m:%d %H:%M:%S')
				result["time"] = dt.strftime('%Y-%m-%d %H:%M:%S')
			except ValueError:
				if date_time:
					result["time"] = date_time

		# 8. Author
		author = exif.get('Artist')
		if author:
			author = _to_text(author)
			if author:
				result["author"] = author

	except Exception as e:
		result["error"] = str(e)

	return result

if __name__ == "__main__":
	import sys
	import json

	def json_serializable(obj):
		"""Handle non-serializable object types"""
		if isinstance(obj, bytes):
			return obj.decode('utf-8', errors='replace')
		return str(obj)

	if len(sys.argv) > 1:
		image_path = sys.argv[1]
		info = get_exif_info(image_path)

		print(json.dumps(info, indent=2, ensure_ascii=False, default=json_serializable))
	else:
		print("Usage: python exif_api.py <image file path>")
