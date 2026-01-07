from PIL import Image, ImageDraw, ImageFont, ImageOps
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
	Automatically handles EXIF orientation and pads portrait images to 4:5 aspect ratio.
	"""

	# Get EXIF information
	exif_info = get_exif_info(image_path)

	if output_path is None:
		file_name, file_ext = os.path.splitext(image_path)
		output_path = f"{file_name}_watermarked{file_ext}"

	# Open original image
	img = Image.open(image_path)

	# [FIX] 自動根據 EXIF 資訊轉正照片 (解決直式照片變橫的問題)
	img = ImageOps.exif_transpose(img)

	width, height = img.size

	# Calculate actual dimensions based on image size and ratio parameters
	border_width = min(width, height) // border_ratio
	bottom_height = int(height / bottom_ratio)

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

	# 2. Logic for 4:5 Aspect Ratio (Portrait Only)
	final_width = content_width
	final_height = content_height
	offset_x = 0
	offset_y = 0

	# 如果是直向照片 (高 > 寬)，強制調整為 4:5 (0.8)
	if height > width:
		target_ratio = 4 / 5
		current_ratio = content_width / content_height

		if current_ratio < target_ratio:
			# 情況 A: 照片太細長 (例如 2:3 或 9:16) -> 增加左右白邊
			final_height = content_height
			final_width = int(final_height * target_ratio)
			# 計算左右需要補多少白邊才能置中
			offset_x = (final_width - content_width) // 2
			
		elif current_ratio > target_ratio:
			# 情況 B: 照片太寬 (例如正方形 1:1) -> 增加上下白邊
			final_width = content_width
			final_height = int(final_width / target_ratio)
			# 計算上下需要補多少白邊才能置中
			offset_y = (final_height - content_height) // 2

	# Create new image with white background (Final 4:5 canvas)
	new_img = Image.new('RGB', (final_width, final_height), (255, 255, 255))

	# Paste original image (Content Position + Offset)
	paste_x = base_img_x + offset_x
	paste_y = base_img_y + offset_y
	new_img.paste(img, (paste_x, paste_y))

	# Create drawing object
	draw = ImageDraw.Draw(new_img)

	# Calculate font size
	font_size = int(bottom_height / font_ratio)

	# Select font
	try:
		font_regular = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Regular.ttf", font_size)
		font_bold = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Bold.ttf", font_size)
	except:
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
		camera_text = f"{brand} {camera_model}"
		
		try:
			camera_text_width = draw.textlength(camera_text, font=font_bold)
			lens_text_width = draw.textlength(lens_model, font=font_regular) if has_lens_info else 0
		except AttributeError:
			camera_text_width = font_bold.getlength(camera_text)
			lens_text_width = font_regular.getlength(lens_model) if has_lens_info else 0
		
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
		text_width = lens_text_width if lens_text_width > 0 else font_regular.getlength(author)
		lens_x = camera_right_x - text_width
		lens_y = left_y + font_size + padding // 2
		line2_text = lens_model if has_lens_info and lens_model != "Unknown" else author
		
		draw.text((camera_x, left_y), camera_text, font=font_bold, fill=text_color)
		draw.text((lens_x, lens_y), line2_text, font=font_regular, fill=text_color)
		
		# Separator line
		separator_x = camera_x - padding
		separator_y1 = current_bottom_y + padding
		separator_y2 = current_bottom_y + bottom_height - padding
		draw.line([(separator_x, separator_y1), (separator_x, separator_y2)], fill=text_color, width=2)
		
	elif template_style == "bottom_only" or template_style == "full_frame":
		# Centered styles
		
		# Logo Logic
		logo_height = 0
		if logo_path and os.path.exists(logo_path):
			try:
				logo = Image.open(logo_path).convert("RGBA")
				logo_max_height = int(bottom_height / logo_ratio)
				logo_ratio_size = logo_max_height / logo.height
				logo_new_width = int(logo.width * logo_ratio_size)
				logo_new_height = logo_max_height
				logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
				
				# Center logo in the Final Width (Canvas)
				logo_x = int((final_width - logo_new_width) // 2)
				logo_y = current_bottom_y + padding
				
				if logo.mode == 'RGBA':
					new_img.paste(logo, (logo_x, logo_y), logo)
				else:
					new_img.paste(logo, (logo_x, logo_y))
				logo_height = logo_new_height + padding/2
			except Exception as e:
				print(f"Error adding logo: {str(e)}")

		shot_text = "Shot on "
		camera_model_text = camera_model
		line2 = f"{focal_length}  {aperture}  {shutter_speed}  {iso}"
		
		if logo_height > 0:
			text_y = current_bottom_y + logo_height + padding
		else:
			text_y = current_bottom_y + padding * 2

		# Draw centered text
		try:
			shot_text_width = draw.textlength(shot_text, font=font_regular)
			camera_model_width = draw.textlength(camera_model_text, font=font_bold)
			total_width = shot_text_width + camera_model_width
		except AttributeError:
			shot_text_width = font_regular.getlength(shot_text)
			camera_model_width = font_bold.getlength(camera_model_text)
			total_width = shot_text_width + camera_model_width

		# Center text based on FINAL width
		text_start_x = (final_width - total_width) / 2

		draw.text((text_start_x, text_y), shot_text, font=font_regular, fill=text_color)
		draw.text((text_start_x + shot_text_width, text_y), camera_model_text, font=font_bold, fill=text_color)

		text_y += font_size + padding // 2

		try:
			text_width = draw.textlength(line2, font=font_regular)
		except AttributeError:
			text_width = font_regular.getlength(line2)

		draw.text(((final_width - text_width) / 2, text_y), line2, font=font_regular, fill=text_color)

	new_img.save(output_path)

	return output_path
