# Image Watermarker with EXIF Information and White Border

This project provides both a Python command-line tool and an interactive GUI for adding customizable white borders and EXIF-based watermarks to images. It supports a larger bottom border to accommodate watermark text and an optional camera logo.

Inspire by https://github.com/7ryo/EXIFframe_maker

## Features

- **Command-Line Mode**: Use `new_metamingle.py` for scriptable batch processing.
- **Interactive GUI**: Launch `gui.py` to visually adjust parameters and preview results in real time.
- **White Borders**: Configure full-frame or bottom-only borders with proportional sizing.
- **EXIF Watermark**: Automatically extract camera metadata (model, focal length, aperture, shutter speed, ISO) and render it as centered text.
- **Camera Logo**: Optionally embed a logo image above the watermark text.
- **Custom Fonts & Colors**: Specify font files, sizes, and RGB text color.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourname/image-watermarker.git
   cd image-watermarker
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\\Scripts\\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   The `requirements.txt` should include:
   ```text
   Pillow
   piexif
   ```

   Ensure `tkinter` is available for the GUI (usually included with Python).

## Usage

### 1. Command-Line Interface (`new_metamingle.py`)

Process images via terminal using proportional parameters:

```bash
python new_metamingle.py IMAGE_PATH \
  [-o OUTPUT_PATH] \
  [-l LOGO_PATH] \
  [-t {full_frame,bottom_only}] \
  [--border-ratio FLOAT] \
  [--bottom-ratio FLOAT] \
  [--font-ratio FLOAT] \
  [--logo-ratio FLOAT] \
  [--padding-ratio FLOAT] \
  [--color R,G,B]
```

- **IMAGE_PATH**: Input image file (required).
- **-o, --output**: Output file path (default: appends `_watermarked`).
- **-l, --logo**: Camera logo PNG file to embed.
- **-t, --template**: `full_frame` for all-around border or `bottom_only` (default).
- **--border-ratio**: Inverse proportional factor for border thickness (default: 35).
- **--bottom-ratio**: Inverse for bottom border height (default: 8).
- **--font-ratio**: Inverse for font size relative to bottom height (default: 5).
- **--logo-ratio**: Inverse for logo height relative to bottom (default: 3.5).
- **--padding-ratio**: Inverse for spacing between logo and text (default: 6).
- **--color**: Text color as `R,G,B` (default: `0,0,0`).

**Example**:
```bash
python new_metamingle.py photos/IMG_001.jpg \
  -l logo/camera.png \
  -t full_frame \
  --color 255,255,255
```

### 2. Interactive GUI (`gui.py`)

Launch the graphical interface to load an image, tweak settings, and preview:

```bash
python gui.py
```

The GUI provides:

- **Select Image**: Choose any jpg, JPEG or PNG file.
- **Logo Selection**: Dropdown of `./logo/*.png` files.
- **Border Width**: Slider (50–300 px).
- **Font Size**: Slider (60–200 pt).
- **Generate Preview**: Render current settings on canvas.
- **Save Image**: Export final watermark image to chosen path.
- **Status**: Displays processing or error messages.

## Configuration and Assets

- **Logo Folder**: Place `.png` logos in `./logo/` to have them listed in the GUI.
- **Fonts**: Default fonts are under `./font/Saira_Semi_Condensed/`. You may specify others via CLI.

## Dependencies

- Python 3.7+ with `tkinter` support
- [Pillow](https://pypi.org/project/Pillow/)
- [piexif](https://pypi.org/project/piexif/) (or compatible EXIF API library)

## Contributing

Feel free to submit issues and pull requests:
1. Fork the repo
2. Create a feature branch: `git checkout -b feature/xyz`
3. Commit and push your changes
4. Open a Pull Request

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details.

