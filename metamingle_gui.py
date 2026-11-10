import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import threading
import tempfile
from metamingle import (add_exif_watermark, batch_process, center_crop_box, ig_crop_ratio, ig_target_ratio,
						IG_WIDTH, IG_RATIO, IG_LANDSCAPE_RATIO)
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

class PhotoWatermarkGUI:
	def __init__(self, root):
		self.root = root
		self.root.title("MetaMingle - IG Layout Editor")
		self.root.geometry("1240x900")
		self.root.minsize(1000, 760)

		# Variables
		self.image_path = None       # image being watermarked
		self.source_path = None      # same as image_path (kept for compatibility)
		self.source_size = None      # (width, height) of the upright source image
		self.preview_image = None
		self.preview_ready = False
		self.preview_pending = False
		self.processing = False
		self.batch_running = False
		self.preview_mode = "classic"  # Default preview mode
		self.template_var = tk.StringVar(value=self.preview_mode)

		# Crop variables
		self.crop_mode = tk.StringVar(value="ig")
		self.crop_box = None         # (left, top, right, bottom) in source pixels, or None
		self.original_img = None
		self.crop_win = None
		self.crop_canvas = None
		self.cbox = None             # crop box in crop-canvas coordinates
		self.drag_action = None      # None, "move" or a corner name ("nw", "ne", "sw", "se")
		self.crop_start_x = 0
		self.crop_start_y = 0

		# Output variables
		self.canvas_mode = tk.StringVar(value="ig")       # "ig" (4:5 canvas) or "original"
		self.resize_var = tk.BooleanVar(value=True)       # downscale to 1080 px wide

		# Logo options
		self.logo_paths = self.get_logo_paths()
		self.selected_logo = tk.StringVar(value=NO_LOGO)
		if self.logo_paths:
			self.selected_logo.set(os.path.basename(self.logo_paths[0]))

		# Build UI
		self.create_ui()
		self.fit_window_to_content()
		# Initial placeholder display
		self.show_placeholder()

	def fit_window_to_content(self):
		"""Make sure every control is visible whatever the font size / display scaling is."""
		self.root.update_idletasks()
		needed = self.root.winfo_reqheight() + 40   # room for a two-line status message
		limit = max(600, self.root.winfo_screenheight() - 80)
		height = min(max(900, needed), limit)
		self.root.geometry(f"1240x{height}")
		self.root.minsize(1000, min(needed, limit))

	def get_logo_paths(self):
		logo_dir = os.path.join(BASE_DIR, "logo")
		os.makedirs(logo_dir, exist_ok=True)
		return sorted(glob.glob(os.path.join(logo_dir, "*.png")))

	# ------------------------------------------------------------------ UI

	def create_ui(self):
		main = ttk.Frame(self.root, padding=10)
		main.pack(fill=tk.BOTH, expand=True)

		# Controls panel
		ctrl = ttk.Frame(main, width=330, padding=10)
		ctrl.pack(side=tk.LEFT, fill=tk.Y)
		head = (None, 12, 'bold')

		# --- Image Selection ---
		ttk.Label(ctrl, text="1. Image Source", font=head).pack(anchor=tk.W, pady=(0,3))
		ttk.Button(ctrl, text="Select Image", command=self.select_image).pack(fill=tk.X, pady=3)

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
		action_row = ttk.Frame(ctrl)
		action_row.pack(fill=tk.X, pady=2)
		ttk.Button(action_row, text="Refresh Preview", command=self.generate_preview).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
		ttk.Button(action_row, text="Save Image", command=self.save_image).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))
		self.batch_btn = ttk.Button(ctrl, text="Batch Export...", command=self.batch_export)
		self.batch_btn.pack(fill=tk.X, pady=2)

		self.status_label = ttk.Label(ctrl, text="Ready", foreground='green', wraplength=300, justify=tk.LEFT)
		self.status_label.pack(anchor=tk.W, pady=(8,0))

		# Preview panel
		preview_panel = ttk.Frame(main)
		preview_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
		ttk.Label(preview_panel, text="Live Preview", font=(None,14,'bold')).pack(anchor=tk.W, pady=(0,10))

		canvas_frame = tk.Frame(preview_panel, background='#2b2b2b')
		canvas_frame.pack(fill=tk.BOTH, expand=True)

		self.canvas = tk.Canvas(canvas_frame, bg='#2b2b2b', highlightthickness=0)
		self.canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
		self.canvas.bind('<Configure>', self._on_canvas_resize)

	def _on_canvas_resize(self, event=None):
		if self.preview_ready:
			self.display_preview(PREVIEW_TEMP_PATH)
		else:
			self.show_placeholder()

	# ---------------------------------------------------------------- crop

	def current_template(self):
		return TEMPLATE_BY_MODE.get(self.preview_mode, "bottom_only")

	def current_crop_ratio(self):
		"""Width / height of the crop for the selected mode, or None for no / free-form crop."""
		mode = self.crop_mode.get()
		if mode == "ig":
			# Follow the photo: landscape -> 5:4, portrait / square -> 4:5
			target = ig_target_ratio(*self.source_size) if self.source_size else IG_RATIO
			return ig_crop_ratio(self.current_template(), target_ratio=target)
		if mode == "ig45":
			return ig_crop_ratio(self.current_template(), target_ratio=IG_RATIO)
		if mode == "ig54":
			return ig_crop_ratio(self.current_template(), target_ratio=IG_LANDSCAPE_RATIO)
		if mode == "3:2":
			return 1.5
		if mode == "1:1":
			return 1.0
		return None

	def reset_crop_box(self):
		"""Largest centred crop for the selected mode (None when cropping is off)."""
		ratio = self.current_crop_ratio()
		if ratio and self.source_size:
			self.crop_box = center_crop_box(self.source_size[0], self.source_size[1], ratio)
		else:
			self.crop_box = None
		self.update_crop_info()

	def refit_crop_box(self):
		"""Keep the current crop position but adapt it to a (slightly) different ratio."""
		ratio = self.current_crop_ratio()
		if not (ratio and self.crop_box and self.source_size):
			return
		img_w, img_h = self.source_size
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
		self.update_crop_info()

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
		self.reset_crop_box()
		if self.image_path:
			self.generate_preview()

	def update_crop_text(self):
		"""Kept for compatibility: the crop button label no longer depends on the ratio."""
		self.update_crop_info()

	def open_crop_window(self):
		if not self.source_path:
			messagebox.showinfo('Info', 'Select an image first')
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
		self.crop_win.title(f"Adjust Crop - {mode_label}")
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
		self.preview_mode = mode
		self.template_var.set(mode)
		# The IG crop ratio depends on the template (Full Frame has side borders)
		if self.crop_mode.get().startswith("ig"):
			if self.crop_win and self.crop_win.winfo_exists():
				self.crop_win.destroy()
			self.refit_crop_box()
		if self.image_path:
			self.generate_preview()
		else:
			self.show_placeholder()

	def _on_param_change(self):
		if self.image_path:
			self.generate_preview()

	def show_placeholder(self):
		self.canvas.delete('all')
		cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
		if cw < 10 or ch < 10:
			cw, ch = self.canvas.winfo_reqwidth(), self.canvas.winfo_reqheight()
		self.canvas.create_text(cw//2, ch//2,
								text="Select an Image to Start", fill='white', font=(None, 16))

	def get_selected_logo_path(self):
		selected = self.selected_logo.get()
		for path in self.logo_paths:
			if os.path.basename(path) == selected:
				return path
		return None

	def render_options(self):
		"""Settings shared by preview, save and batch export (read on the main thread)."""
		return dict(
			logo_path=self.get_selected_logo_path(),
			template_style=self.current_template(),
			canvas_ratio="ig" if self.canvas_mode.get() == "ig" else "original",
			output_width=IG_WIDTH if self.resize_var.get() else None,
		)

	@staticmethod
	def _upright_size(path):
		"""Image size after applying the EXIF orientation, without decoding the pixels."""
		with Image.open(path) as img:
			width, height = img.size
			if img.getexif().get(0x0112) in (5, 6, 7, 8):
				width, height = height, width
		return width, height

	def select_image(self):
		fp = filedialog.askopenfilename(filetypes=[('Image files','*.jpg *.jpeg *.png')])
		if not fp: return
		self.load_image(fp)

	def load_image(self, fp):
		try:
			size = self._upright_size(fp)
		except Exception as e:
			messagebox.showerror('Error', f'Cannot open image: {e}')
			return
		if self.crop_win and self.crop_win.winfo_exists():
			self.crop_win.destroy()
		self.image_path = fp
		self.source_path = fp
		self.source_size = size
		self.preview_ready = False
		self.reset_crop_box()
		self.update_status(f'Loaded: {os.path.basename(fp)}')
		self.generate_preview()

	# ------------------------------------------------------------- preview

	def generate_preview(self):
		if not self.image_path: return
		if self.processing:
			# Settings changed while rendering: render again once the current run finishes
			self.preview_pending = True
			return
		self.processing = True
		self.update_status('Generating Preview...', 'orange')
		# Read Tk state on the main thread; the worker only touches plain values
		options = self.render_options()
		options['crop_box'] = self.crop_box
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
		if error is None:
			self.preview_ready = True
			self.display_preview(PREVIEW_TEMP_PATH)
			self.update_status('Preview Ready', 'green')
		else:
			self.update_status(f'Error: {error}', 'red')
		if self.preview_pending:
			self.preview_pending = False
			self.generate_preview()

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
		if not self.image_path: return
		default_name = os.path.splitext(os.path.basename(self.source_path or self.image_path))[0] + "_IG.jpg"

		# [FIX] 增加 defaultextension 參數
		save_path = filedialog.asksaveasfilename(
			initialfile=default_name,
			filetypes=[('JPEG', '*.jpg')],
			defaultextension=".jpg"  # 確保如果使用者沒打副檔名，會自動加上 .jpg
		)

		if not save_path: return

		options = self.render_options()
		options['crop_box'] = self.crop_box

		try:
			add_exif_watermark(image_path=self.image_path, output_path=save_path, **options)
			with Image.open(save_path) as saved:
				size = saved.size
			messagebox.showinfo("Success", f"Saved to {save_path}\n{size[0]} x {size[1]} px")
		except Exception as e:
			messagebox.showerror("Error", str(e))

	def batch_export(self):
		"""Export several photos with the current template, logo, crop mode and output settings."""
		if self.batch_running: return
		files = filedialog.askopenfilenames(
			title="Select photos to export",
			filetypes=[('Image files','*.jpg *.jpeg *.png')])
		if not files: return
		out_dir = filedialog.askdirectory(title="Select output folder")
		if not out_dir: return
		self.start_batch(list(files), out_dir)

	def start_batch(self, files, out_dir):
		options = self.render_options()
		# Batch photos are cropped around their centre; a manually adjusted crop only applies to the open photo
		# "IG auto" is resolved per photo so a mixed folder gets 4:5 and 5:4 as appropriate
		options['crop_ratio'] = "ig" if self.crop_mode.get() == "ig" else self.current_crop_ratio()
		self.batch_running = True
		self.batch_btn.config(state=tk.DISABLED)
		self._batch_state = {"done": 0, "total": len(files), "name": "", "results": None}

		def progress(done, total, path):
			self._batch_state["done"] = done
			self._batch_state["name"] = os.path.basename(path) if path else ""

		def worker():
			try:
				results = batch_process(files, output_dir=out_dir, suffix="_IG", progress=progress, **options)
			except Exception as e:
				results = [(None, None, str(e))]
			self._batch_state["results"] = results

		threading.Thread(target=worker, daemon=True).start()
		self.root.after(100, lambda: self._poll_batch(out_dir))

	def _poll_batch(self, out_dir):
		state = self._batch_state
		if state["results"] is None:
			self.update_status(f'Batch {min(state["done"] + 1, state["total"])}/{state["total"]}: {state["name"]}', 'orange')
			self.root.after(100, lambda: self._poll_batch(out_dir))
			return
		self.batch_running = False
		self.batch_btn.config(state=tk.NORMAL)
		failed = [(src, err) for src, _, err in state["results"] if err]
		saved = len(state["results"]) - len(failed)
		self.update_status(f'Batch done: {saved} saved, {len(failed)} failed', 'red' if failed else 'green')
		self.show_batch_summary(out_dir, saved, failed)

	def show_batch_summary(self, out_dir, saved, failed):
		message = f"{saved} image(s) saved to\n{out_dir}"
		if failed:
			details = "\n".join(f"- {os.path.basename(src or '?')}: {err}" for src, err in failed[:10])
			messagebox.showwarning("Batch export", f"{message}\n\n{len(failed)} failed:\n{details}")
		else:
			messagebox.showinfo("Batch export", message)

if __name__ == '__main__':
	root = tk.Tk()
	app = PhotoWatermarkGUI(root)
	root.mainloop()
