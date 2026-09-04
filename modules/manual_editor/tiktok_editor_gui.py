import os
import cv2
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import config.config as cfg
import threading

# Import engine render và helper chuyển đổi ngang -> dọc
try:
    from manual_editor.tiktok_render_engine import render_tiktok_video, convert_frame_to_portrait
except ImportError:
    render_tiktok_video = None
    convert_frame_to_portrait = None

def F(size=12, weight="normal"):
    return ctk.CTkFont(family="Arial", size=size, weight=weight)
BG = ("#EFF1F5", "#1E1E2E")
BG2 = ("#DCE0E8", "#181825")
BG3 = ("#BCC0CC", "#313244")
BG4 = ("#9CA0B0", "#45475A")
T1 = ("#4C4F69", "#CDD6F4")
T2 = ("#6C6F85", "#A6ADC8")
T3 = ("#5C5F77", "#7F849C")
ORG = ("#FE640B", "#FAB387")
GRN = ("#40A02B", "#A6E3A1")
SEL = ("#1E66F5", "#89B4FA")
HOVER = ("#7287FD", "#B4BEFE")
RED = ("#D20F39", "#F38BA8")
PUR = ("#8839EF", "#CBA6F7")

class TikTokEditorApp(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0) # Cột trái (Cài đặt) cố định
        self.grid_columnconfigure(1, weight=1) # Cột phải (Preview) co giãn
        
        # State variables - Cố định kích thước dọc 1080x1920 cho TikTok
        self.video_path = None
        self.video_width = 1080
        self.video_height = 1920
        self.preview_image = None
        self.canvas_scale = 1.0
        
        self.cap = None
        self.is_playing = False
        self.current_frame_idx = 0
        self.total_frames = 0
        self.fps = 30
        
        self.custom_output_dir = None
        
        self.blur_boxes = [] # Danh sách [(x1, y1, x2, y2)] trên hệ tọa độ 1080x1920
        self.texts = []      # Danh sách [{"text": "abc", "x": x, "y": y, "voice": True, "start": 0, "end": 9999}] trên hệ tọa độ 1080x1920
        
        self.current_tool = "none" # "blur" hoặc "text"
        self.start_x = 0
        self.start_y = 0
        self.temp_rect = None
        self.dragging_text_idx = None
        
        # Load persisted settings cho TikTok
        self.load_settings()
        
        self.grid_columnconfigure(1, weight=3) # Preview
        self.grid_columnconfigure(2, weight=1) # Layers
        self.grid_rowconfigure(0, weight=1)
        
        self._build_left_panel()
        self._build_right_panel()
        self._build_layer_panel()
        
    def load_settings(self):
        settings_file = os.path.join(os.path.dirname(__file__), "tiktok_editor_settings.json")
        if os.path.exists(settings_file):
            try:
                import json
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.video_speed = settings.get("video_speed", "1.0x")
                    self.strip_metadata = settings.get("strip_metadata", False)
                    self.split_video = settings.get("split_video", False)
                    self.font_size = settings.get("font_size", 30)
                    self.text_color_hex = settings.get("text_color_hex", "#FFFF00")
                    
                    # Convert hex to RGB
                    h = self.text_color_hex.lstrip("#")
                    self.text_color_rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                    return
            except Exception as e:
                print(f"Failed to load tiktok editor settings: {e}")
        # Default fallback settings
        self.video_speed = "1.0x"
        self.strip_metadata = False
        self.split_video = False
        self.font_size = 30
        self.text_color_hex = "#FFFF00"
        self.text_color_rgb = (255, 255, 0)

    def save_settings(self):
        settings_file = os.path.join(os.path.dirname(__file__), "tiktok_editor_settings.json")
        try:
            import json
            speed = self.combo_speed.get() if hasattr(self, 'combo_speed') else self.video_speed
            strip = self.chk_metadata_var.get() if hasattr(self, 'chk_metadata_var') else self.strip_metadata
            split = self.chk_split_var.get() if hasattr(self, 'chk_split_var') else self.split_video
            size = int(self.slider_font_size.get()) if hasattr(self, 'slider_font_size') else self.font_size
            color = self.text_color_hex
            
            settings = {
                "video_speed": speed,
                "strip_metadata": strip,
                "split_video": split,
                "font_size": size,
                "text_color_hex": color
            }
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            self.lbl_status.configure(text="✅ Đã lưu cấu hình biên tập TikTok!", text_color=GRN)
        except Exception as e:
            self.lbl_status.configure(text=f"❌ Không thể lưu cấu hình: {e}", text_color=RED)

    def on_font_size_change(self, value):
        self.font_size = int(value)
        self.lbl_font_size.configure(text=f"Cỡ chữ: {self.font_size}")
        self.redraw_overlays()

    def choose_text_color(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(color=self.text_color_hex, title="Chọn màu chữ")[1]
        if color:
            self.text_color_hex = color
            # Convert hex to RGB
            h = color.lstrip("#")
            self.text_color_rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            # Determine contrast text color for the button
            contrast = "#1E1E2E" if (self.text_color_rgb[0]*0.299 + self.text_color_rgb[1]*0.587 + self.text_color_rgb[2]*0.114) > 186 else "#CDD6F4"
            self.btn_color.configure(fg_color=color, text_color=contrast)
            self.redraw_overlays()

    def _build_left_panel(self):
        self.left_panel = ctk.CTkScrollableFrame(self, width=320, corner_radius=10, fg_color=BG2, scrollbar_button_color=BG4)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        ctk.CTkLabel(self.left_panel, text="🎬 EDIT & LÁCH TIKTOK (DỌC)", font=F(16, "bold"), text_color=ORG).pack(pady=(20, 10))
        
        # Nút Tải Video
        self.btn_load = ctk.CTkButton(self.left_panel, text="📁 Chọn Video Cần Sửa", command=self.load_video, fg_color=SEL, text_color=BG, font=F(13, "bold"), height=36)
        self.btn_load.pack(fill="x", padx=20, pady=10)
        
        # Công cụ Blur
        f_blur = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_blur.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f_blur, text="1. Vùng Làm Mờ (Blur Logo)", font=F(12, "bold"), text_color=T1).pack(pady=(5, 0))
        
        self.btn_tool_blur = ctk.CTkButton(f_blur, text="[+] Bật Công cụ Vẽ Blur", command=lambda: self.set_tool("blur"), fg_color=BG4, text_color=T1, hover_color=HOVER)
        self.btn_tool_blur.pack(pady=5, padx=10, fill="x")
        
        self.btn_clear_blur = ctk.CTkButton(f_blur, text="🧹 Xóa hết Blur", command=self.clear_blurs, fg_color=RED, text_color=BG, hover_color="#C82333")
        self.btn_clear_blur.pack(pady=(0, 10), padx=10, fill="x")
        
        # Công cụ Text
        f_text = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_text.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_text, text="2. Phụ Đề Chèn Thêm", font=F(12, "bold"), text_color=T1).pack(pady=(5, 0))
        
        self.text_input = ctk.CTkEntry(f_text, placeholder_text="Gõ chữ vào đây...", font=F(12))
        self.text_input.pack(pady=5, padx=10, fill="x")
        
        self.voice_var = ctk.BooleanVar(value=True)
        self.chk_voice = ctk.CTkCheckBox(f_text, text="Tự động lồng Giọng đọc AI", variable=self.voice_var, font=F(11), text_color=T2)
        self.chk_voice.pack(pady=5, padx=10, anchor="w")
        
        self.btn_auto_sub = ctk.CTkButton(f_text, text="🤖 Tự Động Tạo Phụ Đề (AI)", command=self.auto_generate_subtitles, fg_color=SEL, text_color=BG, hover_color="#89B4FA", font=F(12, "bold"))
        self.btn_auto_sub.pack(pady=5, padx=10, fill="x")
        
        self.btn_tool_text = ctk.CTkButton(f_text, text="[A] Bật Công cụ Chèn Chữ", command=lambda: self.set_tool("text"), fg_color=PUR, text_color=BG, hover_color="#B48EAD")
        self.btn_tool_text.pack(pady=5, padx=10, fill="x")
        
        self.btn_clear_text = ctk.CTkButton(f_text, text="🧹 Xóa hết Chữ", command=self.clear_texts, fg_color=RED, text_color=BG, hover_color="#C82333")
        self.btn_clear_text.pack(pady=(0, 10), padx=10, fill="x")
        
        # Tùy Chọn Lách Bản Quyền & Định Dạng
        f_copyright = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_copyright.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_copyright, text="3. Lách Bản Quyền & Phông Chữ", font=F(12, "bold"), text_color=T1).pack(pady=(5, 0))
        
        # Tốc độ Video
        f_speed = ctk.CTkFrame(f_copyright, fg_color="transparent")
        f_speed.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_speed, text="Tốc độ:", font=F(11), text_color=T2).pack(side="left")
        self.combo_speed = ctk.CTkComboBox(f_speed, values=["1.0x", "1.1x", "1.2x", "1.25x", "1.5x", "2.0x"], width=80, height=24)
        self.combo_speed.set(self.video_speed)
        self.combo_speed.pack(side="right")
        
        # Tẩy Metadata
        self.chk_metadata_var = ctk.BooleanVar(value=self.strip_metadata)
        self.chk_metadata = ctk.CTkCheckBox(f_copyright, text="Tẩy sạch Metadata", variable=self.chk_metadata_var, font=F(11), text_color=T2)
        self.chk_metadata.pack(pady=5, padx=10, anchor="w")
        
        # Tự động Cắt Đôi Video
        self.chk_split_var = ctk.BooleanVar(value=self.split_video)
        self.chk_split = ctk.CTkCheckBox(f_copyright, text="Tự động cắt đôi Video", variable=self.chk_split_var, font=F(11), text_color=T2)
        self.chk_split.pack(pady=5, padx=10, anchor="w")
        
        # Cỡ chữ Slider
        f_font_size = ctk.CTkFrame(f_copyright, fg_color="transparent")
        f_font_size.pack(fill="x", padx=10, pady=5)
        self.lbl_font_size = ctk.CTkLabel(f_font_size, text=f"Cỡ chữ: {self.font_size}", font=F(11), text_color=T2)
        self.lbl_font_size.pack(side="left")
        self.slider_font_size = ctk.CTkSlider(f_font_size, from_=12, to=80, number_of_steps=68, width=120, height=16, command=self.on_font_size_change)
        self.slider_font_size.set(self.font_size)
        self.slider_font_size.pack(side="right")
        
        # Màu chữ
        f_color = ctk.CTkFrame(f_copyright, fg_color="transparent")
        f_color.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_color, text="Màu chữ:", font=F(11), text_color=T2).pack(side="left")
        
        contrast = "#1E1E2E" if (self.text_color_rgb[0]*0.299 + self.text_color_rgb[1]*0.587 + self.text_color_rgb[2]*0.114) > 186 else "#CDD6F4"
        self.btn_color = ctk.CTkButton(f_color, text="Chọn màu", fg_color=self.text_color_hex, text_color=contrast, width=80, height=24, command=self.choose_text_color)
        self.btn_color.pack(side="right")
        
        # Nút Lưu cấu hình
        self.btn_save_settings = ctk.CTkButton(f_copyright, text="💾 Lưu Cấu Hình", command=self.save_settings, fg_color=BG4, text_color=T1, height=28)
        self.btn_save_settings.pack(pady=(5, 10), padx=10, fill="x")
        
        # Cài đặt Nơi lưu
        f_save = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_save.pack(fill="x", padx=20, pady=10)
        self.lbl_out_dir = ctk.CTkLabel(f_save, text="Lưu tại: Mặc định (outputs)", font=F(11), text_color=T3)
        self.lbl_out_dir.pack(pady=(5,2))
        ctk.CTkButton(f_save, text="📁 Đổi Nơi Lưu", command=self.choose_output_dir, fg_color=BG4, text_color=T1, height=28).pack(pady=(0,5), padx=10, fill="x")
  
        # Nút Render
        self.btn_render = ctk.CTkButton(self.left_panel, text="🚀 XUẤT VIDEO (RENDER)", command=self.render_video, fg_color=GRN, text_color=BG, font=F(14, "bold"), height=40)
        self.btn_render.pack(fill="x", padx=20, pady=15)
        
        self.lbl_status = ctk.CTkLabel(self.left_panel, text="", font=F(11), text_color=ORG)
        self.lbl_status.pack(pady=0)
        
    def choose_output_dir(self):
        d = filedialog.askdirectory(title="Chọn Nơi Lưu")
        if d:
            self.custom_output_dir = d
            self.lbl_out_dir.configure(text=f"Lưu tại: .../{os.path.basename(d)}")

    def _build_layer_panel(self):
        self.layer_panel = ctk.CTkFrame(self, width=280, corner_radius=10, fg_color=BG2)
        self.layer_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self.layer_panel.grid_propagate(False)
        
        lbl_hint = ctk.CTkLabel(self.layer_panel, text="📑 LAYER PHỤ ĐỀ", font=F(14, "bold"), text_color=T3)
        lbl_hint.pack(pady=(15, 5))
        
        self.scroll_layers = ctk.CTkScrollableFrame(self.layer_panel, fg_color="transparent", scrollbar_button_color=BG4)
        self.scroll_layers.pack(expand=True, fill="both", padx=5, pady=5)
        
    def update_layer_panel(self):
        if not hasattr(self, 'scroll_layers'): return
        for widget in self.scroll_layers.winfo_children():
            widget.destroy()
            
        for idx, txt in enumerate(self.texts):
            row = ctk.CTkFrame(self.scroll_layers, fg_color=BG3, corner_radius=6)
            row.pack(fill="x", pady=4, padx=2)
            
            start_t = txt.get("start", 0)
            end_t = txt.get("end", 999999)
            
            def fmt(t):
                if t == 999999: return "Full"
                return f"{int(t//60):02d}:{int(t%60):02d}"
                
            time_str = f"[{fmt(start_t)} - {fmt(end_t)}]"
            
            btn_time = ctk.CTkButton(row, text=time_str, width=60, height=24, font=F(10), fg_color=BG4, hover_color=ORG, text_color=T2,
                                     command=lambda t=start_t: self.seek_to_time(t))
            btn_time.pack(side="left", padx=4, pady=4)
            
            entry_var = ctk.StringVar(value=txt["text"])
            entry = ctk.CTkEntry(row, textvariable=entry_var, font=F(11), fg_color=BG, text_color=T1, height=26)
            entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
            
            def on_text_change(event, i=idx, var=entry_var):
                self.texts[i]["text"] = var.get()
                self.redraw_overlays()
                
            entry.bind("<KeyRelease>", on_text_change)
            
            btn_del = ctk.CTkButton(row, text="✕", width=24, height=24, fg_color="transparent", hover_color=RED, text_color=RED,
                                    command=lambda i=idx: self.delete_layer(i))
            btn_del.pack(side="right", padx=2, pady=4)
            
    def seek_to_time(self, time_sec):
        if self.fps:
            frame_idx = int(time_sec * self.fps)
            self.on_slider_move(frame_idx)
            
    def delete_layer(self, idx):
        self.texts.pop(idx)
        self.update_layer_panel()
        self.redraw_overlays()

    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(self, corner_radius=10, fg_color=BG2)
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        
        lbl_hint = ctk.CTkLabel(self.right_panel, text="MÀN HÌNH PREVIEW DỌC TIKTOK (PLAY/PAUSE)", font=F(14, "bold"), text_color=T3)
        lbl_hint.pack(pady=(10, 0))
        
        # Canvas để vẽ
        self.canvas_frame = ctk.CTkFrame(self.right_panel, fg_color="black")
        self.canvas_frame.pack(expand=True, fill="both", padx=20, pady=(10, 5))
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(expand=True)
        
        # Player Controls
        f_ctrl = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        f_ctrl.pack(fill="x", padx=20, pady=(0, 15))
        
        self.btn_play = ctk.CTkButton(f_ctrl, text="▶", width=40, font=F(16), command=self.toggle_play)
        self.btn_play.pack(side="left", padx=(0, 10))
        
        self.slider_time = ctk.CTkSlider(f_ctrl, from_=0, to=100, command=self.on_slider_move)
        self.slider_time.set(0)
        self.slider_time.pack(side="left", fill="x", expand=True)
        
        self.lbl_time = ctk.CTkLabel(f_ctrl, text="00:00 / 00:00", font=F(12), width=80)
        self.lbl_time.pack(side="left", padx=10)
        
        # Bind Mouse Events
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
    def set_tool(self, tool_name):
        self.current_tool = tool_name
        self.btn_tool_blur.configure(fg_color=SEL if tool_name == "blur" else BG4)
        self.btn_tool_text.configure(fg_color=ORG if tool_name == "text" else PUR)
        
    def load_video(self):
        path = filedialog.askopenfilename(
            title="Chọn Video", 
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.mpeg *.mpg *.3gp *.m4v")]
        )
        if not path: return
        self.video_path = path
        
        if self.cap:
            self.cap.release()
            
        self.cap = cv2.VideoCapture(path)
        
        # Đối với TikTok, hệ tọa độ chỉnh sửa là dọc 1080x1920
        self.video_width = 1080
        self.video_height = 1920
        
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        self.slider_time.configure(to=self.total_frames)
        self.current_frame_idx = 0
        self.slider_time.set(0)
        
        self.lbl_status.configure(text=f"Đã tải video: {os.path.basename(path)}")
        self.read_and_show_frame()
        
    def toggle_play(self):
        if not self.cap: return
        self.is_playing = not self.is_playing
        self.btn_play.configure(text="⏸" if self.is_playing else "▶")
        if self.is_playing:
            self.update_video_loop()
            
    def update_video_loop(self):
        if self.is_playing and self.cap:
            self.read_and_show_frame()
            if self.current_frame_idx >= self.total_frames - 1:
                self.current_frame_idx = 0
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            delay = int(1000 / self.fps) if self.fps > 0 else 33
            self.after(delay, self.update_video_loop)
 
    def on_slider_move(self, value):
        if not self.cap: return
        self.current_frame_idx = int(value)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
        self.read_and_show_frame()
        
    def read_and_show_frame(self):
        if not self.cap: return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.slider_time.set(self.current_frame_idx)
            
            cur_sec = int(self.current_frame_idx / self.fps) if self.fps else 0
            tot_sec = int(self.total_frames / self.fps) if self.fps else 0
            self.lbl_time.configure(text=f"{cur_sec//60:02d}:{cur_sec%60:02d} / {tot_sec//60:02d}:{tot_sec%60:02d}")
            
            # CHUYỂN ĐỔI KHUNG HÌNH SANG DỌC KÈM LÀM MỜ NỀN BẰNG OPENCV
            if convert_frame_to_portrait is not None:
                frame = convert_frame_to_portrait(frame, self.video_width, self.video_height)
                
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.raw_preview_img = Image.fromarray(frame)
            self.update_canvas()
        
    def update_canvas(self):
        if not hasattr(self, 'raw_preview_img'): return
        
        self.update_idletasks()
        cw = self.canvas_frame.winfo_width() - 20
        ch = self.canvas_frame.winfo_height() - 20
        if cw <= 0 or ch <= 0:
            cw, ch = 800, 600
            
        img_w, img_h = self.raw_preview_img.size
        scale_w = cw / img_w
        scale_h = ch / img_h
        self.canvas_scale = min(scale_w, scale_h)
        
        new_w = int(img_w * self.canvas_scale)
        new_h = int(img_h * self.canvas_scale)
        
        self.canvas.config(width=new_w, height=new_h)
        resized_img = self.raw_preview_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        self.preview_image = ImageTk.PhotoImage(resized_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_image, tags="bg")
        
        self.redraw_overlays()
        
    def redraw_overlays(self):
        self.canvas.delete("overlay")
        
        # Vẽ các hộp Blur
        for (x1, y1, x2, y2) in self.blur_boxes:
            cx1, cy1 = x1 * self.canvas_scale, y1 * self.canvas_scale
            cx2, cy2 = x2 * self.canvas_scale, y2 * self.canvas_scale
            self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="red", width=3, stipple="gray25", fill="red", tags="overlay")
            
        # Vẽ Text
        current_time_sec = self.current_frame_idx / self.fps if self.fps else 0
        for idx, txt in enumerate(self.texts):
            start_t = txt.get("start", 0)
            end_t = txt.get("end", 999999)
            if not (start_t <= current_time_sec <= end_t):
                continue
                
            cx, cy = txt["x"] * self.canvas_scale, txt["y"] * self.canvas_scale
            tag_id = f"text_{idx}"
            
            font_style = ("Arial", self.font_size, "bold")
            offsets = [(-2,-2), (2,-2), (-2,2), (2,2), (-3,0), (3,0), (0,-3), (0,3)]
            for ox, oy in offsets:
                self.canvas.create_text(cx + ox, cy + oy, text=txt["text"], fill="black", font=font_style, anchor="center", tags=("overlay", "sub_text_bg", tag_id))
                
            self.canvas.create_text(cx, cy, text=txt["text"], fill=self.text_color_hex, font=font_style, anchor="center", tags=("overlay", "sub_text", tag_id))
            
            if txt.get("voice"):
                self.canvas.create_text(cx, cy - 30, text="🔊 [AI]", fill="#A6E3A1", font=("Arial", 10, "bold"), anchor="center", tags=("overlay", "sub_voice", tag_id))
                
        self.canvas.tag_bind("sub_text", "<Double-Button-1>", self.on_text_double_click)
        self.canvas.tag_bind("sub_text_bg", "<Double-Button-1>", self.on_text_double_click)
        self.canvas.tag_bind("sub_voice", "<Double-Button-1>", self.on_text_double_click)

    def on_text_double_click(self, event):
        item = self.canvas.find_withtag("current")
        if not item: return
        
        tags = self.canvas.gettags(item[0])
        for tag in tags:
            if tag.startswith("text_"):
                idx = int(tag.split("_")[1])
                dialog = ctk.CTkInputDialog(text="Sửa nội dung phụ đề (Xóa trắng để xóa dòng này):", title="Chỉnh sửa Phụ Đề")
                new_text = dialog.get_input()
                if new_text is not None:
                    if new_text.strip() == "":
                        self.texts.pop(idx)
                    else:
                        self.texts[idx]["text"] = new_text
                    self.redraw_overlays()
                    self.update_layer_panel()
                return

    def on_double_click(self, event):
        pass

    def on_press(self, event):
        if not self.video_path: return
        self.start_x = event.x
        self.start_y = event.y
        
        real_x = event.x / self.canvas_scale
        real_y = event.y / self.canvas_scale
        current_time_sec = self.current_frame_idx / self.fps if self.fps else 0
        
        self.dragging_text_idx = None
        for idx in range(len(self.texts)-1, -1, -1):
            txt = self.texts[idx]
            start_t = txt.get("start", 0)
            end_t = txt.get("end", 999999)
            if not (start_t <= current_time_sec <= end_t): continue
            
            if abs(txt["x"] - real_x) < 250 and abs(txt["y"] - real_y) < 50:
                self.dragging_text_idx = idx
                return
        
        if self.current_tool == "blur":
            self.temp_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2, tags="overlay")
            
        elif self.current_tool == "text":
            text_content = self.text_input.get().strip()
            if text_content:
                self.texts.append({
                    "text": text_content,
                    "x": real_x,
                    "y": real_y,
                    "voice": self.voice_var.get(),
                    "start": 0,
                    "end": 999999
                })
                self.redraw_overlays()
                self.update_layer_panel()
                self.text_input.delete(0, tk.END)

    def on_drag(self, event):
        if not self.video_path: return
        
        if self.dragging_text_idx is not None:
            real_x = int(event.x / self.canvas_scale)
            real_y = int(event.y / self.canvas_scale)
            self.texts[self.dragging_text_idx]["x"] = real_x
            self.texts[self.dragging_text_idx]["y"] = real_y
            self.redraw_overlays()
            return
            
        if self.current_tool == "blur" and self.temp_rect:
            self.canvas.coords(self.temp_rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        if not self.video_path: return
        
        if self.dragging_text_idx is not None:
            self.dragging_text_idx = None
            return
            
        if self.current_tool == "blur" and self.temp_rect:
            real_x1 = int(self.start_x / self.canvas_scale)
            real_y1 = int(self.start_y / self.canvas_scale)
            real_x2 = int(event.x / self.canvas_scale)
            real_y2 = int(event.y / self.canvas_scale)
            
            rx1, rx2 = min(real_x1, real_x2), max(real_x1, real_x2)
            ry1, ry2 = min(real_y1, real_y2), max(real_y1, real_y2)
            
            if rx2 - rx1 > 10 and ry2 - ry1 > 10:
                self.blur_boxes.append((rx1, ry1, rx2, ry2))
                
            self.canvas.delete(self.temp_rect)
            self.temp_rect = None
            self.redraw_overlays()
            
    def clear_blurs(self):
        self.blur_boxes.clear()
        self.redraw_overlays()
        
    def clear_texts(self):
        self.texts.clear()
        self.redraw_overlays()
        self.update_layer_panel()
        
    def auto_generate_subtitles(self):
        if not self.video_path:
            messagebox.showwarning("Lỗi", "Chưa chọn video!")
            return
            
        self.btn_auto_sub.configure(state="disabled", text="⏳ Đang xử lý AI...")
        threading.Thread(target=self._run_auto_sub_thread, daemon=True).start()
        
    def _run_auto_sub_thread(self):
        try:
            from automation.utils.sync_and_sub import parse_srt_to_list
            from automation.utils.whisper_engine import extract_audio, transcribe_to_srt
            from automation.utils.gemini_translator import translate_srt_with_gemini
            import tempfile
            
            self.after(0, lambda: self.lbl_status.configure(text="Đang tách âm thanh..."))
            temp_audio = os.path.join(tempfile.gettempdir(), "temp_tiktok_audio.mp3")
            temp_srt = os.path.join(tempfile.gettempdir(), "temp_tiktok_auto.srt")
            temp_translated = os.path.join(tempfile.gettempdir(), "temp_tiktok_translated.srt")
            
            extract_audio(self.video_path, temp_audio)
            if not os.path.exists(temp_audio) or os.path.getsize(temp_audio) == 0:
                self.after(0, lambda: self.lbl_status.configure(text="Không có âm thanh, đang quét chữ (OCR)..."))
                from automation.utils.ocr_engine import extract_srt_from_video_ocr
                extract_srt_from_video_ocr(self.video_path, temp_srt)
            else:
                self.after(0, lambda: self.lbl_status.configure(text="Đang nghe tiếng (Whisper)..."))
                try:
                    transcribe_to_srt(temp_audio, temp_srt)
                except Exception as e:
                    self.after(0, lambda: self.lbl_status.configure(text="Lỗi nhận diện âm thanh, đang quét chữ (OCR)..."))
                    from automation.utils.ocr_engine import extract_srt_from_video_ocr
                    extract_srt_from_video_ocr(self.video_path, temp_srt)
            
            target_lang = getattr(cfg, "TARGET_LANGUAGE", "Tiếng Việt")
            if target_lang != "Không Dịch (Giữ Nguyên Bản)":
                self.after(0, lambda: self.lbl_status.configure(text="Đang dịch thuật (Gemini)..."))
                translate_srt_with_gemini(temp_srt, temp_translated)
                final_srt = temp_translated
            else:
                final_srt = temp_srt
                
            subs = parse_srt_to_list(final_srt)
            
            # Thêm phụ đề căn giữa hoàn hảo trên hệ tọa độ dọc 1080x1920
            for sub in subs:
                self.texts.append({
                    "text": sub["text"],
                    "x": int(self.video_width / 2),    # Căn giữa chính xác trục X (540)
                    "y": int(self.video_height * 0.8), # Đặt ở phần dưới (khoảng 1536)
                    "voice": self.voice_var.get(),
                    "start": sub["start"],
                    "end": sub["end"]
                })
                
            self.after(0, lambda: self.redraw_overlays())
            self.after(0, lambda: self.update_layer_panel())
            self.after(0, lambda: self.lbl_status.configure(text="✅ Tạo phụ đề AI thành công!", text_color=GRN))
            
            if subs and self.fps:
                first_start = subs[0]["start"]
                first_frame = int(first_start * self.fps)
                self.after(0, lambda: self.on_slider_move(first_frame))
        except Exception as e:
            err_msg = f"❌ Lỗi AI: {str(e)}"
            self.after(0, lambda msg=err_msg: self.lbl_status.configure(text=msg, text_color=RED))
        finally:
            self.after(0, lambda: self.btn_auto_sub.configure(state="normal", text="🤖 Tự Động Tạo Phụ Đề (AI)"))
        
    def render_video(self):
        if not self.video_path:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn Video gốc!")
            return
            
        if render_tiktok_video is None:
            messagebox.showerror("Lỗi", "Chưa liên kết Module Render TikTok!")
            return
            
        self.btn_render.configure(state="disabled", text="⏳ ĐANG XỬ LÝ...")
        self.lbl_status.configure(text="Đang chuyển giao tọa độ cho FFmpeg...")
        
        speed_val = float(self.combo_speed.get().replace("x", ""))
        strip_metadata = self.chk_metadata_var.get()
        split_video = self.chk_split_var.get()
        font_size = self.font_size
        text_color_rgb = self.text_color_rgb
        
        threading.Thread(
            target=self._run_render_thread, 
            args=(speed_val, strip_metadata, split_video, font_size, text_color_rgb), 
            daemon=True
        ).start()
        
    def _run_render_thread(self, speed_val, strip_metadata, split_video, font_size, text_color_rgb):
        try:
            output_path = render_tiktok_video(
                self.video_path, self.blur_boxes, self.texts, self.video_width, self.video_height, 
                custom_output_dir=self.custom_output_dir,
                speed=speed_val,
                strip_metadata=strip_metadata,
                split_video=split_video,
                font_size=font_size,
                text_color=text_color_rgb
            )
            self.after(0, lambda: self.lbl_status.configure(text=f"✅ HOÀN TẤT: {os.path.basename(output_path)}", text_color=GRN))
        except Exception as e:
            err_msg = f"❌ Lỗi Render: {str(e)}"
            self.after(0, lambda msg=err_msg: self.lbl_status.configure(text=msg, text_color=RED))
        finally:
            self.after(0, lambda: self.btn_render.configure(state="normal", text="🚀 XUẤT VIDEO (RENDER)"))
