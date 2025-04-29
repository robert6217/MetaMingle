from PIL import Image, ImageDraw, ImageFont
from exif_api import get_exif_info
import os

def add_exif_watermark(image_path, output_path=None, logo_path=None, template_style="bottom_only",
                        text_color=(0, 0, 0),
                        border_ratio=35,     # border ratio (image dimension divided by this value)
                        bottom_ratio=8,      # bottom border height ratio (image height divided by this value)
                        font_ratio=5,        # font size ratio (bottom border height divided by this value)
                        logo_ratio=3.5,      # logo size ratio (bottom border height divided by this value)
                        padding_ratio=6):    # spacing ratio between logo and text (bottom border height divided by this value)
	"""
	Add a watermark containing EXIF information and proportionally scaled borders to an image.

	Args:
		image_path (str): Path to the input image file.
		output_path (str, optional): Path to the output image file. If not specified, the original filename will have "_watermarked" appended.
		logo_path (str, optional): Path to the camera logo image file.
		template_style (str, optional): Watermark template style. Valid options are "full_frame" (white border around the entire image), "bottom_only" (white border only at the bottom), or "classic" (classic layout).
		text_color (tuple, optional): Text color, default is black (0, 0, 0).
		border_ratio (float, optional): Border ratio, default is 35 (1/35 of the image dimension).
		bottom_ratio (float, optional): Bottom border height ratio, default is 8 (1/8 of the image height).
		font_ratio (float, optional): Font size ratio, default is 5 (1/5 of the bottom border height).
		logo_ratio (float, optional): Logo size ratio, default is 3.5 (1/3.5 of the bottom border height).
		padding_ratio (float, optional): Spacing ratio between the logo and text, default is 6 (1/6 of the bottom border height).

	Returns:
		str: Path to the output image file.
	"""

	# Get EXIF information
	exif_info = get_exif_info(image_path)

	if output_path is None:
		file_name, file_ext = os.path.splitext(image_path)
		output_path = f"{file_name}_watermarked1{file_ext}"

	# Open original image
	img = Image.open(image_path)
	width, height = img.size

	# Calculate actual dimensions based on image size and ratio parameters
	border_width = min(width, height) // border_ratio
	bottom_height = int(height / bottom_ratio)

	# Calculate new image dimensions based on template style
	if template_style == "full_frame":
		# Full frame style: white border all around
		new_width = width + 2 * border_width
		new_height = height + 2 * border_width + bottom_height
		img_position = (border_width, border_width)
		bottom_start_y = height + border_width  # Starting position of bottom area
	else:  # "bottom_only" or "classic"
		# Only bottom style: white border only at bottom
		new_width = width
		new_height = height + bottom_height
		img_position = (0, 0)
		bottom_start_y = height  # Starting position of bottom area

	# Create new image with white background
	new_img = Image.new('RGB', (new_width, new_height), (255, 255, 255))

	# Paste original image to the appropriate position in new image
	new_img.paste(img, img_position)

	# Create drawing object
	draw = ImageDraw.Draw(new_img)

	# Calculate font size
	font_size = int(bottom_height / font_ratio)

	# Select font
	try:
		font_regular = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Regular.ttf", font_size)
		font_bold = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Bold.ttf", font_size)
	except:
		# If any error occurs, use default font
		font_regular = ImageFont.load_default()
		font_bold = font_regular

	# Calculate padding
	padding = bottom_height // padding_ratio

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

	# Determine whether to display time
	# show_time = time_text != 'Unknown'

	# Draw different layouts based on template style
	if template_style == "classic":
		# Classic template layout
		
		# Calculate left and right positions of bottom area
		bottom_margin = padding
		left_x = bottom_margin
		
		# Left area - First line: Parameter information
		param_text = f"{focal_length}  {aperture}  {shutter_speed}  {iso}"
		left_y = bottom_start_y + 1.5*padding
		draw.text((left_x, left_y), param_text, font=font_bold, fill=text_color)
		
		# Left area - Second line: Time information
		if time_text != 'Unknown':
			time_y = left_y + font_size + padding // 2
			draw.text((left_x, time_y), time_text, font=font_regular, fill=text_color)
		
		# Calculate parameter text width for subsequent layout
		try:
			param_text_width = draw.textlength(param_text, font=font_bold)
			time_text_width = draw.textlength(time_text, font=font_regular) if time_text != 'Unknown' else 0
		except AttributeError:
			# For older versions of PIL
			param_text_width = font_bold.getlength(param_text)
			time_text_width = font_regular.getlength(time_text) if time_text != 'Unknown' else 0
			
		max_text_width = max(param_text_width, time_text_width)
		left_text_space = max_text_width + 2 * padding
		
		# Check if lens information exists
		has_lens_info = lens_model != "Unknown"
		
		# Calculate camera information text to measure width
		camera_text = f"{brand} {camera_model}"
		
		# Measure text width
		try:
			camera_text_width = draw.textlength(camera_text, font=font_bold)
			lens_text_width = draw.textlength(lens_model, font=font_regular) if has_lens_info else 0
			max_camera_width = max(camera_text_width, lens_text_width)
		except AttributeError:
			camera_text_width = font_bold.getlength(camera_text)
			lens_text_width = font_regular.getlength(lens_model) if has_lens_info else 0
			max_camera_width = max(camera_text_width, lens_text_width)
		
		# Calculate right margin same as left margin
		right_margin = bottom_margin
		
		# Calculate right position of camera info based on right margin
		camera_right_x = new_width - right_margin
		camera_x = camera_right_x - max_camera_width
		
		# Prepare logo image (if provided)
		logo_height = 0
		logo_width = 0
		
		if logo_path and os.path.exists(logo_path):
			try:
				logo = Image.open(logo_path).convert("RGBA")
				
				# Calculate appropriate size for logo (height as a proportion of bottom area)
				# Increase logo size (2.5 instead of original 3.5)
				logo_max_height = int(bottom_height/1.5)
				logo_ratio_size = logo_max_height / logo.height
				logo_new_width = int(logo.width * logo_ratio_size)
				logo_new_height = logo_max_height
				
				# Resize logo
				logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
				
				# Calculate logo position
				# First determine the leftmost position of camera info
				camera_left_x = camera_x
				
				# Minimum required spacing
				min_separator_distance = padding * 2
				
				# The right edge of logo should be to the left of camera info left edge minus spacing
				logo_right_x = camera_left_x - min_separator_distance
				
				# Calculate the left edge position of logo from right to left
				logo_x = int(logo_right_x - logo_new_width)  # Convert to integer
				
				# Ensure logo doesn't overlap with left side text
				min_logo_x = int(left_text_space + padding)  # Convert to integer
				logo_x = max(logo_x, min_logo_x)
				
				# Center logo vertically in bottom area
				logo_y = bottom_start_y + (bottom_height - logo_new_height) // 2
				
				# Paste logo
				if logo.mode == 'RGBA':
					# Special handling for transparent channel
					new_img.paste(logo, (logo_x, logo_y), logo)
				else:
					new_img.paste(logo, (logo_x, logo_y))
					
				logo_width = logo_new_width
				logo_height = logo_new_height
		
			except Exception as e:
				print(f"Error adding logo: {str(e)}")
				logo_width = 0
				logo_height = 0
		
		# Draw camera information
		text_width = lens_text_width if lens_text_width > 0 else font_regular.getlength(author)
		lens_x = camera_right_x - text_width
		lens_y = left_y + font_size + padding // 2
		line2_text = lens_model if has_lens_info and lens_model != "Unknow" else author
		draw.text((camera_x, left_y), camera_text, font=font_bold, fill=text_color)
		draw.text((lens_x, lens_y), line2_text, font=font_regular, fill=text_color)
		
		# Set separator line position
		separator_x = camera_x - padding

		# Draw separator line
		separator_y1 = bottom_start_y + padding
		separator_y2 = bottom_start_y + bottom_height - padding
		draw.line([(separator_x, separator_y1), (separator_x, separator_y2)], fill=text_color, width=3)
		
	elif template_style == "bottom_only" or template_style == "full_frame":
		# Original style code

		# Prepare logo image (if provided)
		logo_height = 0
		if logo_path and os.path.exists(logo_path):
			try:
				logo = Image.open(logo_path).convert("RGBA")
				
				# Calculate appropriate size for logo (height as a proportion of bottom area)
				logo_max_height = int(bottom_height / logo_ratio)
				logo_ratio_size = logo_max_height / logo.height
				logo_new_width = int(logo.width * logo_ratio_size)
				logo_new_height = logo_max_height
				
				# Resize logo
				logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
				
				# Calculate logo position - place at the top of bottom area
				logo_x = int((new_width - logo_new_width) // 2)
				logo_y = bottom_start_y + padding  # Offset from starting position of bottom area
				
				# Paste logo
				if logo.mode == 'RGBA':
					# Special handling for transparent channel
					new_img.paste(logo, (logo_x, logo_y), logo)
				else:
					new_img.paste(logo, (logo_x, logo_y))
					
				logo_height = logo_new_height + padding/2  # Add spacing
				
			except Exception as e:
				print(f"Error adding logo: {str(e)}")
				logo_height = 0

		shot_text = "Shot on "
		camera_model_text = camera_model
		line2 = f"{focal_length}  {aperture}  {shutter_speed}  {iso}"
		
		if logo_height > 0:
			text_y = bottom_start_y + logo_height + padding
		else:
			text_y = bottom_start_y + padding * 2  # Double the padding when no logo is provided

		# Draw camera model text - first line
		# Split and separately measure the widths of "Shot on" and the camera model so they can be rendered with different fonts
		try:
			shot_text_width = draw.textlength(shot_text, font=font_regular)
			camera_model_width = draw.textlength(camera_model_text, font=font_bold)
			total_width = shot_text_width + camera_model_width
		except AttributeError:
			shot_text_width = font_regular.getlength(shot_text)
			camera_model_width = font_bold.getlength(camera_model_text)
			total_width = shot_text_width + camera_model_width

		text_start_x = (new_width - total_width) / 2

		draw.text((text_start_x, text_y), shot_text, font=font_regular, fill=text_color)

		draw.text((text_start_x + shot_text_width, text_y), camera_model_text, font=font_bold, fill=text_color)

		text_y += font_size + padding // 2

		try:
			text_width = draw.textlength(line2, font=font_regular)
		except AttributeError:
			text_width = font_regular.getlength(line2)

		draw.text(((new_width - text_width) / 2, text_y), line2, font=font_regular, fill=text_color)

	new_img.save(output_path)

	return output_path

if __name__ == "__main__":
	import sys
	import argparse

	parser = argparse.ArgumentParser(description='Add an EXIF watermark to a photo')
	parser.add_argument('image_path', help='Path to the input image')
	parser.add_argument('-o', '--output', help='Path to the output image')
	parser.add_argument('-l', '--logo', help='Path to the camera logo image')
	parser.add_argument(
		'-t', '--template',
		choices=['full_frame', 'bottom_only', 'classic'],
		default='bottom_only',
		help='Watermark template style: "full_frame", "bottom_only", or "classic"'
	)
	parser.add_argument(
		'-br', '--border-ratio',
		type=float,
		default=35,
		help='Border ratio (image dimension divided by this value)'
	)
	parser.add_argument(
		'-bh', '--bottom-ratio',
		type=float,
		default=8,
		help='Bottom border height ratio (image height divided by this value)'
	)
	parser.add_argument(
		'-fr', '--font-ratio',
		type=float,
		default=5,
		help='Font size ratio (bottom border height divided by this value)'
	)
	parser.add_argument(
		'-lr', '--logo-ratio',
		type=float,
		default=3.5,
		help='Logo size ratio (bottom border height divided by this value)'
	)
	parser.add_argument(
		'-pr', '--padding-ratio',
		type=float,
		default=6,
		help='Spacing ratio between logo and text (bottom border height divided by this value)'
	)
	parser.add_argument(
		'-c', '--color',
		type=str,
		default='0,0,0',
		help='Text color in RGB format, comma-separated (e.g., "0,0,0")'
	)

	args = parser.parse_args()

	try:
		text_color = tuple(map(int, args.color.split(',')))
	except:
		text_color = (0, 0, 0)  # black by default

	result = add_exif_watermark(
		args.image_path, 
		output_path=args.output, 
		logo_path=args.logo,
		template_style=args.template,
		text_color=text_color,
		border_ratio=args.border_ratio,
		bottom_ratio=args.bottom_ratio,
		font_ratio=args.font_ratio,
		logo_ratio=args.logo_ratio,
		padding_ratio=args.padding_ratio
	)

	print(f"Watermarked image created: {result}")
