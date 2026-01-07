import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import threading
from metamingle import add_exif_watermark
import glob

class PhotoWatermarkGUI:
	def __init__(self, root):
		self.root = root
		self.root.title("MetaMingle - IG Layout Editor")
		self.root.geometry("1200x850")

		# Variables
		self.image_path = None
		self.preview_image = None
		self.processing = False
		self.preview_mode = "classic"  # Default preview mode
		
		# Crop variables
		self.original_img = None
		self.crop_win = None
		self.crop_canvas = None
		self.crop_preview = None
		self.crop_rect = None
		self.crop_start_x = 0
		self.crop_start_y = 0
		self.is_cropping = False
		self.crop_ratio_val = tk.DoubleVar(value=1.5) # 預設 3:2 (1.5)

		# Logo options
		self.logo_paths = self.get_logo_paths()
		self.selected_logo = tk.StringVar()
		if self.logo_paths:
			self.selected_logo.set(os.path.basename(self.logo_paths[0]))

		# Parameters (Hidden or Default)
		self.border_width = tk.IntVar(value=100)
		self.font_size = tk.IntVar(value=120)

		# Build UI
		self.create_ui()
		# Initial placeholder display
		self.show_placeholder()

	def get_logo_paths(self):
		logo_dir = "./logo"
		if not os.path.exists(logo_dir):
			os.makedirs(logo_dir)
		return glob.glob(os.path.join(logo_dir, "*.png"))

	def create_ui(self):
		main = ttk.Frame(self.root, padding=10)
		main.pack(fill=tk.BOTH, expand=True)

		# Controls panel
		ctrl = ttk.Frame(main, width=320, padding=10)
		ctrl.pack(side=tk.LEFT, fill=tk.Y)

		# --- Image Selection ---
		ttk.Label(ctrl, text="1. Image Source", font=(None,14,'bold')).pack(anchor=tk.W, pady=(0,5))
		ttk.Button(ctrl, text="Select Image", command=self.select_image).pack(fill=tk.X, pady=5)

		# --- Crop Settings ---
		ttk.Label(ctrl, text="2. Crop Ratio", font=(None,14,'bold')).pack(anchor=tk.W, pady=(15,5))
		
		crop_frame = ttk.LabelFrame(ctrl, text="Aspect Ratio Target", padding=10)
		crop_frame.pack(fill=tk.X, pady=5)
		
		# Radio buttons for crop ratio
		ttk.Radiobutton(crop_frame, text="Landscape (3:2)", variable=self.crop_ratio_val, 
						value=1.5, command=self.update_crop_text).pack(anchor=tk.W, pady=2)
		
		ttk.Radiobutton(crop_frame, text="Square (1:1) -> IG Portrait", variable=self.crop_ratio_val, 
						value=1.0, command=self.update_crop_text).pack(anchor=tk.W, pady=2)

		self.crop_btn = ttk.Button(ctrl, text="Open Crop Window (3:2)", command=self.open_crop_window)
		self.crop_btn.pack(fill=tk.X, pady=5)

		# --- Logo ---
		ttk.Label(ctrl, text="3. Logo Style", font=(None,14,'bold')).pack(anchor=tk.W, pady=(15,5))
		combo = ttk.Combobox(ctrl, textvariable=self.selected_logo, state='readonly')
		combo['values'] = [os.path.basename(p) for p in self.logo_paths] or ['No logos found']
		combo.pack(fill=tk.X, pady=5)
		combo.bind('<<ComboboxSelected>>', lambda e: self._on_param_change())

		# --- Template ---
		ttk.Label(ctrl, text="4. Preview Template", font=(None,14,'bold')).pack(anchor=tk.W, pady=(15,5))
		preview_buttons = ttk.Frame(ctrl)
		preview_buttons.pack(fill=tk.X, pady=5)

		ttk.Button(preview_buttons, text="Bottom Only", 
				command=lambda: self.change_preview_mode("bottom")).pack(expand=True, fill=tk.X, pady=(2,2))
		ttk.Button(preview_buttons, text="Full Frame", 
				command=lambda: self.change_preview_mode("full")).pack(expand=True, fill=tk.X, pady=(2,2))
		ttk.Button(preview_buttons, text="Classic Layout", 
				command=lambda: self.change_preview_mode("classic")).pack(expand=True, fill=tk.X, pady=(2,2))
		
		# --- Actions ---
		ttk.Label(ctrl, text="5. Actions", font=(None,14,'bold')).pack(anchor=tk.W, pady=(15,5))

		ttk.Button(ctrl, text="Refresh Preview", command=self.generate_preview).pack(fill=tk.X, pady=(5,5))
		ttk.Button(ctrl, text="Save Image", command=self.save_image).pack(fill=tk.X, pady=5)
		
		self.status_label = ttk.Label(ctrl, text="Ready", foreground='green')
		self.status_label.pack(anchor=tk.W, pady=(15,0))

		# Preview panel
		preview_panel = ttk.Frame(main)
		preview_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
		ttk.Label(preview_panel, text="Live Preview", font=(None,14,'bold')).pack(anchor=tk.W, pady=(0,10))
		
		canvas_frame = tk.Frame(preview_panel, background='#2b2b2b')
		canvas_frame.pack(fill=tk.BOTH, expand=True)
		
		self.canvas = tk.Canvas(canvas_frame, bg='#2b2b2b', highlightthickness=0)
		self.canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

	def update_crop_text(self):
		ratio = self.crop_ratio_val.get()
		if ratio == 1.5:
			self.crop_btn.config(text="Open Crop Window (3:2)")
		else:
			self.crop_btn.config(text="Open Crop Window (1:1)")

	def open_crop_window(self):
		if not self.image_path:
			messagebox.showinfo('Info', 'Select an image first')
			return
				
		if self.crop_win and self.crop_win.winfo_exists():
			self.crop_win.destroy()
			
		img = Image.open(self.image_path)
		self.original_img = ImageOps.exif_transpose(img) 
		
		width, height = self.original_img.size
		target_ratio = self.crop_ratio_val.get()

		self.crop_win = tk.Toplevel(self.root)
		title = "Crop to 3:2" if target_ratio == 1.5 else "Crop to Square (1:1)"
		self.crop_win.title(title)
		self.crop_win.geometry("900x700")
		
		msg = "Drag to position the area."
		if target_ratio == 1.0:
			msg += "\n(Square crop + Bottom Bar ≈ Perfect IG 4:5 Portrait)"
			
		ttk.Label(self.crop_win, text=msg, font=(None, 12)).pack(pady=10)
		
		canvas_frame = tk.Frame(self.crop_win, background='black')
		canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
		
		self.crop_canvas = tk.Canvas(canvas_frame, highlightthickness=0, bg='black')
		self.crop_canvas.pack(fill=tk.BOTH, expand=True)
		
		self.display_crop_preview()
		self.init_crop_rect(target_ratio)
		
		self.crop_canvas.bind("<ButtonPress-1>", self.on_crop_start)
		self.crop_canvas.bind("<B1-Motion>", self.on_crop_move)
		self.crop_canvas.bind("<ButtonRelease-1>", self.on_crop_end)
		
		ttk.Button(self.crop_win, text="Apply Crop", command=self.apply_crop).pack(pady=10)

	def display_crop_preview(self):
		if not self.original_img: return
		self.crop_canvas.update_idletasks()
		cw, ch = self.crop_canvas.winfo_width(), self.crop_canvas.winfo_height()
		if cw <= 1 or ch <= 1: cw, ch = 800, 600

		img_preview = ImageOps.contain(self.original_img, (cw, ch), Image.LANCZOS)
		self.crop_preview_scale = min(cw / self.original_img.width, ch / self.original_img.height)
		
		preview_w, preview_h = img_preview.size
		cx, cy = (cw - preview_w) // 2, (ch - preview_h) // 2
		
		self.crop_preview_pos = (cx, cy)
		self.crop_preview_size = (preview_w, preview_h)
		
		self.crop_photo_obj = ImageTk.PhotoImage(img_preview)
		self.crop_canvas.delete('all')
		self.crop_canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=self.crop_photo_obj)

	def init_crop_rect(self, ratio_val):
		if not self.original_img: return
		img_w, img_h = self.original_img.size
		preview_w, preview_h = self.crop_preview_size
		cx, cy = self.crop_preview_pos
		
		if (img_w / img_h) > ratio_val:
			crop_h = img_h
			crop_w = crop_h * ratio_val
		else:
			crop_w = img_w
			crop_h = crop_w / ratio_val
			
		rect_width = crop_w * self.crop_preview_scale
		rect_height = crop_h * self.crop_preview_scale
		
		x1 = cx + (preview_w - rect_width) / 2
		y1 = cy + (preview_h - rect_height) / 2
		x2 = x1 + rect_width
		y2 = y1 + rect_height
		
		self.crop_rect = self.crop_canvas.create_rectangle(
			x1, y1, x2, y2, outline='white', width=2, dash=(5, 5)
		)
		self.crop_rect_coords = [x1, y1, x2, y2]

	def on_crop_start(self, event):
		if not self.crop_rect: return
		x1, y1, x2, y2 = self.crop_canvas.coords(self.crop_rect)
		if x1 <= event.x <= x2 and y1 <= event.y <= y2:
			self.is_cropping = True
			self.crop_start_x = event.x
			self.crop_start_y = event.y

	def on_crop_move(self, event):
		if not self.is_cropping or not self.crop_rect: return
		dx = event.x - self.crop_start_x
		dy = event.y - self.crop_start_y
		
		self.crop_canvas.move(self.crop_rect, dx, dy)
		self.crop_start_x = event.x
		self.crop_start_y = event.y
		
		coords = self.crop_canvas.coords(self.crop_rect)
		self.crop_rect_coords = coords

	def on_crop_end(self, event):
		self.is_cropping = False

	def apply_crop(self):
		if not self.original_img or not self.crop_rect: return
		
		x1, y1, x2, y2 = self.crop_rect_coords
		cx, cy = self.crop_preview_pos
		
		crop_x1 = (x1 - cx) / self.crop_preview_scale
		crop_y1 = (y1 - cy) / self.crop_preview_scale
		crop_x2 = (x2 - cx) / self.crop_preview_scale
		crop_y2 = (y2 - cy) / self.crop_preview_scale
		
		crop_x1 = max(0, crop_x1)
		crop_y1 = max(0, crop_y1)
		crop_x2 = min(self.original_img.width, crop_x2)
		crop_y2 = min(self.original_img.height, crop_y2)
		
		exif_data = self.original_img.info.get('exif')
		cropped_img = self.original_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
		
		temp_path = os.path.join(os.path.dirname(self.image_path), '_cropped_temp.jpg')
		
		if exif_data:
			cropped_img.save(temp_path, quality=95, exif=exif_data)
		else:
			cropped_img.save(temp_path, quality=95)
			
		self.image_path = temp_path
		self.update_status(f'Image cropped to {self.crop_ratio_val.get()}:1')
		self.crop_win.destroy()
		self.generate_preview()

	def change_preview_mode(self, mode):
		self.preview_mode = mode
		if self.image_path:
			self.generate_preview()
		else:
			self.show_placeholder()

	def _on_param_change(self):
		if self.image_path:
			self.generate_preview()

	def show_placeholder(self):
		self.canvas.delete('all')
		self.canvas.create_text(self.canvas.winfo_reqwidth()//2, self.canvas.winfo_reqheight()//2, 
								text="Select an Image to Start", fill='white', font=(None, 16))

	def get_selected_logo_path(self):
		selected = self.selected_logo.get()
		for path in self.logo_paths:
			if os.path.basename(path) == selected:
				return path
		return None

	def select_image(self):
		fp = filedialog.askopenfilename(filetypes=[('Image files','*.jpg *.jpeg *.png')])
		if not fp: return
		self.image_path = fp
		self.update_status(f'Loaded: {os.path.basename(fp)}')
		self.generate_preview()

	def generate_preview(self):
		if not self.image_path: return
		if self.processing: return
		self.processing = True
		self.update_status('Generating Preview…', 'orange')
		threading.Thread(target=self._process_preview).start()

	def _process_preview(self):
		tmp = "preview_temp.jpg"
		logo = self.get_selected_logo_path()
		
		if self.preview_mode == "full":
			template = "full_frame"
		elif self.preview_mode == "classic":
			template = "classic"
		else:
			template = "bottom_only"
		
		try:
			add_exif_watermark(
				image_path=self.image_path,
				output_path=tmp,
				logo_path=logo,
				template_style=template,
			)
			self.root.after(0, lambda: self.display_preview(tmp))
			self.root.after(0, lambda: self.update_status('Preview Ready', 'green'))
		except Exception as e:
			self.root.after(0, lambda: self.update_status(f'Error: {e}', 'red'))
		finally:
			self.processing = False

	def display_preview(self, image_path):
		if not os.path.exists(image_path): return
		img = Image.open(image_path)
		
		self.canvas.update_idletasks()
		cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
		if cw < 10: cw, ch = 800, 600
		
		img_resized = ImageOps.contain(img, (cw, ch), Image.LANCZOS)
		self.preview_photo = ImageTk.PhotoImage(img_resized)
		
		self.canvas.delete('all')
		self.canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=self.preview_photo)

	def update_status(self, msg, color="green"):
		self.status_label.config(text=msg, foreground=color)

	def save_image(self):
		if not self.image_path: return
		default_name = os.path.splitext(os.path.basename(self.image_path))[0] + "_IG.jpg"
		
		# [FIX] 增加 defaultextension 參數
		save_path = filedialog.asksaveasfilename(
			initialfile=default_name, 
			filetypes=[('JPEG', '*.jpg')],
			defaultextension=".jpg"  # 確保如果使用者沒打副檔名，會自動加上 .jpg
		)
		
		if not save_path: return
		
		logo = self.get_selected_logo_path()
		
		if self.preview_mode == "full":
			template = "full_frame"
		elif self.preview_mode == "classic":
			template = "classic"
		else:
			template = "bottom_only"
		
		try:
			add_exif_watermark(
				image_path=self.image_path,
				output_path=save_path,
				logo_path=logo,
				template_style=template
			)
			messagebox.showinfo("Success", f"Saved to {save_path}")
		except Exception as e:
			messagebox.showerror("Error", str(e))

if __name__ == '__main__':
	root = tk.Tk()
	app = PhotoWatermarkGUI(root)
	root.mainloop()
