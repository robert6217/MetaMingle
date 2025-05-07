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
- Logo selection dropdown
- Preview template options (Bottom, Full Frame, Classic)
- Preview generation
- Image saving with custom filename

### Command-Line Interface

For batch processing or scripting, use the command-line interface:

```bash
python metamingle.py IMAGE_PATH [OPTIONS]
```

#### Options:

- `-o, --output`: Output file path
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
