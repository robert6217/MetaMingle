import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import threading
import tempfile
from metamingle import (add_exif_watermark, collect_images, center_crop_box, ig_crop_ratio, ig_target_ratio,
						IG_WIDTH, IG_RATIO, IG_LANDSCAPE_RATIO, BASE_DIR, APP_DIR)
import sys
import glob

try:
	# Optional: drag & drop of files from the file manager
	from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception:
	TkinterDnD = None
	DND_FILES = None

TEMP_DIR = os.path.join(tempfile.gettempdir(), "metamingle")
PREVIEW_TEMP_PATH = os.path.join(TEMP_DIR, "preview_temp.jpg")
TEMPLATE_BY_MODE = {"full": "full_frame", "classic": "classic", "bottom": "bottom_only"}
NO_LOGO = "(No logo)"
PREVIEW_MAX_WIDTH = 1600     # previews never need more pixels than this
CROP_MODES = (
	("ig", "IG auto (portrait 4:5 / landscape 5:4)"),
	("ig45", "IG 4:5 portrait"),
	("ig54", "IG 5:4 landscape"),
	("3:2", "Landscape (3:2)"),
	("1:1", "Square (1:1)"),
	("none", "No crop (free-form when adjusting)"),
)
HANDLE_RADIUS = 6            # half size of the corner handles, in screen pixels
HANDLE_HIT = 14              # how close the pointer must be to grab a corner
MIN_CROP_SIZE = 40           # smallest crop box on screen, in pixels
THUMB_HEIGHT = 84            # height of the filmstrip thumbnails, in screen pixels
THUMB_GAP = 8
SETTING_NAMES = ("crop_mode", "template", "logo", "canvas", "resize")

class PhotoItem:
	"""One loaded photo together with its own settings."""
	def __init__(self, path, size, settings):
		self.path = path
		self.size = size             # (width, height) of the upright photo
		self.thumb = None            # ImageTk.PhotoImage for the filmstrip
		self.crop_mode = settings["crop_mode"]
		self.template = settings["template"]     # "bottom", "full" or "classic"
		self.logo = settings["logo"]             # logo file name or NO_LOGO
		self.canvas = settings["canvas"]         # "ig" or "original"
		self.resize = settings["resize"]
		self.crop_box = None         # (left, top, right, bottom) in photo pixels, or None
		self.reset_crop_box()

	@property
	def name(self):
		return os.path.basename(self.path)

	def settings(self):
		return {name: getattr(self, name) for name in SETTING_NAMES}

	def crop_ratio(self):
		"""Width / height of the crop for this photo's mode, or None for no / free-form crop."""
		template = TEMPLATE_BY_MODE.get(self.template, "bottom_only")
		if self.crop_mode == "ig":
			# Follow the photo: landscape -> 5:4, portrait / square -> 4:5
			return ig_crop_ratio(template, target_ratio=ig_target_ratio(*self.size))
		if self.crop_mode == "ig45":
			return ig_crop_ratio(template, target_ratio=IG_RATIO)
		if self.crop_mode == "ig54":
			return ig_crop_ratio(template, target_ratio=IG_LANDSCAPE_RATIO)
		if self.crop_mode == "3:2":
			return 1.5
		if self.crop_mode == "1:1":
			return 1.0
		return None

	def reset_crop_box(self):
		"""Largest centred crop for the selected mode (None when cropping is off)."""
		ratio = self.crop_ratio()
		self.crop_box = center_crop_box(self.size[0], self.size[1], ratio) if ratio else None

	def refit_crop_box(self):
		"""Keep the current crop position but adapt it to a (slightly) different ratio."""
		ratio = self.crop_ratio()
		if not (ratio and self.crop_box):
			return
		img_w, img_h = self.size
		left, top, right, bottom = self.crop_box
		crop_h = bottom - top
		crop_w = round(crop_h * ratio)
		if crop_w > img_w:
			crop_w = img_w
			crop_h = min(img_h, round(crop_w / ratio))
		center_x, center_y = (left + right) / 2, (top + bottom) / 2
		new_left = min(max(0, round(center_x - crop_w / 2)), img_w - crop_w)
		new_top = min(max(0, round(center_y - crop_h / 2)), img_h - crop_h)
		self.crop_box = (new_left, new_top, new_left + crop_w, new_top + crop_h)

