# MetaMingle - Photo Watermarking Tool with EXIF Information

MetaMingle is a powerful Python application for adding professional watermarks with EXIF information to your photos. It extracts camera metadata automatically and offers both command-line and GUI interfaces for maximum flexibility.

## Features

- **Multiple Template Styles**: Choose from three layouts:
  - **Bottom Only**: Clean white border at the bottom
  - **Full Frame**: Elegant white border around the entire image
  - **Classic**: Professional layout with parameters on the left and camera info on the right
- **EXIF Information Extraction**: Automatically pulls camera metadata including:
  - Camera brand and model
  - Lens information
  - Aperture, shutter speed, ISO
  - Focal length
  - Capture date/time
- **Instagram-ready output**:
  - **Orientation aware**: portrait and square photos become 4:5, landscape photos become 5:4 (either can be forced)
  - **IG crop / canvas**: the photo is either cropped so that photo + border fill the canvas exactly, or centred uncropped on a white 4:5 / 5:4 canvas
  - **1080 px export**: results are downscaled to 1080 x 1350 px (portrait) or 1080 x 864 px (landscape)
  - **Batch export**: process a whole folder with the same settings
- **Custom Logo Support**: Add your favorite camera brand logos
- **Proportional Sizing**: All elements scale proportionally based on image dimensions
- **User-Friendly GUI**: Visual previews and intuitive controls
- **Command-Line Interface**: Perfect for batch processing and automation

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/metamingle.git
   cd metamingle
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Add your camera logos: (optional)
   ```
   # Place PNG files in the logo directory
   ```

## Usage

### GUI Interface

Run the graphical user interface for interactive watermarking:

```bash
python metamingle_gui.py
```

The GUI provides:

- Image selection
- Crop modes: IG auto (4:5 for portrait, 5:4 for landscape photos), IG 4:5, IG 5:4, 3:2, 1:1 or no crop. "Adjust Crop..." opens a window where the
  crop box can be moved, resized by its corners or with the mouse wheel, with a rule-of-thirds grid
- Logo selection dropdown
- Template options (Bottom Only, Full Frame, Classic)
- Output options: IG canvas (4:5 or 5:4, chosen from the photo's orientation) or original ratio, optional resize to 1080 px wide
- Live preview with an indicator showing whether the result is exactly 4:5 or 5:4
- Image saving with custom filename
- Batch export of several photos (each photo is cropped around its centre)

### Command-Line Interface

For batch processing or scripting, use the command-line interface:

```bash
python metamingle.py IMAGE [IMAGE ...] [OPTIONS]
```

`IMAGE` can be one or more image files and/or folders.

#### Options:

- `-o, --output`: Output file path (single image) or output folder (several images / a folder)
- `--ig`: Instagram preset, same as `--crop ig --canvas ig --width 1080` (portrait photos become 4:5, landscape photos 5:4)
- `--crop`: Centred crop before watermarking: `ig` (photo + border = exactly 4:5 or 5:4), a ratio such as `3:2`, or `none` (default)
- `--canvas`: `ig` = 4:5 for portrait and 5:4 for landscape photos, `4:5` / `5:4` force one of them, `auto` pads only portrait/square photos to 4:5 (default), `original` never pads
- `--width`: Downscale the result to this width in pixels (never upscales)
- `--suffix`: File name suffix for batch output (default: `_watermarked`, or `_IG` with `--ig`)
- `-l, --logo`: Path to the camera logo image
- `-t, --template`: Watermark template style (`full_frame`, `bottom_only`, or `classic`)
- `-br, --border-ratio`: Border ratio (default: 35)
- `-bh, --bottom-ratio`: Bottom border height ratio (default: 8)
- `-fr, --font-ratio`: Font size ratio (default: 5)
- `-lr, --logo-ratio`: Logo size ratio (default: 3.5)
- `-pr, --padding-ratio`: Spacing ratio (default: 6)
- `-c, --color`: Text color in RGB format (default: "0,0,0")

#### Example:

```bash
python metamingle.py photo.jpg -l logo/canon.png -t classic -c "0,0,0"
```

Instagram post (portrait 1080 x 1350 or landscape 1080 x 864, photo fills the frame). Add `--canvas 4:5` to force a portrait cover from a landscape photo:

```bash
python metamingle.py photo.jpg --ig -l logo/FUJIFILM.png
```

Whole folder, keeping each photo uncropped on its IG canvas:

```bash
python metamingle.py ./photos --canvas ig --width 1080 -o ./photos/ig
```

## Configuration Details

### Ratio Parameters

All dimensions are calculated proportionally to ensure consistent visual appeal:

- **Border Ratio**: Controls the width of borders (smaller value = thicker border)
- **Bottom Ratio**: Controls the height of the bottom area (smaller value = taller area)
- **Font Ratio**: Controls text size relative to bottom height
- **Logo Ratio**: Controls logo size relative to bottom height
- **Padding Ratio**: Controls spacing between elements

### Folder Structure

- `./logo/`: Place your camera logo PNG files here
- `./font/Saira_Semi_Condensed/`: Contains the fonts for text rendering:
  - `SairaSemiCondensed-Regular.ttf`
  - `SairaSemiCondensed-Bold.ttf`

## EXIF Information Extraction

The tool extracts the following EXIF data:

- Camera make and model
- Lens model
- Aperture (f-stop)
- Shutter speed
- ISO sensitivity
- Focal length
- Capture date and time
- Artist/author information

## TODO List
Next improvements planned for MetaMingle:

1. Package as standalone .exe file for easier distribution
2. Add support for user-updatable fonts
3. Implement flexible border size adjustment

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License.
