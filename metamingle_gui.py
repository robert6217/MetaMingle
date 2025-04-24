import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw
from metamingle import add_exif_watermark

class WatermarkApp:
	def __init__(self, master):
		self.master = master
		self.master.title("MetaMingle")
		self.image_path = None
		self.logo_path = None

		# 控制區塊在預覽圖下方
		control_frame = ttk.Frame(master)
		control_frame.pack(pady=10)

		# 預覽圖像區（先）
		preview_w, preview_h = 800, 600
		placeholder = Image.new("RGB", (preview_w, preview_h), color=(230, 230, 230))
		draw = ImageDraw.Draw(placeholder)
		draw.text((preview_w//2 - 100, preview_h//2 - 20), "PIC", fill=(150, 150, 150))
		photo = ImageTk.PhotoImage(placeholder)
		self.preview_label = tk.Label(master, image=photo)
		self.preview_label.image = photo
		self.preview_label.pack(pady=10)

		self.preview_path = "_preview_output.jpg"

		self.control_frame = ttk.Frame(master)
		self.control_frame.pack(pady=20, padx=20, fill="x")

		# LOGO 下拉 + label
		ttk.Label(self.control_frame, text="LOGO 選擇：").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=5)
		self.logo_var = tk.StringVar()
		self.logo_options = self.load_logo_files()
		self.logo_combo = ttk.Combobox(self.control_frame, textvariable=self.logo_var, values=self.logo_options, state="readonly", width=30)
		self.logo_combo.set("請選擇 Logo")
		self.logo_combo.grid(row=0, column=1, columnspan=2, sticky="we", pady=5)
		self.logo_combo.bind("<<ComboboxSelected>>", self.on_logo_selected)

		# Logo 大小拉桿（比例）
		ttk.Label(self.control_frame, text="Logo 大小：").grid(row=4, column=0, sticky="e", padx=(0, 8))
		self.logo_slider = ttk.Scale(self.control_frame, from_=10, to=100, orient="horizontal", length=200)
		self.logo_slider.grid(row=4, column=1, sticky="w")
		self.logo_label = ttk.Label(self.control_frame, text="30%")
		self.logo_label.grid(row=4, column=2, sticky="w")
		self.logo_slider.set(30)
		self.logo_slider.config(command=self.update_logo_label)

		# 選擇圖片按鈕（單獨置中）
		ttk.Button(self.control_frame, text="📷 選擇照片", command=self.load_image, width=30)\
			.grid(row=1, column=0, columnspan=3, pady=(10, 15))

		# 邊框寬度（滑桿 + 數值）
		ttk.Label(self.control_frame, text="邊框寬度：").grid(row=2, column=0, sticky="e", padx=(0, 8))
		self.border_slider = ttk.Scale(self.control_frame, from_=50, to=300, orient="horizontal", length=200)
		self.border_slider.grid(row=2, column=1, sticky="w")
		self.border_label = ttk.Label(self.control_frame, text="100 px")
		self.border_label.grid(row=2, column=2, sticky="w")
		self.border_slider.set(100)
		self.border_slider.config(command=self.update_border_label)

		# 字體大小（滑桿 + 數值）
		ttk.Label(self.control_frame, text="字體大小：").grid(row=3, column=0, sticky="e", padx=(0, 8))
		self.font_slider = ttk.Scale(self.control_frame, from_=30, to=200, orient="horizontal", length=200)
		self.font_slider.grid(row=3, column=1, sticky="w")
		self.font_label = ttk.Label(self.control_frame, text="60 pt")
		self.font_label.grid(row=3, column=2, sticky="w")
		self.font_slider.set(60)
		self.font_slider.config(command=self.update_font_label)

		# 儲存圖片按鈕（置中）
		ttk.Button(self.control_frame, text="💾 儲存圖片", command=self.save_output, width=30)\
			.grid(row=5, column=0, columnspan=3, pady=(20, 0))

	def update_font_label(self, val):
		self.font_label.config(text=f"{int(float(val))} pt")
		self.preview()

	def update_border_label(self, val):
		self.border_label.config(text=f"{int(float(val))} px")
		self.preview()
	
	def update_logo_label(self, val):
		self.logo_label.config(text=f"{int(float(val))}%")
		self.preview()

	def load_logo_files(self):
		logo_dir = "./logo"
		if not os.path.exists(logo_dir):
			return []
		return [f for f in os.listdir(logo_dir) if f.lower().endswith(".png")]

	def get_selected_logo_path(self):
		selected = self.logo_var.get()
		if selected == "請選擇 Logo":
			return None
		return os.path.join("logo", selected)


	def load_image(self):
		self.image_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
		self.preview()

	def preview(self):
		if not self.image_path:
			return
		border = self.border_slider.get()
		font_size = self.font_slider.get()
		logo_path = self.get_selected_logo_path()
		logo_size_percent = int(self.logo_slider.get())

		add_exif_watermark(
			self.image_path,
			output_path=self.preview_path,
			border_width=border,
			logo_path=logo_path,
			font_size=font_size,
			logo_size_percent=logo_size_percent
		)

		img = Image.open(self.preview_path)
		img.thumbnail((800, 600))
		photo = ImageTk.PhotoImage(img)
		self.preview_label.configure(image=photo)
		self.preview_label.image = photo

	def on_logo_selected(self, event=None):
		self.preview()

	def save_output(self):
		if not self.image_path:
			return
		save_path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG", "*.jpg"), ("All files", "*.*")])
		if save_path:
			border = self.border_slider.get()
			font_size = self.font_slider.get()
			logo_path = self.get_selected_logo_path()
			logo_size_percent = int(self.logo_slider.get())
			add_exif_watermark(
				self.image_path,
				output_path=save_path,
				border_width=border,
				logo_path=logo_path,
				font_size=font_size,
				logo_size_percent=logo_size_percent
			)
			tk.messagebox.showinfo("完成", f"圖片已儲存至：\n{save_path}")


if __name__ == "__main__":
	root = tk.Tk()
	app = WatermarkApp(root)
	root.mainloop()
	style = ttk.Style()
	style.theme_use("clam")
	style.configure("TButton", font=("Helvetica", 10), padding=6, relief="flat", background="#f0f0f0")
	style.configure("TLabel", background="#f0f0f0", font=("Helvetica", 10))
	style.configure("TFrame", background="#f0f0f0")
	style.configure("TScale", background="#f0f0f0")
	