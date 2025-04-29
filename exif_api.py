import math
from PIL import Image
from PIL.ExifTags import TAGS
from fractions import Fraction
from datetime import datetime

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
		image = Image.open(image_path)
		
		# Check if there is any EXIF data
		if hasattr(image, '_getexif') and image._getexif() is not None:
			exif_data = image._getexif()
			
			# Convert numeric tags to human-readable tag names
			exif = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}
			
			# 1. Aperture (F-Number)
			aperture = exif.get('FNumber')
			if aperture:
				result["aperture"] = f"f/{aperture}"
			
			# 2. Shutter Speed (Exposure Time) — convert to fractional seconds format
			shutter = exif.get('ExposureTime')
			if shutter:
				if isinstance(aperture, tuple) and len(shutter) == 2:
					numerator, denominator = shutter
					fraction = Fraction(numerator, denominator)
					result["shutter_speed"] = f"{fraction}s"
				else:
					try:
						fraction = Fraction(str(shutter)).limit_denominator()
						result["shutter_speed"] = f"{fraction}s"
					except:
						result["shutter_speed"] = f"{shutter}s"
			
			# 3. ISO Sensitivity
			iso = exif.get('ISOSpeedRatings')
			if iso is not None:
				result["iso"] = f"ISO{iso}"
			
			# 4. Camera Information
			make = exif.get('Make', '')
			if isinstance(make, bytes):
				make = make.decode('utf-8', errors='replace')
			
			if make:
				result["brand"] = f"{make}"
				
			model = exif.get('Model', '')
			if isinstance(model, bytes):
				model = model.decode('utf-8', errors='replace')
				
			if model:
				result["camera_model"] = f"{model}"
			
			# 5. Lens Focal Length (including equivalent full-frame focal length)
			focal_length = int(exif.get('FocalLength'))
			if focal_length:
				if isinstance(focal_length, tuple) and len(focal_length) == 2:
					actual_focal_mm = focal_length[0] / focal_length[1]
					
					crop_factor = 1.5 # Default to a 1.5× crop factor for Sony/Nikon/Fuji
					
					if make and isinstance(make, str):
						if 'canon' in make.lower():
							crop_factor = 1.6
					
					equivalent_focal_mm = actual_focal_mm * crop_factor
					
					result["focal_length"] = f"{actual_focal_mm}mm"
					result["equivalent_focal_length"] = f"{equivalent_focal_mm:.1f}mm"
				else:
					try:
						actual_focal_mm = focal_length
						equivalent_focal_mm = actual_focal_mm * 1.5
						result["focal_length"] = f"{focal_length}mm"
						result["equivalent_focal_length"] = f"{math.ceil(equivalent_focal_mm)}mm"
					except:
						result["focal_length"] = f"{focal_length}"
			
			# 6. Lens Model
			lens_model = exif.get('LensModel')
			if not lens_model:
				lens_model = exif.get('LensInfo', exif.get('Lens'))
			
			if lens_model:
				if isinstance(lens_model, bytes):
					lens_model = lens_model.decode('utf-8', errors='replace')
				result["lens_model"] = lens_model

			# 7. Photo Capture Time
			date_time = exif.get('DateTimeOriginal')
			
			if not date_time:
				date_time = exif.get('DateTime')
			
			if not date_time:
				date_time = exif.get('DateTimeDigitized')
				
			if date_time:
				if isinstance(date_time, bytes):
					date_time = date_time.decode('utf-8', errors='replace')
				
				try:
					dt = datetime.strptime(date_time, '%Y:%m:%d %H:%M:%S')
					result["time"] = dt.strftime('%Y-%m-%d %H:%M:%S')
				except ValueError:
					result["time"] = date_time
			
			# 8. Author
			author = exif.get('Artist')
			if author:
				try:
					author = author.decode(errors="ignore")
				except:
					author = author.decode('utf-8', 'ignore')
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
