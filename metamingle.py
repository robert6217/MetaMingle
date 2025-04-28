from PIL import Image, ImageDraw, ImageFont
from exif_api import get_exif_info
import os

def add_exif_watermark(image_path, output_path=None, logo_path=None, template_style="bottom_only", 
						text_color=(0, 0, 0), 
						border_ratio=35,     # 邊框比例 (圖片尺寸除以此值)
						bottom_ratio=8,   # 底部高度比例 (圖片高度除以此值)
						font_ratio=5,       # 字體大小比例 (底部高度除以此值)
						logo_ratio=3.5,      # Logo 大小比例 (底部高度除以此值)
						padding_ratio=6):   # Logo 和文字間距比例 (底部高度除以此值)
	"""
	添加帶有 EXIF 信息的浮水印和按比例縮放的邊框到圖片。

	Args:
		image_path (str): 輸入圖片文件路徑。
		output_path (str, optional): 輸出圖片文件路徑。如果未指定，將在原始文件名後添加後綴 "_watermarked"。
		logo_path (str, optional): 相機 logo a圖片文件路徑。
		template_style (str, optional): 浮水印模板樣式，可選值為 "full_frame"（四周白框）、"bottom_only"（僅底部白邊）或 "classic"（經典版面）。
		text_color (tuple, optional): 文字顏色，默認為黑色 (0, 0, 0)。
		border_ratio (float, optional): 邊框比例，默認為 35 (圖片尺寸的 1/35)。
		bottom_ratio (float, optional): 底部高度比例，默認為 8 (圖片高度的 1/8)。
		font_ratio (float, optional): 字體大小比例，默認為 5 (底部高度的 1/5)。
		logo_ratio (float, optional): Logo 大小比例，默認為 3.5 (底部高度的 1/3.5)。
		padding_ratio (float, optional): Logo 和文字間距比例，默認為 6 (底部高度的 1/6)。
		
	Returns:
		str: 輸出圖片路徑
	"""
	# 獲取 EXIF 信息
	exif_info = get_exif_info(image_path)

	if output_path is None:
		file_name, file_ext = os.path.splitext(image_path)
		output_path = f"{file_name}_watermarked1{file_ext}"

	# 打開原始圖片
	img = Image.open(image_path)
	width, height = img.size

	# 根據圖片大小和比例參數計算實際尺寸
	border_width = min(width, height) // border_ratio
	bottom_height = int(height / bottom_ratio)

	# 根據模板樣式計算新圖片尺寸
	if template_style == "full_frame":
		# 全邊框樣式：四周都有白框
		new_width = width + 2 * border_width
		new_height = height + 2 * border_width + bottom_height
		img_position = (border_width, border_width)
		bottom_start_y = height + border_width  # 底部區域開始位置
	else:  # "bottom_only" 或 "classic"
		# 僅底部樣式：只有底部有白邊
		new_width = width
		new_height = height + bottom_height
		img_position = (0, 0)
		bottom_start_y = height  # 底部區域開始位置

	# 創建具有白色背景的新圖片
	new_img = Image.new('RGB', (new_width, new_height), (255, 255, 255))

	# 將原始圖片粘貼到新圖片的適當位置
	new_img.paste(img, img_position)

	# 創建繪圖對象
	draw = ImageDraw.Draw(new_img)

	# 計算字體大小
	font_size = int(bottom_height / font_ratio)

	# 選擇字體
	try:
		font_regular = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Regular.ttf", font_size)
		font_bold = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Bold.ttf", font_size)
	except:
		# 如果出現任何錯誤，使用默認字體
		font_regular = ImageFont.load_default()
		font_bold = font_regular

	# 計算間距
	padding = bottom_height // padding_ratio

	# 獲取EXIF文本信息
	brand = exif_info['brand']
	camera_model = exif_info['camera_model']
	focal_length = exif_info['focal_length']
	aperture = exif_info['aperture']
	shutter_speed = exif_info['shutter_speed']
	iso = exif_info['iso']
	lens_model = exif_info['lens_model']
	time_text = exif_info.get('time', 'Unknown')

	# 判斷是否顯示時間
	# show_time = time_text != 'Unknown'

	# 根據模板樣式繪製不同的布局
	if template_style == "classic":
		# 經典模板布局
		
		# 計算底部區域的左右兩側位置
		bottom_margin = padding
		left_x = bottom_margin
		right_area_start_x = int(0.75 * new_width)  # 右半區起始位置
		
		# 左側區域 - 第一行：參數信息
		param_text = f"{focal_length}  {aperture}  {shutter_speed}  {iso}"
		left_y = bottom_start_y + 2 * padding
		draw.text((left_x, left_y), param_text, font=font_bold, fill=text_color)
		
		# 左側區域 - 第二行：時間信息
		if time_text:
			time_y = left_y + font_size + padding // 2
			draw.text((left_x, time_y), time_text, font=font_regular, fill=text_color)
		
		# 右側區域
		# 準備 logo 圖片（如果提供）
		logo_height = 0
		logo_width = 0
		
		if logo_path and os.path.exists(logo_path):
			try:
				logo = Image.open(logo_path).convert("RGBA")
				
				# 計算 logo 的適當尺寸（高度為底部區域的一定比例）
				logo_max_height = int(bottom_height / logo_ratio)
				logo_ratio_size = logo_max_height / logo.height
				logo_new_width = int(logo.width * logo_ratio_size)
				logo_new_height = logo_max_height
				
				# 調整 logo 大小
				logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
				
				# 計算 logo 位置 - 置於右側區域
				logo_x = right_area_start_x
				logo_y = bottom_start_y + 2 * padding  # 從底部區域開始的位置再偏移
				
				# 粘貼 logo
				if logo.mode == 'RGBA':
					# 如果有透明通道，需要特殊處理
					new_img.paste(logo, (logo_x, logo_y), logo)
				else:
					new_img.paste(logo, (logo_x, logo_y))
					
				logo_width = logo_new_width
				logo_height = logo_new_height
				
			except Exception as e:
				print(f"添加 logo 時出錯: {str(e)}")
				logo_width = 0
				logo_height = 0
		
		# 繪製分隔線
		separator_x = right_area_start_x + logo_width + padding//2
		separator_y1 = bottom_start_y + padding
		separator_y2 = bottom_start_y + bottom_height - padding
		draw.line([(separator_x, separator_y1), (separator_x, separator_y2)], fill=text_color, width=2)
		
		# 繪製相機信息
		camera_x = separator_x + padding//2
		camera_y = separator_y1
		
		# 檢查是否有鏡頭信息
		has_lens_info = lens_model != "Unknown"
		
		if has_lens_info:
			# 有鏡頭信息時，顯示品牌和相機型號在第一行，鏡頭信息在第二行
			camera_text = f"{brand} {camera_model}"
			draw.text((camera_x, camera_y), camera_text, font=font_bold, fill=text_color)
			
			lens_y = camera_y + font_size + padding // 2
			draw.text((camera_x, lens_y), lens_model, font=font_regular, fill=text_color)
		else:
			# 無鏡頭信息時，居中顯示品牌和相機型號
			camera_text = f"{brand} {camera_model}"
			draw.text((camera_x, logo_y), camera_text, font=font_bold, fill=text_color)
		
	elif template_style == "bottom_only" or template_style == "full_frame":
		# 原始樣式的代碼

		# 準備 logo 圖片（如果提供）
		logo_height = 0
		if logo_path and os.path.exists(logo_path):
			try:
				logo = Image.open(logo_path).convert("RGBA")
				
				# 計算 logo 的適當尺寸（高度為底部區域的一定比例）
				logo_max_height = int(bottom_height / logo_ratio)
				logo_ratio_size = logo_max_height / logo.height
				logo_new_width = int(logo.width * logo_ratio_size)
				logo_new_height = logo_max_height
				
				# 調整 logo 大小
				logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
				
				# 計算 logo 位置 - 置於底部區域的上方
				logo_x = int((new_width - logo_new_width) // 2)
				logo_y = bottom_start_y + padding  # 從底部區域開始的位置再偏移
				
				# 粘貼 logo
				if logo.mode == 'RGBA':
					# 如果有透明通道，需要特殊處理
					new_img.paste(logo, (logo_x, logo_y), logo)
				else:
					new_img.paste(logo, (logo_x, logo_y))
					
				logo_height = logo_new_height + padding/2  # 增加間距
				
			except Exception as e:
				print(f"添加 logo 時出錯: {str(e)}")
				logo_height = 0

		# 準備 EXIF 文本
		shot_text = "Shot on "
		camera_model_text = camera_model
		line2 = f"{focal_length}  {aperture}  {shutter_speed}  {iso}"
		
		# 計算文本位置 - 基於底部開始位置和 logo 高度
		if logo_height > 0:
			text_y = bottom_start_y + logo_height + padding
		else:
			text_y = bottom_start_y + padding * 2  # 無 logo 時加倍間距

		# 繪製相機型號文本 - 第一行
		# 拆分並分別測量 "Shot on" 和相機型號的寬度，以便分別用不同字體渲染
		try:
			shot_text_width = draw.textlength(shot_text, font=font_regular)
			camera_model_width = draw.textlength(camera_model_text, font=font_bold)
			total_width = shot_text_width + camera_model_width
		except AttributeError:
			# 對於舊版本的 PIL，textlength 可能不可用
			shot_text_width = font_regular.getlength(shot_text)
			camera_model_width = font_bold.getlength(camera_model_text)
			total_width = shot_text_width + camera_model_width

		# 計算文本起始位置以使整體居中
		text_start_x = (new_width - total_width) / 2

		# 繪製 "Shot on" 文本
		draw.text((text_start_x, text_y), shot_text, font=font_regular, fill=text_color)

		# 繪製相機型號文本（粗體）
		draw.text((text_start_x + shot_text_width, text_y), camera_model_text, font=font_bold, fill=text_color)

		# 繪製第二行
		text_y += font_size + padding // 2

		try:
			text_width = draw.textlength(line2, font=font_regular)
		except AttributeError:
			text_width = font_regular.getlength(line2)

		draw.text(((new_width - text_width) / 2, text_y), line2, font=font_regular, fill=text_color)

	# 保存輸出圖片
	new_img.save(output_path)

	return output_path

if __name__ == "__main__":
	import sys
	import argparse

	parser = argparse.ArgumentParser(description='為照片添加 EXIF 浮水印')
	parser.add_argument('image_path', help='輸入圖片路徑')
	parser.add_argument('-o', '--output', help='輸出圖片路徑')
	parser.add_argument('-l', '--logo', help='相機 logo 圖片路徑')
	parser.add_argument('-t', '--template', choices=['full_frame', 'bottom_only', 'classic'], 
						default='bottom_only', help='浮水印模板樣式')
	parser.add_argument('-br', '--border-ratio', type=float, default=35, 
						help='邊框比例 (圖片尺寸除以此值)')
	parser.add_argument('-bh', '--bottom-ratio', type=float, default=8, 
						help='底部高度比例 (圖片高度除以此值)')
	parser.add_argument('-fr', '--font-ratio', type=float, default=5, 
						help='字體大小比例 (底部高度除以此值)')
	parser.add_argument('-lr', '--logo-ratio', type=float, default=3.5, 
						help='Logo 大小比例 (底部高度除以此值)')
	parser.add_argument('-pr', '--padding-ratio', type=float, default=6, 
						help='間距比例 (底部高度除以此值)')
	parser.add_argument('-c', '--color', type=str, default='0,0,0', 
						help='文字顏色 (RGB 格式，用逗號分隔，例如: 0,0,0)')

	args = parser.parse_args()

	# 解析文字顏色
	try:
		text_color = tuple(map(int, args.color.split(',')))
	except:
		text_color = (0, 0, 0)  # 默認黑色

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

	print(f"已創建帶有浮水印的圖片: {result}")