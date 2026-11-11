"""
Build MetaMingle.exe (Windows) with PyInstaller.

    pip install -r requirements.txt pyinstaller
    python build_exe.py            # single file:  dist/MetaMingle.exe
    python build_exe.py --onedir   # folder:       dist/MetaMingle/MetaMingle.exe (starts faster)

The fonts, the logos in ./logo and icon.ico (see make_icon.py) are bundled into the exe. Extra logos can be added
later without rebuilding: put PNG files in a "logo" folder next to MetaMingle.exe.
"""
import os
import sys

try:
	import PyInstaller.__main__
except ImportError:
	sys.exit("PyInstaller is not installed. Run:  pip install pyinstaller")

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join("font", "Saira_Semi_Condensed")
FONT_FILES = ("SairaSemiCondensed-Regular.ttf", "SairaSemiCondensed-Bold.ttf", "OFL.txt")
EXCLUDES = ("numpy", "PyInstaller", "setuptools", "pkg_resources", "cffi", "pycparser", "yaml",
			"charset_normalizer", "pefile", "altgraph", "packaging", "platformdirs", "IPython", "matplotlib")


def data(source, target):
	"""--add-data argument: source path (relative to this folder) -> folder inside the bundle."""
	return f"{os.path.join(HERE, source)}{os.pathsep}{target}"


def main():
	onedir = "--onedir" in sys.argv[1:]
	args = [
		os.path.join(HERE, "metamingle_gui.py"),
		"--name", "MetaMingle",
		"--onedir" if onedir else "--onefile",
		"--windowed",                       # no console window
		"--noconfirm",
		"--clean",
		"--distpath", os.path.join(HERE, "dist"),
		"--workpath", os.path.join(HERE, "build"),
		"--specpath", os.path.join(HERE, "build"),
		"--add-data", data("logo", "logo"),
		"--collect-data", "tkinterdnd2",    # drag & drop needs the bundled tkdnd library
	]
	# Optional imports pulled in by Pillow / build tools that the program never uses (about 14 MB)
	for module in EXCLUDES:
		args += ["--exclude-module", module]
	for name in FONT_FILES:
		args += ["--add-data", data(os.path.join(FONT_DIR, name), FONT_DIR)]

	icon = os.path.join(HERE, "icon.ico")
	if os.path.isfile(icon):
		args += ["--icon", icon,                   # file icon of MetaMingle.exe
				 "--add-data", data("icon.ico", ".")]  # window / taskbar icon

	PyInstaller.__main__.run(args)
	exe = os.path.join(HERE, "dist", *(["MetaMingle"] if onedir else []), "MetaMingle.exe")
	print(f"\nBuilt: {exe}")


if __name__ == "__main__":
	main()
