import math
from PIL import Image
from PIL.ExifTags import TAGS
from fractions import Fraction
from datetime import datetime

def get_exif_info(image_path):
	"""
	从图像中提取EXIF信息并返回字典形式的摄影参数

	Args:
		image_path (str): 图像文件的路径
		
	Returns:
		dict: 包含摄影参数的字典
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
		# 移除了raw_exif，因为它可能包含无法序列化的值
	}
    
	try:
		# 打开图像
		image = Image.open(image_path)
		
		# 检查是否有EXIF数据
		if hasattr(image, '_getexif') and image._getexif() is not None:
			exif_data = image._getexif()
			
			# 将数字标签转换为可读标签名
			exif = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}
			
			# 1. 光圈 (F-Number)
			aperture = exif.get('FNumber')
			if aperture:
				# 光圈通常存储为元组，比如 (35, 10) 表示 f/3.5
				# if isinstance(aperture, tuple) and len(aperture) == 2:
				#     aperture_value = aperture[0] / aperture[1]
				#     result["aperture"] = f"f/{aperture_value}"
				# else:
				result["aperture"] = f"f/{aperture}"
			
			# 2. 快门速度 (Exposure Time) - 转换为分数每秒格式
			shutter = exif.get('ExposureTime')
			if shutter:
				# 快门速度通常存储为元组，比如 (1, 125) 表示 1/125秒
				if isinstance(aperture, tuple) and len(shutter) == 2:
					numerator, denominator = shutter
					# 创建分数表示
					fraction = Fraction(numerator, denominator)
					result["shutter_speed"] = f"{fraction}s"
				else:
					# 如果不是元组，尝试直接转换为分数
					try:
						fraction = Fraction(str(shutter)).limit_denominator()
						result["shutter_speed"] = f"{fraction}s"
					except:
						result["shutter_speed"] = f"{shutter}s"
			
			# 3. ISO感光度
			iso = exif.get('ISOSpeedRatings')
			if iso is not None:
				result["iso"] = f"ISO{iso}"
			
			# 4. 相机信息
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
			
			# 5. 镜头焦距（包括等效全画幅焦距）
			focal_length = int(exif.get('FocalLength'))
			if focal_length:
				if isinstance(focal_length, tuple) and len(focal_length) == 2:
					actual_focal_mm = focal_length[0] / focal_length[1]
					
					# 检查相机型号以确定正确的裁切系数
					crop_factor = 1.5  # 默认为索尼/尼康/富士的1.5倍
					
					# 根据相机制造商调整裁切系数
					if make and isinstance(make, str):
						if 'canon' in make.lower():
							crop_factor = 1.6
					
					# 计算等效全画幅焦距
					equivalent_focal_mm = actual_focal_mm * crop_factor
					
					result["focal_length"] = f"{actual_focal_mm}mm"
					result["equivalent_focal_length"] = f"{equivalent_focal_mm:.1f}mm"
				else:
					try:
						actual_focal_mm = focal_length
						equivalent_focal_mm = actual_focal_mm * 1.5  # 默认使用1.5倍系数
						result["focal_length"] = f"{focal_length}mm"
						result["equivalent_focal_length"] = f"{math.ceil(equivalent_focal_mm)}mm"
					except:
						result["focal_length"] = f"{focal_length}"
			
			# 6. 镜头型号
			lens_model = exif.get('LensModel')
			if not lens_model:
				# 尝试从LensInfo或其他标签中提取
				lens_model = exif.get('LensInfo', exif.get('Lens'))
			
			if lens_model:
				# 检查并转换bytes类型
				if isinstance(lens_model, bytes):
					lens_model = lens_model.decode('utf-8', errors='replace')
				result["lens_model"] = lens_model

			# 7. 照片拍摄时间
			# 首先尝试读取DateTimeOriginal（拍摄原始时间）
			date_time = exif.get('DateTimeOriginal')
			
			# 如果没有DateTimeOriginal，则尝试读取DateTime（文件创建时间）
			if not date_time:
				date_time = exif.get('DateTime')
			
			# 如果没有DateTime，则尝试读取DateTimeDigitized（数字化时间）
			if not date_time:
				date_time = exif.get('DateTimeDigitized')
				
			if date_time:
				# 检查并转换bytes类型
				if isinstance(date_time, bytes):
					date_time = date_time.decode('utf-8', errors='replace')
				
				# EXIF时间格式通常为 'YYYY:MM:DD HH:MM:SS'
				try:
					# 解析时间字符串并格式化
					dt = datetime.strptime(date_time, '%Y:%m:%d %H:%M:%S')
					result["time"] = dt.strftime('%Y-%m-%d %H:%M:%S')
				except ValueError:
					# 如果解析失败，直接使用原始字符串
					result["time"] = date_time
			
	except Exception as e:
		result["error"] = str(e)
		
	return result

	# 示例用法
if __name__ == "__main__":
	import sys
	import json

	def json_serializable(obj):
		"""处理无法序列化的对象类型"""
		if isinstance(obj, bytes):
			return obj.decode('utf-8', errors='replace')
		# 可以根据需要添加其他类型的处理
		return str(obj)

	if len(sys.argv) > 1:
		image_path = sys.argv[1]
		info = get_exif_info(image_path)
		
		# 打印格式化的JSON输出
		print(json.dumps(info, indent=2, ensure_ascii=False, default=json_serializable))
	else:
		print("使用方法: python exif_api.py <图像文件路径>")