class PhotoWatermarkGUI:
	def __init__(self, root):
		self.root = root
		self.root.title("MetaMingle - IG Layout Editor")
		self.root.geometry("1240x900")
		self.root.minsize(1000, 760)

		# Photos
		self.items = []              # list of PhotoItem
		self.current = None          # index of the photo shown in the preview
		self.selected = set()        # indices the left-hand controls apply to
		self.anchor = None           # start of a Shift-click range
		self.thumb_boxes = []        # (x1, x2) of each thumbnail on the filmstrip
		self.thumb_queue = []        # items still waiting for a thumbnail

		# Preview state
		self.preview_image = None
		self.preview_ready = False
		self.preview_pending = False
		self.processing = False
		self.batch_running = False

		# Controls (they mirror the settings of the current photo)
		self.template_var = tk.StringVar(value="classic")
		self.crop_mode = tk.StringVar(value="ig")
		self.canvas_mode = tk.StringVar(value="ig")       # "ig" (4:5 / 5:4 canvas) or "original"
		self.resize_var = tk.BooleanVar(value=True)       # downscale to 1080 px wide

		# Crop window state
		self.original_img = None
		self.crop_win = None
		self.crop_canvas = None
		self.cbox = None             # crop box in crop-canvas coordinates
		self.drag_action = None      # None, "move" or a corner name ("nw", "ne", "sw", "se")
		self.crop_start_x = 0
		self.crop_start_y = 0

		# Logo options
		self.logo_paths = self.get_logo_paths()
		self.selected_logo = tk.StringVar(value=NO_LOGO)
		if self.logo_paths:
			self.selected_logo.set(os.path.basename(self.logo_paths[0]))

		# Build UI
		self.create_ui()
		self.fit_window_to_content()
		self.setup_drag_and_drop()
		self.refresh_all()

	# ------------------------------------------------ current photo access

	@property
	def cur(self):
		"""The photo shown in the preview, or None."""
		if self.current is None or not (0 <= self.current < len(self.items)):
			return None
		return self.items[self.current]

	@property
	def image_path(self):
		return self.cur.path if self.cur else None

	@property
	def source_path(self):
		return self.image_path

	@property
	def source_size(self):
		return self.cur.size if self.cur else None

	@source_size.setter
	def source_size(self, value):
		if self.cur:
			self.cur.size = value

	@property
	def crop_box(self):
		return self.cur.crop_box if self.cur else None

	@crop_box.setter
	def crop_box(self, value):
		if self.cur:
			self.cur.crop_box = value

	@property
	def preview_mode(self):
		return self.cur.template if self.cur else self.template_var.get()

	def targets(self):
		"""Photos the left-hand controls apply to: every selected photo."""
		return [self.items[i] for i in sorted(self.selected) if 0 <= i < len(self.items)]

	def fit_window_to_content(self):
		"""Make sure every control is visible whatever the font size / display scaling is."""
		self.root.update_idletasks()
		scale = max(1.0, self.root.winfo_fpixels('1i') / 96)   # 1.5 on a 150 % display
		screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
		needed = self.root.winfo_reqheight() + int(40 * scale)   # room for a two-line status message
		limit = max(600, screen_h - int(80 * scale))
		height = min(max(int(900 * scale), needed), limit)
		width = min(int(1240 * scale), screen_w - int(40 * scale))
		self.root.geometry(f"{width}x{height}")
		self.root.minsize(min(int(1000 * scale), width), min(needed, limit))

	def get_logo_paths(self):
		"""Bundled logos plus any PNG placed in a "logo" folder next to the program (same name wins)."""
		by_name = {}
		for logo_dir in dict.fromkeys((os.path.join(BASE_DIR, "logo"), os.path.join(APP_DIR, "logo"))):
			for path in glob.glob(os.path.join(logo_dir, "*.png")):
				by_name[os.path.basename(path)] = path
		return [by_name[name] for name in sorted(by_name, key=str.lower)]

	# ------------------------------------------------------------------ UI

	def create_ui(self):
		main = ttk.Frame(self.root, padding=10)
		main.pack(fill=tk.BOTH, expand=True)

		# Controls panel
		ctrl = ttk.Frame(main, width=330, padding=10)
		ctrl.pack(side=tk.LEFT, fill=tk.Y)
		head = (None, 12, 'bold')

		# --- Photos ---
		ttk.Label(ctrl, text="1. Photos", font=head).pack(anchor=tk.W, pady=(0,3))
		ttk.Button(ctrl, text="Add Photos...", command=self.select_image).pack(fill=tk.X, pady=2)
		photo_row = ttk.Frame(ctrl)
		photo_row.pack(fill=tk.X, pady=2)
		ttk.Button(photo_row, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
		ttk.Button(photo_row, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))
		self.selection_info = ttk.Label(ctrl, text="", foreground='gray', wraplength=300, justify=tk.LEFT)
		self.selection_info.pack(anchor=tk.W)

		# --- Crop Settings ---
		ttk.Label(ctrl, text="2. Crop", font=head).pack(anchor=tk.W, pady=(8,3))
		for value, label in CROP_MODES:
			ttk.Radiobutton(ctrl, text=label, variable=self.crop_mode, value=value,
							command=self.on_crop_mode_change).pack(anchor=tk.W, pady=1)
		self.crop_btn = ttk.Button(ctrl, text="Adjust Crop...", command=self.open_crop_window)
		self.crop_btn.pack(fill=tk.X, pady=(5,2))
		self.crop_info = ttk.Label(ctrl, text="No image", foreground='gray')
		self.crop_info.pack(anchor=tk.W)

		# --- Logo ---
		ttk.Label(ctrl, text="3. Logo Style", font=head).pack(anchor=tk.W, pady=(8,3))
		combo = ttk.Combobox(ctrl, textvariable=self.selected_logo, state='readonly')
		combo['values'] = [NO_LOGO] + [os.path.basename(p) for p in self.logo_paths]
		combo.pack(fill=tk.X, pady=3)
		combo.bind('<<ComboboxSelected>>', lambda e: self._on_param_change())

		# --- Template ---
		ttk.Label(ctrl, text="4. Template", font=head).pack(anchor=tk.W, pady=(8,3))
		for value, label in (("bottom", "Bottom Only"), ("full", "Full Frame"), ("classic", "Classic Layout")):
			ttk.Radiobutton(ctrl, text=label, variable=self.template_var, value=value,
							command=lambda: self.change_preview_mode(self.template_var.get())).pack(anchor=tk.W, pady=1)

		# --- Output ---
		ttk.Label(ctrl, text="5. Output", font=head).pack(anchor=tk.W, pady=(8,3))
		ttk.Radiobutton(ctrl, text="IG canvas: 4:5 or 5:4 (pad if needed)", variable=self.canvas_mode,
						value="ig", command=self._on_param_change).pack(anchor=tk.W, pady=1)
		ttk.Radiobutton(ctrl, text="Original ratio (no padding)", variable=self.canvas_mode,
						value="original", command=self._on_param_change).pack(anchor=tk.W, pady=1)
		ttk.Checkbutton(ctrl, text=f"Resize to {IG_WIDTH} px wide (IG size)", variable=self.resize_var,
						command=self._on_param_change).pack(anchor=tk.W, pady=(4,1))
		self.output_info = ttk.Label(ctrl, text="", foreground='gray')
		self.output_info.pack(anchor=tk.W)

		# --- Actions ---
		ttk.Label(ctrl, text="6. Actions", font=head).pack(anchor=tk.W, pady=(8,3))
		ttk.Button(ctrl, text="Apply These Settings to All Photos", command=self.apply_to_all).pack(fill=tk.X, pady=2)
		action_row = ttk.Frame(ctrl)
		action_row.pack(fill=tk.X, pady=2)
		ttk.Button(action_row, text="Save Current...", command=self.save_image).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
		self.batch_btn = ttk.Button(action_row, text="Export All...", command=self.batch_export)
		self.batch_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))

		self.status_label = ttk.Label(ctrl, text="Ready", foreground='green', wraplength=300, justify=tk.LEFT)
		self.status_label.pack(anchor=tk.W, pady=(8,0))

		# Preview panel
		preview_panel = ttk.Frame(main)
		preview_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
		self.preview_title = ttk.Label(preview_panel, text="Live Preview", font=(None,14,'bold'))
		self.preview_title.pack(anchor=tk.W, pady=(0,10))

		# Filmstrip (thumbnails of every loaded photo)
		strip_frame = tk.Frame(preview_panel, background='#1f1f1f')
		strip_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(8,0))
		self.strip_scroll = ttk.Scrollbar(strip_frame, orient=tk.HORIZONTAL)
		self.strip_scroll.pack(side=tk.BOTTOM, fill=tk.X)
		self.strip = tk.Canvas(strip_frame, bg='#1f1f1f', highlightthickness=0,
							   height=THUMB_HEIGHT + 2 * THUMB_GAP, xscrollcommand=self.strip_scroll.set)
		self.strip.pack(fill=tk.X)
		self.strip_scroll.config(command=self.strip.xview)
		self.strip.bind("<ButtonPress-1>", self.on_strip_click)
		self.strip.bind("<MouseWheel>", lambda e: self.strip.xview_scroll(-1 if e.delta > 0 else 1, "units"))

		canvas_frame = tk.Frame(preview_panel, background='#2b2b2b')
		canvas_frame.pack(fill=tk.BOTH, expand=True)

		self.canvas = tk.Canvas(canvas_frame, bg='#2b2b2b', highlightthickness=0)
		self.canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
		self.canvas.bind('<Configure>', self._on_canvas_resize)

		# Keyboard shortcuts
		self.root.bind("<Left>", lambda e: self.step_selection(-1))
		self.root.bind("<Right>", lambda e: self.step_selection(1))
		self.root.bind("<Delete>", lambda e: self.remove_selected())
		self.root.bind("<Control-a>", lambda e: self.select_all())

	def _on_canvas_resize(self, event=None):
		if self.preview_ready:
			self.display_preview(PREVIEW_TEMP_PATH)
		else:
			self.show_placeholder()

	# --------------------------------------------------------- drag & drop

	def setup_drag_and_drop(self):
		"""Accept files / folders dropped from the file manager (needs the tkinterdnd2 package)."""
		self.dnd_enabled = False
		if DND_FILES is None:
			return
		try:
			for widget in (self.canvas, self.strip):
				widget.drop_target_register(DND_FILES)
				widget.dnd_bind('<<Drop>>', self.on_drop)
			self.dnd_enabled = True
		except Exception:
			self.dnd_enabled = False   # the root window was not created by TkinterDnD

	def on_drop(self, event):
		try:
			paths = list(self.root.tk.splitlist(event.data))
		except tk.TclError:
			paths = [event.data]
		self.add_paths(paths)
		return getattr(event, 'action', None)

	# -------------------------------------------------------------- photos

	def select_image(self):
		files = filedialog.askopenfilenames(filetypes=[('Image files','*.jpg *.jpeg *.png')])
		if not files: return
		self.add_paths(list(files))

	def load_image(self, fp):
		"""Add a single photo (kept for compatibility)."""
		self.add_paths([fp])

	def current_settings(self):
		"""Settings a newly added photo starts with: those shown in the controls."""
		return {
			"crop_mode": self.crop_mode.get(),
			"template": self.template_var.get(),
			"logo": self.selected_logo.get(),
			"canvas": self.canvas_mode.get(),
			"resize": self.resize_var.get(),
		}

	@staticmethod
	def _upright_size(path):
		"""Image size after applying the EXIF orientation, without decoding the pixels."""
		with Image.open(path) as img:
			width, height = img.size
			if img.getexif().get(0x0112) in (5, 6, 7, 8):
				width, height = height, width
		return width, height

	def add_paths(self, paths):
		"""Add image files and/or folders. Photos already loaded are skipped."""
		existing = {os.path.normcase(os.path.abspath(item.path)) for item in self.items}
		settings = self.current_settings()
		first_new = None
		added, skipped, failed = 0, 0, []
		for path in collect_images(paths):
			key = os.path.normcase(os.path.abspath(path))
			if key in existing:
				skipped += 1
				continue
			try:
				size = self._upright_size(path)
			except Exception as e:
				failed.append(f"{os.path.basename(path)}: {e}")
				continue
			existing.add(key)
			item = PhotoItem(path, size, settings)
			self.items.append(item)
			self.thumb_queue.append(item)
			if first_new is None:
				first_new = len(self.items) - 1
			added += 1

		if first_new is not None:
			# Show the first new photo
			self.current = first_new
			self.selected = {first_new}
			self.anchor = first_new
			self.refresh_all()
			self.root.after(1, self._process_thumb_queue)

		parts = [f"Added {added} photo(s)"]
		if skipped:
			parts.append(f"{skipped} already loaded")
		if failed:
			parts.append(f"{len(failed)} could not be opened")
		if not (added or skipped or failed):
			parts = ["No image files found (jpg / jpeg / png)"]
		if first_new is None:
			self.update_status(", ".join(parts), 'red' if failed else 'gray')
		if failed:
			messagebox.showwarning("Add Photos", "These files could not be opened:\n" + "\n".join(failed[:10]))

	def _process_thumb_queue(self):
		"""Create thumbnails one at a time so the window stays responsive."""
		if not self.thumb_queue:
			return
		item = self.thumb_queue.pop(0)
		if item in self.items and item.thumb is None:
			try:
				with Image.open(item.path) as img:
					img.draft('RGB', (THUMB_HEIGHT * 4, THUMB_HEIGHT * 4))
					thumb = ImageOps.exif_transpose(img)
					thumb.thumbnail((THUMB_HEIGHT * 3, THUMB_HEIGHT), Image.LANCZOS)
					item.thumb = ImageTk.PhotoImage(thumb.convert('RGB'))
			except Exception:
				item.thumb = None
			self.draw_filmstrip()
		if self.thumb_queue:
			self.root.after(1, self._process_thumb_queue)

	def draw_filmstrip(self):
		strip = self.strip
		strip.delete('all')
		self.thumb_boxes = []
		x = THUMB_GAP
		y = THUMB_GAP
		for index, item in enumerate(self.items):
			if item.thumb is not None:
				width = item.thumb.width()
				strip.create_image(x, y, anchor=tk.NW, image=item.thumb)
			else:
				width = max(40, round(THUMB_HEIGHT * item.size[0] / item.size[1]))
				strip.create_rectangle(x, y, x + width, y + THUMB_HEIGHT, fill='#3a3a3a', outline='')
			if index == self.current:
				strip.create_rectangle(x - 2, y - 2, x + width + 2, y + THUMB_HEIGHT + 2, outline='#ffffff', width=3)
			elif index in self.selected:
				strip.create_rectangle(x - 2, y - 2, x + width + 2, y + THUMB_HEIGHT + 2, outline='#4da3ff', width=3)
			self.thumb_boxes.append((x, x + width))
			x += width + THUMB_GAP
		if not self.items:
			hint = "Drop photos or folders here" if self.dnd_available() else "Use \"Add Photos...\" to load photos"
			strip.create_text(THUMB_GAP + 4, y + THUMB_HEIGHT // 2, anchor=tk.W, text=hint, fill='#9a9a9a')
		strip.config(scrollregion=(0, 0, max(x, 1), THUMB_HEIGHT + 2 * THUMB_GAP))

	def dnd_available(self):
		return getattr(self, 'dnd_enabled', False)

	def scroll_to_current(self):
		if self.current is None or self.current >= len(self.thumb_boxes):
			return
		self.strip.update_idletasks()
		total = max(1, self.thumb_boxes[-1][1] + THUMB_GAP)
		view_w = max(1, self.strip.winfo_width())
		x1, x2 = self.thumb_boxes[self.current]
		left = self.strip.canvasx(0)
		if x1 - THUMB_GAP < left:
			self.strip.xview_moveto(max(0, (x1 - THUMB_GAP) / total))
		elif x2 + THUMB_GAP > left + view_w:
			self.strip.xview_moveto(max(0, (x2 + THUMB_GAP - view_w) / total))

	def on_strip_click(self, event):
		x = self.strip.canvasx(event.x)
		for index, (x1, x2) in enumerate(self.thumb_boxes):
			if x1 - THUMB_GAP / 2 <= x <= x2 + THUMB_GAP / 2:
				self.select_index(index, ctrl=bool(event.state & 0x4), shift=bool(event.state & 0x1))
				return

	def select_index(self, index, ctrl=False, shift=False):
		"""Click = select one, Ctrl+click = add / remove, Shift+click = select a range."""
		if not (0 <= index < len(self.items)):
			return
		if shift and self.anchor is not None and self.anchor < len(self.items):
			low, high = sorted((self.anchor, index))
			self.selected = set(range(low, high + 1))
			self.current = index
		elif ctrl:
			if index in self.selected and len(self.selected) > 1:
				self.selected.discard(index)
				if self.current == index:
					self.current = max(self.selected)
			else:
				self.selected.add(index)
				self.current = index
			self.anchor = index
		else:
			self.selected = {index}
			self.current = index
			self.anchor = index
		self.refresh_all()

	def step_selection(self, delta):
		if not self.items or self.current is None:
			return
		self.select_index(min(max(self.current + delta, 0), len(self.items) - 1))

	def select_all(self):
		if not self.items:
			return
		self.selected = set(range(len(self.items)))
		if self.current is None:
			self.current = 0
		self.refresh_all(preview=False)

	def remove_selected(self):
		if not self.items or not self.selected:
			return
		position = min(self.selected)
		self.items = [item for i, item in enumerate(self.items) if i not in self.selected]
		if self.items:
			self.current = min(position, len(self.items) - 1)
			self.selected = {self.current}
			self.anchor = self.current
		else:
			self.current, self.selected, self.anchor = None, set(), None
		self.refresh_all()

	def clear_all(self):
		if not self.items:
			return
		self.items = []
		self.thumb_queue = []
		self.current, self.selected, self.anchor = None, set(), None
		self.refresh_all()

	def refresh_all(self, preview=True):
		"""Sync the controls, labels, filmstrip and preview with the current photo."""
		if self.crop_win and self.crop_win.winfo_exists():
			self.crop_win.destroy()
		item = self.cur
		if item:
			# Setting a Tk variable does not trigger the widget commands
			self.crop_mode.set(item.crop_mode)
			self.template_var.set(item.template)
			self.selected_logo.set(item.logo)
			self.canvas_mode.set(item.canvas)
			self.resize_var.set(item.resize)
			self.preview_title.config(text=f"Live Preview - {item.name}  ({self.current + 1}/{len(self.items)})")
		else:
			self.preview_title.config(text="Live Preview")
			self.output_info.config(text="")
		self.update_crop_info()
		self.update_selection_info()
		self.draw_filmstrip()
		self.scroll_to_current()
		if not item:
			self.preview_ready = False
			self.show_placeholder()
			self.update_status("Ready")
		elif preview:
			self.preview_ready = False
			self.generate_preview()

	def update_selection_info(self):
		total = len(self.items)
		if not total:
			text = "No photos loaded"
		elif len(self.selected) > 1:
			text = f"{total} photos, {len(self.selected)} selected - changes apply to all selected"
		else:
			text = f"{total} photo(s). Ctrl / Shift + click to select several"
		self.selection_info.config(text=text)

	# ---------------------------------------------------------------- crop

	def current_template(self):
		return TEMPLATE_BY_MODE.get(self.preview_mode, "bottom_only")

	def current_crop_ratio(self):
		"""Width / height of the current photo's crop, or None for no / free-form crop."""
		return self.cur.crop_ratio() if self.cur else None

	def update_crop_info(self):
		if not self.source_size:
			self.crop_info.config(text="No image")
		elif self.crop_box:
			w, h = self.crop_box[2] - self.crop_box[0], self.crop_box[3] - self.crop_box[1]
			self.crop_info.config(text=f"Crop: {w} x {h} px of {self.source_size[0]} x {self.source_size[1]}")
		else:
			self.crop_info.config(text=f"Whole photo: {self.source_size[0]} x {self.source_size[1]} px")

	def on_crop_mode_change(self):
		if self.crop_win and self.crop_win.winfo_exists():
			self.crop_win.destroy()
		mode = self.crop_mode.get()
		for item in self.targets():
			item.crop_mode = mode
			item.reset_crop_box()
		self.update_crop_info()
		if self.image_path:
			self.generate_preview()

	def open_crop_window(self):
		if not self.source_path:
			messagebox.showinfo('Info', 'Add a photo first')
			return

		if self.crop_win and self.crop_win.winfo_exists():
			self.crop_win.destroy()

		try:
			with Image.open(self.source_path) as img:
				self.original_img = ImageOps.exif_transpose(img)
				self.original_img.load()
		except Exception as e:
			messagebox.showerror('Error', f'Cannot open image: {e}')
			return

		self.crop_win_ratio = self.current_crop_ratio()
		mode_label = dict(CROP_MODES)[self.crop_mode.get()]

		self.crop_win = tk.Toplevel(self.root)
		self.crop_win.title(f"Adjust Crop - {self.cur.name} - {mode_label}")
		self.crop_win.geometry("940x760")

		msg = "Drag inside the box to move it. Drag a corner or use the mouse wheel to resize."
		if self.crop_mode.get().startswith("ig"):
			target = "5:4" if self.crop_win_ratio > 1 else "4:5"
			msg += f"\nThe ratio is locked so that photo + border = exactly {target} for the selected template."
		ttk.Label(self.crop_win, text=msg, justify=tk.CENTER).pack(pady=(10,4))
		self.crop_size_label = ttk.Label(self.crop_win, text="", foreground='gray')
		self.crop_size_label.pack()

		buttons = ttk.Frame(self.crop_win)
		buttons.pack(side=tk.BOTTOM, pady=10)
		ttk.Button(buttons, text="Reset", command=self.reset_crop_rect).pack(side=tk.LEFT, padx=5)
		ttk.Button(buttons, text="Cancel", command=self.crop_win.destroy).pack(side=tk.LEFT, padx=5)
		ttk.Button(buttons, text="Apply Crop", command=self.apply_crop).pack(side=tk.LEFT, padx=5)

		canvas_frame = tk.Frame(self.crop_win, background='black')
		canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

		self.crop_canvas = tk.Canvas(canvas_frame, highlightthickness=0, bg='black')
		self.crop_canvas.pack(fill=tk.BOTH, expand=True)

		self.display_crop_preview()
		self.init_crop_rect(self.crop_win_ratio)

		self.crop_canvas.bind("<ButtonPress-1>", self.on_crop_start)
		self.crop_canvas.bind("<B1-Motion>", self.on_crop_move)
		self.crop_canvas.bind("<ButtonRelease-1>", self.on_crop_end)
		self.crop_canvas.bind("<Motion>", self.on_crop_hover)
		self.crop_canvas.bind("<MouseWheel>", self.on_crop_wheel)
		self.crop_canvas.bind("<Button-4>", lambda e: self.zoom_crop_rect(1.05))
		self.crop_canvas.bind("<Button-5>", lambda e: self.zoom_crop_rect(1 / 1.05))

	def display_crop_preview(self):
		if not self.original_img: return
		self.crop_canvas.update_idletasks()
		cw, ch = self.crop_canvas.winfo_width(), self.crop_canvas.winfo_height()
		if cw <= 1 or ch <= 1: cw, ch = 800, 600

		img_preview = ImageOps.contain(self.original_img, (cw, ch), Image.LANCZOS)
		preview_w, preview_h = img_preview.size
		self.crop_preview_scale = preview_w / self.original_img.width
		cx, cy = (cw - preview_w) // 2, (ch - preview_h) // 2

		self.crop_preview_pos = (cx, cy)
		self.crop_preview_size = (preview_w, preview_h)

		self.crop_photo_obj = ImageTk.PhotoImage(img_preview)
		self.crop_canvas.delete('all')
		self.crop_canvas.create_image(cx, cy, anchor=tk.NW, image=self.crop_photo_obj)

	def _max_crop_rect(self, ratio_val):
		"""Largest centred box (canvas coordinates) for the ratio; the whole photo when ratio is None."""
		preview_w, preview_h = self.crop_preview_size
		cx, cy = self.crop_preview_pos
		if not ratio_val:
			return [cx, cy, cx + preview_w, cy + preview_h]
		if (preview_w / preview_h) > ratio_val:
			rect_height = preview_h
			rect_width = rect_height * ratio_val
		else:
			rect_width = preview_w
			rect_height = rect_width / ratio_val
		x1 = cx + (preview_w - rect_width) / 2
		y1 = cy + (preview_h - rect_height) / 2
		return [x1, y1, x1 + rect_width, y1 + rect_height]

	def init_crop_rect(self, ratio_val):
		if not self.original_img: return
		if self.crop_box:
			# Start from the crop that is currently applied
			cx, cy = self.crop_preview_pos
			scale = self.crop_preview_scale
			left, top, right, bottom = self.crop_box
			self.cbox = [cx + left * scale, cy + top * scale, cx + right * scale, cy + bottom * scale]
		else:
			self.cbox = self._max_crop_rect(ratio_val)
		self.draw_crop_overlay()

	def reset_crop_rect(self):
		self.cbox = self._max_crop_rect(self.crop_win_ratio)
		self.draw_crop_overlay()

	def draw_crop_overlay(self):
		"""Redraw the dimmed surround, the crop frame, the rule-of-thirds grid and the corner handles."""
		c = self.crop_canvas
		c.delete('overlay')
		x1, y1, x2, y2 = self.cbox
		ix1, iy1 = self.crop_preview_pos
		ix2, iy2 = ix1 + self.crop_preview_size[0], iy1 + self.crop_preview_size[1]

		# Dim everything outside the crop
		for rx1, ry1, rx2, ry2 in ((ix1, iy1, ix2, y1), (ix1, y2, ix2, iy2), (ix1, y1, x1, y2), (x2, y1, ix2, y2)):
			if rx2 - rx1 > 0.5 and ry2 - ry1 > 0.5:
				c.create_rectangle(rx1, ry1, rx2, ry2, fill='black', stipple='gray50', outline='', tags='overlay')

		# Rule-of-thirds grid
		for i in (1, 2):
			gx = x1 + (x2 - x1) * i / 3
			gy = y1 + (y2 - y1) * i / 3
			c.create_line(gx, y1, gx, y2, fill='white', dash=(2, 4), tags='overlay')
			c.create_line(x1, gy, x2, gy, fill='white', dash=(2, 4), tags='overlay')

		c.create_rectangle(x1, y1, x2, y2, outline='white', width=2, tags='overlay')
		r = HANDLE_RADIUS
		for hx, hy in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
			c.create_rectangle(hx - r, hy - r, hx + r, hy + r, fill='white', outline='black', tags='overlay')

		scale = self.crop_preview_scale
		w, h = round((x2 - x1) / scale), round((y2 - y1) / scale)
		note = f"  (narrower than IG's {IG_WIDTH} px - the result will not be upscaled)" if w < IG_WIDTH else ""
		self.crop_size_label.config(text=f"Selection: {w} x {h} px{note}")

	def _corner_at(self, x, y):
		"""Name of the corner handle under the pointer, or None."""
		x1, y1, x2, y2 = self.cbox
		for name, hx, hy in (("nw", x1, y1), ("ne", x2, y1), ("sw", x1, y2), ("se", x2, y2)):
			if abs(x - hx) <= HANDLE_HIT and abs(y - hy) <= HANDLE_HIT:
				return name
		return None

	def on_crop_hover(self, event):
		if not self.cbox or self.drag_action: return
		corner = self._corner_at(event.x, event.y)
		x1, y1, x2, y2 = self.cbox
		if corner in ("nw", "se"):
			cursor = "size_nw_se"
		elif corner in ("ne", "sw"):
			cursor = "size_ne_sw"
		elif x1 <= event.x <= x2 and y1 <= event.y <= y2:
			cursor = "fleur"
		else:
			cursor = ""
		try:
			self.crop_canvas.config(cursor=cursor)
		except tk.TclError:
			pass  # cursor name not available on this platform

	def on_crop_start(self, event):
		if not self.cbox: return
		x1, y1, x2, y2 = self.cbox
		corner = self._corner_at(event.x, event.y)
		if corner:
			self.drag_action = corner
		elif x1 <= event.x <= x2 and y1 <= event.y <= y2:
			self.drag_action = "move"
			self.crop_start_x = event.x
			self.crop_start_y = event.y

	def on_crop_move(self, event):
		if not self.drag_action or not self.cbox: return
		if self.drag_action == "move":
			dx = event.x - self.crop_start_x
			dy = event.y - self.crop_start_y
			self.move_crop_rect(dx, dy)
			self.crop_start_x = event.x
			self.crop_start_y = event.y
		else:
			self.resize_crop_rect(self.drag_action, event.x, event.y)

	def on_crop_end(self, event):
		self.drag_action = None

	def on_crop_wheel(self, event):
		self.zoom_crop_rect(1.05 if event.delta > 0 else 1 / 1.05)

	def move_crop_rect(self, dx, dy):
		"""Move the crop box, keeping it inside the photo."""
		x1, y1, x2, y2 = self.cbox
		cx, cy = self.crop_preview_pos
		preview_w, preview_h = self.crop_preview_size
		dx = max(cx - x1, min(dx, cx + preview_w - x2))
		dy = max(cy - y1, min(dy, cy + preview_h - y2))
		self.cbox = [x1 + dx, y1 + dy, x2 + dx, y2 + dy]
		self.draw_crop_overlay()

	def resize_crop_rect(self, corner, px, py):
		"""Drag one corner; the opposite corner stays fixed and the ratio (if any) stays locked."""
		x1, y1, x2, y2 = self.cbox
		ix1, iy1 = self.crop_preview_pos
		ix2, iy2 = ix1 + self.crop_preview_size[0], iy1 + self.crop_preview_size[1]

		anchor_x = x2 if 'w' in corner else x1
		anchor_y = y2 if 'n' in corner else y1
		sign_x = -1 if 'w' in corner else 1
		sign_y = -1 if 'n' in corner else 1
		max_w = (anchor_x - ix1) if sign_x < 0 else (ix2 - anchor_x)
		max_h = (anchor_y - iy1) if sign_y < 0 else (iy2 - anchor_y)

		w = max(0, (px - anchor_x) * sign_x)
		h = max(0, (py - anchor_y) * sign_y)
		ratio = self.crop_win_ratio
		if ratio:
			limit = min(max_w, max_h * ratio)
			w = max(w, h * ratio)
			w = max(min(w, limit), min(MIN_CROP_SIZE, limit))
			h = w / ratio
		else:
			w = max(min(w, max_w), min(MIN_CROP_SIZE, max_w))
			h = max(min(h, max_h), min(MIN_CROP_SIZE, max_h))

		new_x = anchor_x + sign_x * w
		new_y = anchor_y + sign_y * h
		self.cbox = [min(anchor_x, new_x), min(anchor_y, new_y), max(anchor_x, new_x), max(anchor_y, new_y)]
		self.draw_crop_overlay()

	def zoom_crop_rect(self, factor):
		"""Grow / shrink the crop box around its centre (mouse wheel)."""
		if not self.cbox: return
		x1, y1, x2, y2 = self.cbox
		ix1, iy1 = self.crop_preview_pos
		preview_w, preview_h = self.crop_preview_size
		w, h = x2 - x1, y2 - y1
		ratio = self.crop_win_ratio or (w / h)

		new_w = w * factor
		new_w = min(new_w, preview_w, preview_h * ratio)
		new_w = max(new_w, min(MIN_CROP_SIZE, preview_w))
		new_h = new_w / ratio

		center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
		nx1 = min(max(ix1, center_x - new_w / 2), ix1 + preview_w - new_w)
		ny1 = min(max(iy1, center_y - new_h / 2), iy1 + preview_h - new_h)
		self.cbox = [nx1, ny1, nx1 + new_w, ny1 + new_h]
		self.draw_crop_overlay()

	def apply_crop(self):
		"""A manually adjusted crop only applies to the photo shown in the preview."""
		if not self.original_img or not self.cbox: return

		x1, y1, x2, y2 = self.cbox
		cx, cy = self.crop_preview_pos
		scale = self.crop_preview_scale
		img_w, img_h = self.original_img.size

		crop_x1 = (x1 - cx) / scale
		crop_y1 = (y1 - cy) / scale
		crop_x2 = (x2 - cx) / scale
		crop_y2 = (y2 - cy) / scale

		ratio = self.crop_win_ratio
		crop_w = min(img_w, max(1, round(crop_x2 - crop_x1)))
		if ratio:
			# Snap to whole pixels while keeping the exact target ratio
			crop_h = max(1, round(crop_w / ratio))
			if crop_h > img_h:
				crop_h = img_h
				crop_w = max(1, round(crop_h * ratio))
		else:
			crop_h = min(img_h, max(1, round(crop_y2 - crop_y1)))
		left = min(max(0, round(crop_x1)), img_w - crop_w)
		top = min(max(0, round(crop_y1)), img_h - crop_h)

		self.source_size = (img_w, img_h)
		if (crop_w, crop_h) == (img_w, img_h):
			self.crop_box = None    # the whole photo is selected: nothing to crop
		else:
			self.crop_box = (left, top, left + crop_w, top + crop_h)
		self.update_crop_info()
		self.crop_win.destroy()
		self.generate_preview()

	# ------------------------------------------------------------- options

	def change_preview_mode(self, mode):
		self.template_var.set(mode)
		if self.crop_win and self.crop_win.winfo_exists():
			self.crop_win.destroy()
		for item in self.targets():
			item.template = mode
			# The IG crop ratio depends on the template (Full Frame has side borders)
			if item.crop_mode.startswith("ig"):
				item.refit_crop_box()
		self.update_crop_info()
		if self.image_path:
			self.generate_preview()
		else:
			self.show_placeholder()

	def _on_param_change(self):
		"""Logo / canvas / resize changed: copy them to every selected photo."""
		for item in self.targets():
			item.logo = self.selected_logo.get()
			item.canvas = self.canvas_mode.get()
			item.resize = self.resize_var.get()
		if self.image_path:
			self.generate_preview()

	def apply_to_all(self):
		"""Copy the current photo's settings to every loaded photo (manual crops are kept where still valid)."""
		source = self.cur
		if not source:
			return
		for item in self.items:
			if item is source:
				continue
			crop_changed = item.crop_mode != source.crop_mode
			template_changed = item.template != source.template
			item.crop_mode, item.template = source.crop_mode, source.template
			item.logo, item.canvas, item.resize = source.logo, source.canvas, source.resize
			if crop_changed:
				item.reset_crop_box()
			elif template_changed and item.crop_mode.startswith("ig"):
				item.refit_crop_box()
		self.update_status(f"Settings applied to all {len(self.items)} photos")

	def show_placeholder(self):
		self.canvas.delete('all')
		cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
		if cw < 10 or ch < 10:
			cw, ch = self.canvas.winfo_reqwidth(), self.canvas.winfo_reqheight()
		if self.dnd_available():
			text = "Drop photos or folders here\nor click \"Add Photos...\""
		else:
			text = "Click \"Add Photos...\" to start\n(install tkinterdnd2 to enable drag & drop)"
		self.canvas.create_text(cw//2, ch//2, text=text, fill='white', font=(None, 16), justify=tk.CENTER)

	def get_selected_logo_path(self):
		return self.logo_path_for(self.selected_logo.get())

	def logo_path_for(self, name):
		for path in self.logo_paths:
			if os.path.basename(path) == name:
				return path
		return None

	def item_options(self, item):
		"""Watermark options for one photo (read on the main thread)."""
		return dict(
			logo_path=self.logo_path_for(item.logo),
			template_style=TEMPLATE_BY_MODE.get(item.template, "bottom_only"),
			canvas_ratio="ig" if item.canvas == "ig" else "original",
			output_width=IG_WIDTH if item.resize else None,
			crop_box=item.crop_box,
		)

	def render_options(self):
		"""Options of the current photo (kept for compatibility)."""
		return self.item_options(self.cur) if self.cur else {}

	# ------------------------------------------------------------- preview

	def generate_preview(self):
		if not self.image_path: return
		if self.processing:
			# Settings or photo changed while rendering: render again once the current run finishes
			self.preview_pending = True
			return
		self.processing = True
		self.update_status('Generating Preview...', 'orange')
		# Read Tk state on the main thread; the worker only touches plain values
		options = self.item_options(self.cur)
		options['output_width'] = options['output_width'] or PREVIEW_MAX_WIDTH
		self._preview_result = None
		threading.Thread(target=self._process_preview, args=(self.image_path, options), daemon=True).start()
		self.root.after(50, self._poll_preview)

	def _poll_preview(self):
		# Tk is not thread-safe: the worker only stores its result, the main thread picks it up here
		if self._preview_result is None:
			self.root.after(50, self._poll_preview)
			return
		self._preview_done(self._preview_result[0])

	def _process_preview(self, image_path, options):
		error = None
		try:
			os.makedirs(TEMP_DIR, exist_ok=True)
			add_exif_watermark(image_path=image_path, output_path=PREVIEW_TEMP_PATH, **options)
		except Exception as e:
			error = str(e)
		self._preview_result = (error,)

	def _preview_done(self, error):
		self.processing = False
		if self.preview_pending:
			# Something changed meanwhile: this result is already outdated
			self.preview_pending = False
			if self.image_path:
				self.generate_preview()
			return
		if not self.image_path:
			return   # the photo was removed while rendering
		if error is None:
			self.preview_ready = True
			self.display_preview(PREVIEW_TEMP_PATH)
			self.update_status('Preview Ready', 'green')
		else:
			self.update_status(f'Error: {error}', 'red')

	def display_preview(self, image_path):
		if not os.path.exists(image_path): return

		cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
		if cw < 10 or ch < 10: cw, ch = 800, 600

		try:
			with Image.open(image_path) as img:
				ratio = img.width / img.height
				img_resized = ImageOps.contain(img, (cw, ch), Image.LANCZOS)
		except Exception:
			return  # file is being rewritten by a newer preview run
		self.preview_photo = ImageTk.PhotoImage(img_resized)

		self.canvas.delete('all')
		self.canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=self.preview_photo)

		if abs(ratio - IG_RATIO) < 0.002:
			text, color = "Output ratio: 4:5 (IG portrait)", 'green'
		elif abs(ratio - IG_LANDSCAPE_RATIO) < 0.003:
			text, color = "Output ratio: 5:4 (IG landscape)", 'green'
		else:
			text, color = f"Output ratio: {ratio:.2f}:1 (not an IG 4:5 / 5:4 canvas)", 'gray'
		self.output_info.config(text=text, foreground=color)

	def update_status(self, msg, color="green"):
		self.status_label.config(text=msg, foreground=color)

	# ---------------------------------------------------------------- save

	def save_image(self):
		"""Save the photo shown in the preview."""
		if not self.image_path: return
		default_name = os.path.splitext(os.path.basename(self.image_path))[0] + "_IG.jpg"

		# [FIX] 增加 defaultextension 參數
		save_path = filedialog.asksaveasfilename(
			initialfile=default_name,
			filetypes=[('JPEG', '*.jpg')],
			defaultextension=".jpg"  # 確保如果使用者沒打副檔名，會自動加上 .jpg
		)

		if not save_path: return

		try:
			add_exif_watermark(image_path=self.image_path, output_path=save_path, **self.item_options(self.cur))
			with Image.open(save_path) as saved:
				size = saved.size
			messagebox.showinfo("Success", f"Saved to {save_path}\n{size[0]} x {size[1]} px")
		except Exception as e:
			messagebox.showerror("Error", str(e))

	def batch_export(self):
		"""Export every loaded photo, each with its own settings."""
		if self.batch_running: return
		if not self.items:
			messagebox.showinfo('Info', 'Add photos first')
			return
		out_dir = filedialog.askdirectory(title=f"Select output folder for {len(self.items)} photo(s)")
		if not out_dir: return
		self.start_batch(out_dir)

	def start_batch(self, out_dir):
		# Snapshot everything on the main thread; the worker only touches plain values
		jobs = []
		used_names = set()
		for item in self.items:
			stem = os.path.splitext(item.name)[0]
			name = f"{stem}_IG.jpg"
			counter = 2
			while name.lower() in used_names:     # same file name coming from two folders
				name = f"{stem}_IG_{counter}.jpg"
				counter += 1
			used_names.add(name.lower())
			jobs.append((item.path, os.path.join(out_dir, name), self.item_options(item)))

		self.batch_running = True
		self.batch_btn.config(state=tk.DISABLED)
		self._batch_state = {"done": 0, "total": len(jobs), "name": "", "results": None}

		def worker():
			results = []
			try:
				os.makedirs(out_dir, exist_ok=True)
			except Exception as e:
				self._batch_state["results"] = [(None, None, str(e))]
				return
			for index, (path, output_path, options) in enumerate(jobs):
				self._batch_state["done"] = index
				self._batch_state["name"] = os.path.basename(path)
				try:
					add_exif_watermark(image_path=path, output_path=output_path, **options)
					results.append((path, output_path, None))
				except Exception as e:
					results.append((path, None, str(e)))
			self._batch_state["results"] = results

		threading.Thread(target=worker, daemon=True).start()
		self.root.after(100, lambda: self._poll_batch(out_dir))

	def _poll_batch(self, out_dir):
		state = self._batch_state
		if state["results"] is None:
			self.update_status(f'Exporting {min(state["done"] + 1, state["total"])}/{state["total"]}: {state["name"]}', 'orange')
			self.root.after(100, lambda: self._poll_batch(out_dir))
			return
		self.batch_running = False
		self.batch_btn.config(state=tk.NORMAL)
		failed = [(src, err) for src, _, err in state["results"] if err]
		saved = len(state["results"]) - len(failed)
		self.update_status(f'Export done: {saved} saved, {len(failed)} failed', 'red' if failed else 'green')
		self.show_batch_summary(out_dir, saved, failed)

	def show_batch_summary(self, out_dir, saved, failed):
		message = f"{saved} image(s) saved to\n{out_dir}"
		if failed:
			details = "\n".join(f"- {os.path.basename(src or '?')}: {err}" for src, err in failed[:10])
			messagebox.showwarning("Export", f"{message}\n\n{len(failed)} failed:\n{details}")
		else:
			messagebox.showinfo("Export", message)

def enable_high_dpi():
	"""Render sharply on Windows displays scaled above 100 % instead of being stretched (blurry)."""
	if sys.platform != "win32":
		return
	try:
		import ctypes
		ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system DPI aware; Tk scales fonts to match
	except Exception:
		pass

def create_root():
	"""Create the main window, with drag & drop support when tkinterdnd2 is installed."""
	if TkinterDnD is not None:
		try:
			return TkinterDnD.Tk()
		except Exception:
			pass   # tkdnd could not be loaded: fall back to a plain window
	return tk.Tk()

if __name__ == '__main__':
	enable_high_dpi()
	root = create_root()
	app = PhotoWatermarkGUI(root)
	# Files / folders given on the command line (also "Open with" or dropping files onto MetaMingle.exe)
	if len(sys.argv) > 1:
		root.after(100, lambda: app.add_paths(sys.argv[1:]))
	root.mainloop()
