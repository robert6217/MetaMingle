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
		self.root.title("MetaMingle")
		self.root.geometry("1200x800")

		# Variables
		self.image_path = None
		self.preview_image = None
		self.processing = False
		self.preview_mode = "classic"  # Default preview mode (bottom or full or classic)

		# Logo options
		self.logo_paths = self.get_logo_paths()
		self.selected_logo = tk.StringVar()
		if self.logo_paths:
			self.selected_logo.set(os.path.basename(self.logo_paths[0]))

		# Parameters
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
		ctrl = ttk.Frame(main, width=300, padding=10)
		ctrl.pack(side=tk.LEFT, fill=tk.Y)

		ttk.Label(ctrl, text="Image Processing", font=(None,14,'bold')).pack(anchor=tk.W, pady=(0,10))
		ttk.Button(ctrl, text="Select Image", command=self.select_image).pack(fill=tk.X, pady=5)

		ttk.Label(ctrl, text="Logo Selection", font=(None,12)).pack(anchor=tk.W, pady=(10,5))
		combo = ttk.Combobox(ctrl, textvariable=self.selected_logo, state='readonly')
		combo['values'] = [os.path.basename(p) for p in self.logo_paths] or ['No logos found']
		combo.pack(fill=tk.X, pady=5)
		combo.bind('<<ComboboxSelected>>', lambda e: self._on_param_change())

		# Uncomment the following lines if you want to add sliders for border width and font size
		# ttk.Label(ctrl, text="Parameters", font=(None,12)).pack(anchor=tk.W, pady=(10,5))
		# for label,var,minv,maxv in [
		# 	("Border Width", self.border_width,50,300),
		# 	("Font Size", self.font_size,60,200)
		# ]:
		# 	ttk.Label(ctrl, text=label).pack(anchor=tk.W)
		# 	s = ttk.Scale(ctrl, from_=minv, to=maxv, variable=var, orient=tk.HORIZONTAL)
		# 	s.pack(fill=tk.X, pady=5)
		# 	s.bind('<ButtonRelease-1>', lambda e: self._on_param_change())

		# Preview template selection
		ttk.Label(ctrl, text="Preview Template", font=(None,12)).pack(anchor=tk.W, pady=(10,5))
		preview_buttons = ttk.Frame(ctrl)
		preview_buttons.pack(fill=tk.X, pady=5)

		# Create a frame for the first row of buttons
		ttk.Button(preview_buttons, text="Bottom Preview", 
				command=lambda: self.change_preview_mode("bottom")).pack(expand=True, fill=tk.X, pady=(5,0))
		
		ttk.Button(preview_buttons, text="Full Preview", 
				command=lambda: self.change_preview_mode("full")).pack(expand=True, fill=tk.X, pady=(5,0))

		# Add the Classic button in a second row
		ttk.Button(preview_buttons, text="Classic", 
				command=lambda: self.change_preview_mode("classic")).pack(expand=True, fill=tk.X, pady=(5,0))
		
		ttk.Label(ctrl, text="Operation", font=(None,12)).pack(anchor=tk.W, pady=(10,5))

		ttk.Button(ctrl, text="Generate Preview", command=self.generate_preview).pack(fill=tk.X, pady=(15,5))
		ttk.Button(ctrl, text="Save Image", command=self.save_image).pack(fill=tk.X, pady=5)
		self.status_label = ttk.Label(ctrl, text="Ready", foreground='green')
		self.status_label.pack(anchor=tk.W, pady=(15,0))

		# Preview panel
		preview_panel = ttk.Frame(main)
		preview_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
		ttk.Label(preview_panel, text="Preview", font=(None,14,'bold')).pack(anchor=tk.W, pady=(0,10))
		
		canvas_frame = tk.Frame(preview_panel, background='black')
		canvas_frame.pack(fill=tk.BOTH, expand=True)
		
		self.canvas = tk.Canvas(canvas_frame, bg='black', highlightthickness=0)
		self.canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

		self.change_preview_mode("classic")

	def change_preview_mode(self, mode):
		"""Change the preview template mode and update the preview"""
		self.preview_mode = mode
		if self.image_path:
			self.generate_preview()
		else:
			self.show_placeholder()

	def _on_param_change(self):
		if self.image_path:
			self.generate_preview()
		else:
			self.show_placeholder()

	def show_placeholder(self):
		"""Use preview template as placeholder: add border and watermark, then display."""
		self.canvas.delete('all')
		
		# Select template based on current mode
		template = f'preview_{self.preview_mode}.png'
		
		if not os.path.exists(template):
			self.canvas.create_text(300, 200, text=f'{template} not found', font=(None,20), fill='red')
			return
			
		# Display template directly
		try:
			img = Image.open(template)
			
			# Calculate canvas dimensions
			self.canvas.update_idletasks()
			cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
			
			# Resize while preserving aspect ratio
			img_resized = ImageOps.contain(img, (cw, ch), Image.LANCZOS)
			photo = ImageTk.PhotoImage(img_resized)
			
			# Store and display the image
			self.preview_image = photo
			self.canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=photo)
			self.update_status(f'Preview template: {template}', 'green')
		except Exception as e:
			print('Placeholder error:', e)
			self.canvas.create_text(300, 200, text='Error loading placeholder', font=(None,20), fill='red')

	def get_selected_logo_path(self):
		"""Return full path of currently selected logo or None if not found."""
		selected = self.selected_logo.get()
		for path in self.logo_paths:
			if os.path.basename(path) == selected:
				return path
		return None

	def select_image(self):
		fp = filedialog.askopenfilename(filetypes=[('Image files','*.jpg *.jpeg *.png')])
		if not fp: return
		self.image_path = fp
		self.update_status(f'Image: {os.path.basename(fp)}')
		self.generate_preview()

	def generate_preview(self):
		"""Generate preview for the selected image."""
		if not self.image_path:
			messagebox.showinfo('Info','Select an image first')
			return
		if self.processing: return
		self.processing = True
		self.update_status('Generating…','orange')
		threading.Thread(target=self._process_preview).start()

	def _process_preview(self):
		tmp = os.path.join(os.path.dirname(self.image_path), '_tmp'+os.path.splitext(self.image_path)[1])
		bw = self.border_width.get()
		fs = self.font_size.get()
		logo = self.get_selected_logo_path()
		
		# In _process_preview function:
		# 根據當前預覽模式設定模板樣式
		if self.preview_mode == "full":
			template_style = "full_frame"
		elif self.preview_mode == "classic":
			template_style = "classic"
		else:  # bottom mode
			template_style = "bottom_only"
		
		try:
			add_exif_watermark(
				image_path=self.image_path,
				output_path=tmp,
				# border_width=bw,
				logo_path=logo,
				# font_size=fs,
				template_style=template_style
			)
			self.display_preview(image_path=tmp)
			self.update_status('Ready','green')
		except Exception as e:
			self.update_status(str(e),'red')
		finally:
			self.processing=False
			if os.path.exists(tmp):
				try: os.remove(tmp)
				except: pass

	def update_status(self, msg, color="green"):
		self.status_label.config(text=msg, foreground=color)
		self.root.update_idletasks()

	def display_preview(self, image_path=None, image_obj=None):
		if image_obj is not None:
			img = image_obj.copy()
		elif image_path and os.path.exists(image_path):
			img = Image.open(image_path)
		else:
			return
			
		# Calculate canvas dimensions
		self.canvas.update_idletasks()
		cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
		
		# Resize while preserving aspect ratio
		img_resized = ImageOps.contain(img, (cw, ch), Image.LANCZOS)
		photo = ImageTk.PhotoImage(img_resized)
		
		# Store and display the image
		self.preview_image = photo
		self.canvas.delete('all')
		self.canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=photo)

	def save_image(self):
		if not self.image_path:
			messagebox.showinfo('Info','Select an image first')
			return
		if self.processing: return
		default = os.path.splitext(os.path.basename(self.image_path))[0]+'_watermarked'+os.path.splitext(self.image_path)[1]
		sp = filedialog.asksaveasfilename(defaultextension=os.path.splitext(self.image_path)[1], initialfile=default,
											filetypes=[('PNG','*.png'),('JPEG','*.jpg'),('All','*.*')])
		if not sp: return
		self.processing=True
		self.update_status('Saving…','orange')
		threading.Thread(target=lambda: self._process_final(sp)).start()

	def _process_final(self, save_path):
		bw = self.border_width.get()
		fs = self.font_size.get()
		logo = self.get_selected_logo_path()
		
		if self.preview_mode == "full":
			template_style = "full_frame"
		elif self.preview_mode == "classic":
			template_style = "classic"
		else:  # bottom mode
			template_style = "bottom_only"
		
		try:
			add_exif_watermark(
				image_path=self.image_path,
				output_path=save_path,
				# border_width=bw,
				logo_path=logo,
				# font_size=fs,
				template_style=template_style
			)
			self.update_status(f'Saved to {os.path.basename(save_path)}','green')
			messagebox.showinfo('Done',f'Saved:\n{save_path}')
		except Exception as e:
			self.update_status(str(e),'red')
			messagebox.showerror('Error',str(e))
		finally:
			self.processing=False

if __name__ == '__main__':
	root=tk.Tk()
	app=PhotoWatermarkGUI(root)
	root.mainloop()
