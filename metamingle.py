from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS
from fractions import Fraction
from exif_api import get_exif_info
import os

def add_exif_watermark(image_path, output_path=None, border_width=40, logo_path=None,
                       font_path=None, font_size=50, text_color=(0, 0, 0)):
    """
    Add a watermark with EXIF information and a white border to the image, 
	with a larger white frame at the bottom that includes the camera logo.
    
    Args:
        image_path (str): image file path as input.
        output_path (str, optional): Output image file path. If not specified, the original filename will be used with the suffix "_watermarked".
        border_width (int, optional): Left, right, and top border width, default is 40 pixels.
        logo_path (str, optional): Camera logo image file path.
		font_path (str, optional): Font file path. If not specified, the default font will be used.
        font_size (int, optional): Font size, default is 50.
        text_color (tuple, optional): Text color, default is black (0, 0, 0).
        
    Returns:
        str: output image path
    """
    # get exif informaion
    exif_info = get_exif_info(image_path)
    
    if output_path is None:
        file_name, file_ext = os.path.splitext(image_path)
        output_path = f"{file_name}_watermarked{file_ext}"
    
    img = Image.open(image_path)
    
    # Calculate the new image dimensions (with added border).
    width, height = img.size
    new_width = width + 2 * border_width
    
    # The bottom white border is five times the height of the original.
    bottom_height = 400  # 80*5=400
    new_height = height + border_width + bottom_height
    
    # Create a new image with a white background.
    new_img = Image.new('RGB', (new_width, new_height), (255, 255, 255))
    
    # Paste the original image at the center of the new image.
    new_img.paste(img, (border_width, border_width))
    
    # generate a drawing Object
    draw = ImageDraw.Draw(new_img)
    
    # Choise font
    try:
        font_regualr = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Regular.ttf", font_size)
        font_bold = ImageFont.truetype("./font/Saira_Semi_Condensed/SairaSemiCondensed-Bold.ttf", font_size)
    except:
        # use default font if any error occurs
        font = ImageFont.load_default()
    
    # prepare logo image, if provided
    logo_height = 0
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            
            # Calculate the appropriate size of the logo (height is 40% of the bottom area).
            logo_max_height = int(bottom_height * 0.4)
            logo_ratio = logo_max_height / logo.height
            logo_new_width = int(logo.width * logo_ratio)
            logo_new_height = logo_max_height
            
            # adjust logo size
            logo = logo.resize((logo_new_width, logo_new_height), Image.LANCZOS)
            
            # calculate the position of logo
            logo_x = (new_width - logo_new_width) // 2
            logo_y = height + border_width + 30  # Place the logo at the top of the bottom area.
            
            if logo.mode == 'RGBA':
                # If there is a transparent channel, special handling is required.
                new_img.paste(logo, (logo_x, logo_y), logo)
            else:
                new_img.paste(logo, (logo_x, logo_y))
                
            logo_height = logo_new_height + 30
            
        except Exception as e:
            print(f"An error occurred while adding the logo: {str(e)}")
            logo_height = 0
    
    line1 = f"Shot on {exif_info['camera_model']}"
    line2 = f"{exif_info['focal_length']}  {exif_info['aperture']}  {exif_info['shutter_speed']}  {exif_info['iso']}"
    
    if logo_height > 0:
        text_y = height + border_width + logo_height + 20
    else:
        text_y = height + border_width + 80  # If there is no logo, move the text downward.
    
    text_width = draw.textlength(line1, font=font_regualr)
    draw.text(((new_width - text_width) / 2, text_y), line1, font=font_regualr, fill=text_color)
    
    text_y += font_size + 20
    text_width = draw.textlength(line2, font=font_regualr)
    draw.text(((new_width - text_width) / 2, text_y), line2, font=font_regualr, fill=text_color)
    
    new_img.save(output_path)
    
    return output_path

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("usage: python3 metamingle.py <input path> [output path] [logo path]")
        sys.exit(1)
        
    image_path = sys.argv[1]
    output_path = None
    logo_path = None
    
    if len(sys.argv) > 2:
        output_path = sys.argv[2]
        
    if len(sys.argv) > 3:
        logo_path = sys.argv[3]
        
    result = add_exif_watermark(image_path, output_path, logo_path=logo_path)
    print(f"An image with a watermark has been created: {result}")
