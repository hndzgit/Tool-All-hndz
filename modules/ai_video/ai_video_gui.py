import os
import sys
import json

# Add modules and automation paths to sys.path to guarantee imports resolve
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
automation_dir = os.path.join(parent_dir, "automation")
for d in [parent_dir, automation_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading
import time
import subprocess
import platform
import config.config as cfg
from automation.utils.sync_and_sub import process_video_pipeline

def F(size=12, weight="normal"):
    return ctk.CTkFont(family="Arial", size=size, weight=weight)

BG = ("#EFF1F5", "#1E1E2E")
BG2 = ("#DCE0E8", "#181825")
BG3 = ("#BCC0CC", "#313244")
BG4 = ("#9CA0B0", "#45475A")
T1 = ("#4C4F69", "#CDD6F4")
T2 = ("#6C6F85", "#A6ADC8")
T3 = ("#5C5F77", "#7F849C")
BORDER = ("#BCC0CC", "#313244")
ORG = ("#FE640B", "#FAB387")
GRN = ("#40A02B", "#A6E3A1")
SEL = ("#1E66F5", "#89B4FA")
HOVER = ("#7287FD", "#B4BEFE")
RED = ("#D20F39", "#F38BA8")
PUR = ("#8839EF", "#CBA6F7")

def has_audio_stream(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
        "-of", "csv=p=0", file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return "audio" in res.stdout
    except:
        return False

def get_video_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(res.stdout.strip())
    except:
        return 0.0

def get_system_fonts():
    paths = [
        "/System/Library/Fonts",
        "/System/Library/Fonts/Supplemental",
        "/Library/Fonts",
        os.path.expanduser("~/Library/Fonts")
    ]
    if platform.system() == "Windows":
        paths = ["C:\\Windows\\Fonts"]
        
    fonts = {}
    
    # Priority font: NVN Cocogoose Vintage 2 (found in the user's Library folder)
    priority_path = "/Users/hoainam/Library/Fonts/NVNCocogooseVintage-Regular.ttf"
    if os.path.exists(priority_path):
        fonts["NVN Cocogoose Vintage 2"] = priority_path
    else:
        # Fallback registration in case it's in a different fonts path or relative path
        fonts["NVN Cocogoose Vintage 2"] = priority_path
        
    fonts["Mặc định (BeVietnamPro-Bold)"] = "BeVietnamPro-Bold.ttf"
    
    for p in paths:
        if os.path.exists(p):
            try:
                for f in os.listdir(p):
                    if f.lower().endswith((".ttf", ".otf", ".ttc")):
                        name = os.path.splitext(f)[0]
                        if name not in fonts:
                            fonts[name] = os.path.join(p, f)
            except:
                pass
    return fonts

class AIVideoApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0) # Left panel
        self.grid_columnconfigure(1, weight=1) # Center canvas
        self.grid_columnconfigure(2, weight=0) # Right settings list
        
        # State variables
        self.video_paths = []
        self.output_dir = ""
        self.preview_image = None
        self.canvas_scale = 1.0
        self.order_image_path = None
        
        self.cap = None
        self.current_frame_idx = 0
        self.total_frames = 0
        self.fps = 30
        self.video_width = 1080
        self.video_height = 1920
        
        self.blur_boxes = [] # List of (x1, y1, x2, y2) in original resolution
        self.current_tool = "none" # "blur"
        self.start_x = 0
        self.start_y = 0
        self.temp_rect = None
        
        self.is_running = False
        self.stop_event = threading.Event()
        
        # Subtitle styling state
        self.sub_x_ratio = 0.5
        self.sub_y_ratio = 0.8
        self.sub_size_scale = 1.0
        self.sub_color_hex = "#FFFF00" # default yellow
        self.system_fonts_map = get_system_fonts()
        
        # Build ordered list of keys: NVN Cocogoose Vintage 2 first, then defaults, then others
        self.font_names = []
        if "NVN Cocogoose Vintage 2" in self.system_fonts_map:
            self.font_names.append("NVN Cocogoose Vintage 2")
        if "Mặc định (BeVietnamPro-Bold)" in self.system_fonts_map:
            self.font_names.append("Mặc định (BeVietnamPro-Bold)")
            
        other_fonts = sorted([k for k in self.system_fonts_map.keys() if k not in ["NVN Cocogoose Vintage 2", "Mặc định (BeVietnamPro-Bold)"]])
        self.font_names.extend(other_fonts)
        
        # Set default font to NVN Cocogoose Vintage 2
        self.sub_font_name = self.system_fonts_map.get("NVN Cocogoose Vintage 2", "BeVietnamPro-Bold.ttf")
        
        self.dragging_sub = False
        
        # Available Vbee voices (must match gui.py exactly)
        self.vbee_voices = {
            "Xoay Vòng Ngẫu Nhiên": "random",
            "Ngọc Huyền (Nữ HN)":  "vbee:hn_female_ngochuyen_full_48k-fhg",
            "Mai Phương (Nữ HN)":   "vbee:hn_female_maiphuong_ngam_48k-fhg",
            "Thảo Trinh (Nữ HN)":  "vbee:hn_female_thaotrinh_full_48k-fhg",
            "Hương Giang (Nữ SG)": "vbee:sg_female_huonggiang_full_48k-fhg",
            "Minh Hoàng (Nam SG)":  "vbee:sg_male_minhhoang_full_48k-fhg",
            "Minh Quân (Nam HN)":   "vbee:hn_male_minhquan_yt-stable",
            "Phú Thăng (Nam HN)":   "vbee:hn_male_phuthang_news65dt_44k-fhg",
            "Duy Phương (Nam Huế)": "vbee:hue_male_duyphuong_full_48k-fhg",
            "Diệu Hương (Nữ HN - News)": "vbee:n_hanoi_female_dieuhuong20260421111346189_news_vc",
            "Vũ Thị Lan Hương (Nữ TQ - Adv)": "vbee:n_tuyenquang_female_vuthilanhuong_advertise_vc",
            "Ngọc Anh (Nữ HN - Book)": "vbee:n_hanoi_female_ngocanhdangg_book_vc",
            "Nam Nhẹ Nhàng (Nam HN - Story)": "vbee:n_hanoi_male_namnhenhangamap_story_vc",
            "Sĩ Tăng Nguyễn (Nam HN - Edu)": "vbee:n_hanoi_male_sizonguyen_education_vc",
            "Nhà Báo Hoàng Nam (Nam HN - News)": "vbee:n_hanoi_male_nhabaohoangnam_news_vc",
        }
        
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        # 1. LEFT PANEL: Queue Management
        self.left_panel = ctk.CTkFrame(self, width=280, corner_radius=10, fg_color=BG2)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.left_panel.grid_propagate(False)
        
        ctk.CTkLabel(self.left_panel, text="🎞 DANH SÁCH VIDEO AI", font=F(14, "bold"), text_color=ORG).pack(pady=(15, 5))
        
        btn_in = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        btn_in.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_in, text="📁 Chọn Video", command=self.load_files, fg_color=SEL, text_color=BG, font=F(12, "bold"), height=30).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_in, text="🧹 Xóa Hết", command=self.clear_queue, fg_color=RED, text_color=BG, font=F(12), height=30).pack(side="left", padx=(5, 0))
        
        # Listbox-like Scrollable List for video items
        self.scroll_queue = ctk.CTkScrollableFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        self.scroll_queue.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Item controls
        btn_ctrl = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        btn_ctrl.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_ctrl, text="▲ Lên", width=50, command=lambda: self.move_item(-1), fg_color=BG4, text_color=T1).pack(side="left", padx=2)
        ctk.CTkButton(btn_ctrl, text="▼ Xuống", width=50, command=lambda: self.move_item(1), fg_color=BG4, text_color=T1).pack(side="left", padx=2)
        ctk.CTkButton(btn_ctrl, text="✕ Xóa", width=50, command=self.delete_selected, fg_color=RED, text_color=BG).pack(side="right", padx=2)
        
        self.lbl_queue_status = ctk.CTkLabel(self.left_panel, text="Chưa nạp video", text_color=T3, font=F(11))
        self.lbl_queue_status.pack(pady=5)

        # 2. CENTER PANEL: Preview Canvas for Blurring & Subtitle dragging
        self.center_panel = ctk.CTkFrame(self, corner_radius=10, fg_color=BG2)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=5)
        
        ctk.CTkLabel(self.center_panel, text="📺 PREVIEW (VẼ BLUR & KÉO THẢ PHỤ ĐỀ)", font=F(14, "bold"), text_color=T1).pack(pady=(15, 5))
        
        # Canvas frame
        self.canvas_frame = ctk.CTkFrame(self.center_panel, fg_color="black")
        self.canvas_frame.pack(expand=True, fill="both", padx=15, pady=5)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(expand=True)
        
        # Bind Mouse events to draw box and drag subtitles
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Tools row
        tools_row = ctk.CTkFrame(self.center_panel, fg_color="transparent")
        tools_row.pack(fill="x", padx=15, pady=10)
        
        self.btn_blur_tool = ctk.CTkButton(tools_row, text="✏️ Vẽ Vùng Blur", fg_color=BG4, text_color=T1, hover_color=HOVER, command=self.toggle_blur_tool)
        self.btn_blur_tool.pack(side="left", padx=5)
        
        ctk.CTkButton(tools_row, text="🧹 Xóa Vùng Blur", fg_color=RED, text_color=BG, hover_color="#C82333", command=self.clear_blurs).pack(side="left", padx=5)
        
        # Hint label for dragging
        ctk.CTkLabel(tools_row, text="💡 Nhấp & Kéo chữ phụ đề trên màn hình để di chuyển vị trí!", font=F(11), text_color=T3).pack(side="right", padx=5)

        # 3. RIGHT PANEL: Config & Actions
        self.right_panel = ctk.CTkFrame(self, width=320, corner_radius=10, fg_color=BG2)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self.right_panel.grid_propagate(False)
        
        # Bottom actions frame (sticky at the bottom, does not scroll!)
        f_bottom_actions = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        f_bottom_actions.pack(side="bottom", fill="x", padx=10, pady=(5, 10))
        
        self.btn_save_config = ctk.CTkButton(f_bottom_actions, text="💾 LƯU CẤU HÌNH", font=F(13, "bold"), fg_color=SEL, text_color=T1, hover_color="#0056b3", height=36, command=self.on_click_manual_save)
        self.btn_save_config.pack(fill="x", pady=4)

        self.btn_start = ctk.CTkButton(f_bottom_actions, text="🚀 RÁP & RENDER CẶP VIDEO", font=F(14, "bold"), fg_color=GRN, text_color=BG, height=45, command=self.start_processing)
        self.btn_start.pack(fill="x", pady=4)
        
        self.btn_stop = ctk.CTkButton(f_bottom_actions, text="🛑 Dừng Lại", font=F(14, "bold"), fg_color=RED, text_color=BG, height=35, state="disabled", command=self.stop_processing)
        self.btn_stop.pack(fill="x", pady=4)
        
        # Scrollable right panel for detailed config options (occupies the remaining top space)
        scroll_config = ctk.CTkScrollableFrame(self.right_panel, fg_color="transparent")
        scroll_config.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(scroll_config, text="⚙️ CẤU HÌNH PIPELINE", font=F(14, "bold"), text_color=T1).pack(pady=(10, 10))
        
        # Script / Subtitle source
        ctk.CTkLabel(scroll_config, text="Nguồn Phụ đề & Kịch bản:", font=F(12, "bold"), text_color=T2).pack(anchor="w", padx=10, pady=(5, 0))
        self.combo_sub_source = ctk.CTkOptionMenu(scroll_config, values=["Whisper (Trích âm thanh)", "OCR (Quét chữ màn hình)", "Gemini (Mắt thần tự viết)", "Gemini (Phân tích ảnh đơn hàng)"], fg_color=BG3, text_color=T1, command=self.on_change_sub_source)
        self.combo_sub_source.pack(fill="x", padx=10, pady=5)
        self.combo_sub_source.set("Whisper (Trích âm thanh)")
        
        # Order / Product Image picker
        self.f_order_img = ctk.CTkFrame(scroll_config, fg_color="transparent")
        self.f_order_img.pack(fill="x", padx=10, pady=5)
        self.btn_order_img = ctk.CTkButton(self.f_order_img, text="📸 Chọn Ảnh Đơn Hàng", fg_color=BG4, text_color=T1, height=28, command=self.choose_order_image)
        self.btn_order_img.pack(fill="x", pady=2)
        self.lbl_order_img = ctk.CTkLabel(self.f_order_img, text="Chưa chọn ảnh đơn hàng", text_color=T3, font=F(11))
        self.lbl_order_img.pack(pady=2)
        
        # Vbee Voice selection
        ctk.CTkLabel(scroll_config, text="Giọng đọc Vbee AI (VIP):", font=F(12, "bold"), text_color=T2).pack(anchor="w", padx=10, pady=(10, 0))
        f_voice_row = ctk.CTkFrame(scroll_config, fg_color="transparent")
        f_voice_row.pack(fill="x", padx=10, pady=5)
        
        self.btn_test_voice = ctk.CTkButton(
            f_voice_row, text="▶ Nghe Thử", command=self.play_test_voice,
            fg_color=BG4, hover_color=HOVER, text_color=ORG,
            corner_radius=8, font=F(11, "bold"), height=28, width=80
        )
        self.btn_test_voice.pack(side="right", padx=(6, 0))

        self.combo_voice = ctk.CTkOptionMenu(
            f_voice_row, values=list(self.vbee_voices.keys()), fg_color=BG3, text_color=T1, 
            command=lambda x: self.save_settings(), height=28
        )
        self.combo_voice.pack(side="left", fill="x", expand=True)
        self.combo_voice.set("Diệu Hương (Nữ HN - News)")
        
        # Options checkboxes
        self.sub_var = ctk.BooleanVar(value=True)
        self.chk_sub = ctk.CTkCheckBox(scroll_config, text="Hiển thị phụ đề (Burn sub)", variable=self.sub_var, font=F(12), text_color=T2, command=self.on_toggle_sub_checkbox)
        self.chk_sub.pack(anchor="w", padx=10, pady=5)
        
        self.mute_var = ctk.BooleanVar(value=True)
        self.chk_mute = ctk.CTkCheckBox(scroll_config, text="Tắt âm thanh gốc của video", variable=self.mute_var, font=F(12), text_color=T2, state="disabled")
        self.chk_mute.pack(anchor="w", padx=10, pady=5)
        
        self.bgm_var = ctk.BooleanVar(value=False)
        self.chk_bgm = ctk.CTkCheckBox(scroll_config, text="Giữ BGM gốc (Tự ducking)", variable=self.bgm_var, font=F(12), text_color=T2, command=self.save_settings)
        self.chk_bgm.pack(anchor="w", padx=10, pady=5)
        
        self.wm_var = ctk.BooleanVar(value=False)
        self.chk_wm = ctk.CTkCheckBox(scroll_config, text="Đóng dấu bản quyền (Watermark)", variable=self.wm_var, font=F(12), text_color=T2, command=self.save_settings)
        self.chk_wm.pack(anchor="w", padx=10, pady=5)
        
        # ── SUBTITLE STYLE SETTINGS ──
        ctk.CTkLabel(scroll_config, text="🎨 TÙY CHỈNH PHỤ ĐỀ", font=F(13, "bold"), text_color=ORG).pack(anchor="w", padx=10, pady=(15, 5))
        
        # System font selection
        ctk.CTkLabel(scroll_config, text="Font chữ tiếng Việt:", font=F(12), text_color=T2).pack(anchor="w", padx=10, pady=(5, 0))
        self.combo_font = ctk.CTkOptionMenu(scroll_config, values=self.font_names, fg_color=BG3, text_color=T1, command=self.on_change_font)
        self.combo_font.pack(fill="x", padx=10, pady=5)
        self.combo_font.set("Mặc định (BeVietnamPro-Bold)")
        
        # Size scale slider
        size_row = ctk.CTkFrame(scroll_config, fg_color="transparent")
        size_row.pack(fill="x", padx=10, pady=5)
        self.lbl_sub_size = ctk.CTkLabel(size_row, text="Kích cỡ chữ: 1.0x", font=F(12), text_color=T2)
        self.lbl_sub_size.pack(side="left")
        
        self.slider_sub_size = ctk.CTkSlider(scroll_config, from_=0.5, to=3.0, number_of_steps=25, command=self.on_change_sub_size)
        self.slider_sub_size.set(1.0)
        self.slider_sub_size.pack(fill="x", padx=10, pady=2)
        
        # Color chooser
        color_row = ctk.CTkFrame(scroll_config, fg_color="transparent")
        color_row.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(color_row, text="Màu chữ:", font=F(12), text_color=T2).pack(side="left", pady=5)
        
        self.btn_color = ctk.CTkButton(color_row, text="■ Màu Vàng", fg_color=self.sub_color_hex, hover_color="#CCCC00", text_color="black", font=F(11, "bold"), width=120, height=28, command=self.choose_color)
        self.btn_color.pack(side="right")
        
        # Output directory selection
        ctk.CTkLabel(scroll_config, text="Nơi lưu sản phẩm:", font=F(12, "bold"), text_color=T2).pack(anchor="w", padx=10, pady=(15, 0))
        self.lbl_out_dir = ctk.CTkLabel(scroll_config, text="Mặc định: /outputs", text_color=T3, font=F(11))
        self.lbl_out_dir.pack(anchor="w", padx=10, pady=2)
        ctk.CTkButton(scroll_config, text="💾 Chọn Nơi Lưu", fg_color=BG4, text_color=T1, height=28, command=self.choose_output_dir).pack(fill="x", padx=10, pady=5)
        
        # (Main actions moved to sticky bottom action frame)
        
        # 4. BOTTOM LOGS PANEL
        self.logs_panel = ctk.CTkFrame(self, height=140, corner_radius=10, fg_color=BG2)
        self.logs_panel.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.logs_panel.grid_propagate(False)
        
        self.txt_logs = ctk.CTkTextbox(self.logs_panel, text_color="#A3E635", fg_color="#0D1117", font=F(11))
        self.txt_logs.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_logs.configure(state="disabled")
        
        self.selected_item_idx = -1
        self.log("✦ Sẵn sàng! Vui lòng nạp tối thiểu 2 video AI để thực hiện ghép đôi.")
        
    def log(self, message):
        def _append():
            self.txt_logs.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            log_line = f"[{ts}] {message}"
            self.txt_logs.insert("end", log_line + "\n")
            self.txt_logs.see("end")
            self.txt_logs.configure(state="disabled")
            
            # Save logs to a physical log file in modules directory
            try:
                log_file = os.path.join(parent_dir, "ai_video_run.log")
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            except:
                pass
        self.after(0, _append)

    # ── State Persistence (Save/Load settings) ───────────────────
    def save_settings(self):
        settings = {
            "sub_x_ratio": self.sub_x_ratio,
            "sub_y_ratio": self.sub_y_ratio,
            "sub_size_scale": self.sub_size_scale,
            "sub_color_hex": self.sub_color_hex,
            "sub_font_name": self.sub_font_name,
            "voice_name": self.combo_voice.get(),
            "sub_source": self.combo_sub_source.get(),
            "output_dir": self.output_dir,
            "blur_boxes": self.blur_boxes,
            "keep_bgm": self.bgm_var.get(),
            "sub_var": self.sub_var.get(),
            "order_image_path": self.order_image_path,
            "enable_watermark": self.wm_var.get()
        }
        try:
            settings_file = os.path.join(parent_dir, "ai_video_settings.json")
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.log(f"⚠️ Không thể lưu cấu hình chỉnh sửa: {e}")

    def load_settings(self):
        settings_file = os.path.join(parent_dir, "ai_video_settings.json")
        if not os.path.exists(settings_file): return
        
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                s = json.load(f)
            
            self.sub_x_ratio = s.get("sub_x_ratio", 0.5)
            self.sub_y_ratio = s.get("sub_y_ratio", 0.8)
            self.sub_size_scale = s.get("sub_size_scale", 1.0)
            self.sub_color_hex = s.get("sub_color_hex", "#FFFF00")
            
            # Sub font name mapping
            font_path = s.get("sub_font_name", "BeVietnamPro-Bold.ttf")
            font_choice = "Mặc định (BeVietnamPro-Bold)"
            for k, v in self.system_fonts_map.items():
                if v == font_path:
                    font_choice = k
                    break
            self.sub_font_name = font_path
            
            # Update GUI elements
            self.combo_font.set(font_choice)
            self.slider_sub_size.set(self.sub_size_scale)
            self.lbl_sub_size.configure(text=f"Kích cỡ chữ: {self.sub_size_scale:.1f}x")
            
            # Color button configuration
            self.btn_color.configure(fg_color=self.sub_color_hex, text=f"■ {self.sub_color_hex.upper()}")
            h = self.sub_color_hex.lstrip('#')
            rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            luma = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            self.btn_color.configure(text_color="black" if luma > 128 else "white")
            
            # Voice
            voice_name = s.get("voice_name", "Diệu Hương (Nữ HN - News)")
            if voice_name in self.vbee_voices:
                self.combo_voice.set(voice_name)
                
            # Sub source
            sub_src = s.get("sub_source", "Whisper (Trích âm thanh)")
            self.combo_sub_source.set(sub_src)
            
            # Checkboxes
            self.bgm_var.set(s.get("keep_bgm", False))
            self.sub_var.set(s.get("sub_var", True))
            self.wm_var.set(s.get("enable_watermark", False))
            
            # Output dir
            self.output_dir = s.get("output_dir", "")
            if self.output_dir:
                self.lbl_out_dir.configure(text=f"Đầu ra: .../{os.path.basename(self.output_dir)}")
                
            # Blur boxes
            self.blur_boxes = s.get("blur_boxes", [])
            self.redraw_overlays()
            self.update_canvas()
            
            # Load product image path
            self.order_image_path = s.get("order_image_path", None)
            if self.order_image_path and os.path.exists(self.order_image_path):
                self.lbl_order_img.configure(text=os.path.basename(self.order_image_path), text_color=GRN)
            else:
                self.order_image_path = None
                self.lbl_order_img.configure(text="Chưa chọn ảnh đơn hàng", text_color=T3)
                
            self.log("💾 Đã khôi phục cấu hình chỉnh sửa từ phiên làm việc trước.")
        except Exception as e:
            self.log(f"⚠️ Lỗi khôi phục cấu hình: {e}")

    # ── Subtitle Control Events ──────────────────────────────────
    def on_change_font(self, choice):
        path = self.system_fonts_map.get(choice, "BeVietnamPro-Bold.ttf")
        self.sub_font_name = path
        self.log(f"Font chữ phụ đề → {choice}")
        self.update_canvas()
        self.save_settings()
        
    def on_change_sub_size(self, val):
        self.sub_size_scale = round(float(val), 2)
        self.lbl_sub_size.configure(text=f"Kích cỡ chữ: {self.sub_size_scale:.1f}x")
        self.update_canvas()
        self.save_settings()
        
    def choose_color(self):
        color_code = colorchooser.askcolor(color=self.sub_color_hex, title="Chọn màu chữ phụ đề")
        if color_code and color_code[1]:
            self.sub_color_hex = color_code[1]
            self.btn_color.configure(fg_color=self.sub_color_hex)
            
            # Determine contrasting text color for button label
            rgb = color_code[0]
            luma = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            text_color = "black" if luma > 128 else "white"
            
            self.btn_color.configure(text=f"■ {self.sub_color_hex.upper()}", text_color=text_color)
            self.log(f"Màu phụ đề → {self.sub_color_hex}")
            self.update_canvas()
            self.save_settings()
            
    def on_toggle_sub_checkbox(self):
        self.update_canvas()
        self.save_settings()

    def on_change_sub_source(self, choice):
        if choice == "Gemini (Phân tích ảnh đơn hàng)":
            self.log("💡 Chế độ phân tích ảnh đơn hàng đang bật. Vui lòng chọn ảnh đơn hàng.")
        self.save_settings()

    def choose_order_image(self):
        path = filedialog.askopenfilename(title="Chọn Ảnh Đơn Hàng / Sản Phẩm", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.heic *.heif *.PNG *.JPG *.JPEG *.WEBP *.HEIC *.HEIF")])
        if path:
            self.order_image_path = path
            self.lbl_order_img.configure(text=os.path.basename(path), text_color=GRN)
            self.log(f"📸 Đã nạp ảnh đơn hàng: {os.path.basename(path)}")
            self.save_settings()

    def on_click_manual_save(self):
        self.save_settings()
        self.log("💾 Đã lưu toàn bộ cấu hình chỉnh sửa thành công.")
        self.btn_save_config.configure(text="✅ Đã Lưu Thành Công!", fg_color="#28A745", text_color="white")
        self.after(1500, lambda: self.btn_save_config.configure(text="💾 LƯU CẤU HÌNH", fg_color=SEL, text_color=T1))

    # ── Queue Handling ──────────────────────────────────────────
    def load_files(self):
        files = filedialog.askopenfilenames(title="Chọn Các Video Cần Ghép", filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv")])
        if not files: return
        
        for path in files:
            if path not in self.video_paths:
                self.video_paths.append(path)
                
        self.update_queue_ui()
        self.log(f"📥 Đã nạp thêm {len(files)} video vào danh sách.")
        
        # Load preview using the first video
        if self.video_paths and not self.cap:
            self.load_video_preview(self.video_paths[0])
            
    def clear_queue(self):
        self.video_paths.clear()
        self.update_queue_ui()
        self.clear_video_preview()
        self.log("🧹 Đã dọn sạch hàng đợi.")
        
    def update_queue_ui(self):
        # Clear scrollable frame widgets
        for widget in self.scroll_queue.winfo_children():
            widget.destroy()
            
        for idx, path in enumerate(self.video_paths):
            name = os.path.basename(path)
            bg_color = BG4 if idx == self.selected_item_idx else "transparent"
            
            row = ctk.CTkFrame(self.scroll_queue, fg_color=bg_color, corner_radius=4)
            row.pack(fill="x", pady=2, padx=2)
            
            # Select button / label combo
            lbl = ctk.CTkLabel(row, text=f"{idx+1}. {name}", anchor="w", font=F(12))
            lbl.pack(side="left", fill="x", expand=True, padx=5, pady=2)
            
            # Binding click to select item
            def make_select_handler(i=idx, p=path):
                return lambda e: self.select_queue_item(i, p)
            lbl.bind("<Button-1>", make_select_handler())
            row.bind("<Button-1>", make_select_handler())
            
        self.lbl_queue_status.configure(text=f"Đang có {len(self.video_paths)} videos (Ghép được {len(self.video_paths)//2} cặp)")

    def select_queue_item(self, idx, path):
        self.selected_item_idx = idx
        self.update_queue_ui()
        self.load_video_preview(path)
        
    def move_item(self, direction):
        idx = self.selected_item_idx
        if idx == -1: return
        
        new_idx = idx + direction
        if 0 <= new_idx < len(self.video_paths):
            # Swap
            self.video_paths[idx], self.video_paths[new_idx] = self.video_paths[new_idx], self.video_paths[idx]
            self.selected_item_idx = new_idx
            self.update_queue_ui()
            
    def delete_selected(self):
        idx = self.selected_item_idx
        if idx == -1: return
        
        path = self.video_paths.pop(idx)
        self.selected_item_idx = -1
        self.update_queue_ui()
        self.log(f"✕ Đã xóa video: {os.path.basename(path)}")
        if self.video_paths:
            self.load_video_preview(self.video_paths[0])
        else:
            self.clear_video_preview()

    # ── Canvas Preview & Drawing ────────────────────────────────
    def load_video_preview(self, path):
        if self.cap:
            self.cap.release()
            
        self.cap = cv2.VideoCapture(path)
        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.raw_preview_img = Image.fromarray(frame)
            self.update_canvas()
            
    def clear_video_preview(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        self.canvas.delete("all")
        if hasattr(self, 'raw_preview_img'):
            del self.raw_preview_img
            
    def update_canvas(self):
        if not hasattr(self, 'raw_preview_img'): return
        
        self.update_idletasks()
        cw = self.canvas_frame.winfo_width() - 10
        ch = self.canvas_frame.winfo_height() - 10
        if cw <= 0 or ch <= 0:
            cw, ch = 540, 960 # Default aspect ratio vertical
            
        img_w, img_h = self.raw_preview_img.size
        scale_w = cw / img_w
        scale_h = ch / img_h
        self.canvas_scale = min(scale_w, scale_h)
        
        new_w = int(img_w * self.canvas_scale)
        new_h = int(img_h * self.canvas_scale)
        
        self.canvas.config(width=new_w, height=new_h)
        
        # 1. Create a copy of the original preview image to draw custom text on
        img_draw = self.raw_preview_img.copy()
        
        # 2. Render subtitle text preview if enabled (direct Pillow drawing for realtime custom font preview)
        if self.sub_var.get():
            draw = ImageDraw.Draw(img_draw)
            
            # Determine size based on image dimensions
            is_vertical = img_h > img_w
            if is_vertical:
                base_font_size = max(28, int(img_w * 0.045))
                font_size = int(base_font_size * self.sub_size_scale)
            else:
                base_font_size = max(32, int(img_h * 0.055))
                font_size = int(base_font_size * self.sub_size_scale)
                
            try:
                # Load custom font (using self.sub_font_name absolute path)
                font_path = self.sub_font_name
                if not os.path.isabs(font_path) and not os.path.exists(font_path):
                    font_path = os.path.join(cfg.ASSETS_DIR, font_path)
                font = ImageFont.truetype(font_path, font_size)
            except Exception:
                try:
                    font = ImageFont.truetype(os.path.join(cfg.ASSETS_DIR, "BeVietnamPro-Bold.ttf"), font_size)
                except:
                    font = ImageFont.load_default()
                    
            # Parse color
            color = self.sub_color_hex
            if isinstance(color, str) and color.startswith("#"):
                try:
                    h = color.lstrip('#')
                    color = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                except:
                    color = (255, 255, 0)
                    
            demo_text = "Phụ đề kéo thả ở đây (Demo)"
            
            # Get text size
            try:
                bbox = draw.textbbox((0, 0), demo_text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except:
                text_w = font_size * len(demo_text) * 0.5
                text_h = font_size
                
            # Align text based on coordinates ratios
            tx = int(img_w * self.sub_x_ratio - text_w / 2)
            ty = int(img_h * self.sub_y_ratio - text_h / 2)
            
            # Draw outline
            stroke_width = max(2, int(font_size * 0.05))
            for ox in range(-stroke_width, stroke_width + 1):
                for oy in range(-stroke_width, stroke_width + 1):
                    if ox != 0 or oy != 0:
                        draw.text((tx + ox, ty + oy), demo_text, font=font, fill=(0,0,0))
                        
            # Draw fill
            draw.text((tx, ty), demo_text, font=font, fill=color)
            
        # 3. Resize and set as background
        resized_img = img_draw.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        self.preview_image = ImageTk.PhotoImage(resized_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_image, tags="bg")
        self.redraw_overlays()
        
    def redraw_overlays(self):
        self.canvas.delete("overlay")
        
        # Draw blur boxes
        for (x1, y1, x2, y2) in self.blur_boxes:
            cx1, cy1 = x1 * self.canvas_scale, y1 * self.canvas_scale
            cx2, cy2 = x2 * self.canvas_scale, y2 * self.canvas_scale
            self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="red", width=3, stipple="gray25", fill="red", tags="overlay")
            
    def toggle_blur_tool(self):
        if self.current_tool == "blur":
            self.current_tool = "none"
            self.btn_blur_tool.configure(fg_color=BG4)
        else:
            self.current_tool = "blur"
            self.btn_blur_tool.configure(fg_color=SEL)
            
    def clear_blurs(self):
        self.blur_boxes.clear()
        self.redraw_overlays()
        self.log("🧹 Đã xoá toàn bộ vùng làm mờ.")
        self.save_settings()
        
    def on_press(self, event):
        if not self.cap: return
        self.start_x = event.x
        self.start_y = event.y
        
        # Check if click is close to the Subtitle preview text
        if self.sub_var.get():
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw > 0 and ch > 0:
                cx = cw * self.sub_x_ratio
                cy = ch * self.sub_y_ratio
                # If clicked within bounding box of subtitle
                if abs(event.x - cx) < 140 and abs(event.y - cy) < 25:
                    self.dragging_sub = True
                    self.canvas.config(cursor="fleur")
                    return
        
        if self.current_tool == "blur":
            self.temp_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2, tags="overlay")
            
    def on_drag(self, event):
        if not self.cap: return
        
        if self.dragging_sub:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw > 0 and ch > 0:
                # Update subtitle ratios and update canvas immediately
                self.sub_x_ratio = max(0.05, min(0.95, event.x / cw))
                self.sub_y_ratio = max(0.05, min(0.95, event.y / ch))
                self.update_canvas()
            return
            
        if self.current_tool == "blur" and self.temp_rect:
            self.canvas.coords(self.temp_rect, self.start_x, self.start_y, event.x, event.y)
            
    def on_release(self, event):
        if not self.cap: return
        
        if self.dragging_sub:
            self.dragging_sub = False
            self.canvas.config(cursor="crosshair")
            self.log(f"📍 Đã dịch chuyển phụ đề đến vị trí: X={self.sub_x_ratio:.2f}, Y={self.sub_y_ratio:.2f}")
            self.save_settings()
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
                self.log(f"➕ Thêm vùng Blur: ({rx1}, {ry1}) đến ({rx2}, {ry2})")
                self.save_settings()
                
            self.canvas.delete(self.temp_rect)
            self.temp_rect = None
            self.redraw_overlays()

    # ── Pipeline Execution ──────────────────────────────────────
    def choose_output_dir(self):
        d = filedialog.askdirectory(title="Chọn Thư Mục Đầu Ra")
        if d:
            self.output_dir = d
            self.lbl_out_dir.configure(text=f"Đầu ra: .../{os.path.basename(d)}")
            self.log(f"💾 Thay đổi thư mục lưu: {d}")
            self.save_settings()
            
    def start_processing(self):
        if self.is_running: return
        if len(self.video_paths) < 2:
            messagebox.showwarning("Cảnh Báo", "Vui lòng chọn tối thiểu 2 video để ghép cặp!")
            return
            
        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", fg_color="#94A3B8")
        self.btn_stop.configure(state="normal")
        
        # Save settings for the main thread
        voice_sel = self.combo_voice.get()
        vbee_voice_code = self.vbee_voices.get(voice_sel, "vbee:hn_female_ngochuyen_full_48k-fhg")
        
        # Configure global config for the pipeline
        cfg.VBEE_VOICE = vbee_voice_code
        cfg.save_settings({"vbee_voice": vbee_voice_code})
        
        sub_source_map = {
            "Whisper (Trích âm thanh)": "audio",
            "OCR (Quét chữ màn hình)": "ocr",
            "Gemini (Mắt thần tự viết)": "vision",
            "Gemini (Phân tích ảnh đơn hàng)": "image"
        }
        sub_src = sub_source_map.get(self.combo_sub_source.get(), "audio")
        
        if sub_src == "image" and (not self.order_image_path or not os.path.exists(self.order_image_path)):
            messagebox.showwarning("Cảnh Báo", "Vui lòng chọn ảnh đơn hàng/sản phẩm hợp lệ trước khi bắt đầu!")
            self.is_running = False
            self._reset_ui()
            return
            
        threading.Thread(target=self.worker, args=(vbee_voice_code, sub_src), daemon=True).start()
        
    def stop_processing(self):
        if self.is_running:
            self.stop_event.set()
            self.btn_stop.configure(state="disabled", text="ĐANG HUỶ...")
            self.log("🛑 Đang huỷ tiến trình ghép cặp...")
            
    def worker(self, voice_code, sub_src):
        # Apply custom style parameters directly to configuration
        cfg.SUB_Y_POS_DOC = self.sub_y_ratio
        cfg.SUB_Y_POS_NGANG = self.sub_y_ratio
        cfg.FONT_SIZE_SCALE_DOC = self.sub_size_scale
        cfg.FONT_SIZE_SCALE_NGANG = self.sub_size_scale
        cfg.SUB_COLOR = self.sub_color_hex
        cfg.FONT_NAME = self.sub_font_name
        cfg.SUB_X_POS_DOC = self.sub_x_ratio
        cfg.SUB_X_POS_NGANG = self.sub_x_ratio

        # Determine files and pairs
        files = list(self.video_paths)
        num_pairs = len(files) // 2
        
        self.log(f"🚀 Bắt đầu quá trình ghép {num_pairs} cặp video...")
        
        out_folder = self.output_dir if self.output_dir else getattr(cfg, "OUTPUT_DIR", "outputs")
        os.makedirs(out_folder, exist_ok=True)
        
        temp_dir = getattr(cfg, "TEMP_DIR", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        codec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
        preset_args = [] if codec == "h264_videotoolbox" else ["-preset", "ultrafast"]
        
        success_count = 0
        
        for i in range(num_pairs):
            if self.stop_event.is_set():
                break
                
            path1 = files[2 * i]
            path2 = files[2 * i + 1]
            
            name1 = os.path.splitext(os.path.basename(path1))[0]
            name2 = os.path.splitext(os.path.basename(path2))[0]
            
            from automation.utils.sync_and_sub import generate_natural_filename
            output_name, final_output_path = generate_natural_filename(out_folder)
            
            self.log(f"\n🎬 [Cặp {i+1}/{num_pairs}] Ghép: {name1} 🔗 {name2}")
            
            # Step 1: Concatenate A + B using FFmpeg (transcoding + scale to uniform vertical layout)
            temp_concat_video = os.path.join(temp_dir, f"temp_pair_concat_{i}.mp4")
            if os.path.exists(temp_concat_video):
                try: os.remove(temp_concat_video)
                except: pass
                
            dur1 = get_video_duration(path1)
            dur2 = get_video_duration(path2)
            has_a1 = has_audio_stream(path1)
            has_a2 = has_audio_stream(path2)
            
            # Assemble audio sources: if missing, synthesize silence of video duration
            if has_a1:
                a0_filter = "[0:a]anull[a0_filt]"
            else:
                a0_filter = f"[2:a]atrim=0:{dur1:.3f},asetpts=PTS[a0_filt]"
                
            if has_a2:
                a1_filter = "[1:a]anull[a1_filt]"
            else:
                a1_filter = f"[2:a]atrim=0:{dur2:.3f},asetpts=PTS[a1_filt]"
            
            filter_complex = (
                f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(1080-iw)/2:(1920-ih)/2,setsar=1[v0]; "
                f"[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(1080-iw)/2:(1920-ih)/2,setsar=1[v1]; "
                f"{a0_filter}; "
                f"{a1_filter}; "
                f"[v0][v1]concat=n=2:v=1:a=0[v]; "
                f"[a0_filt][a1_filt]concat=n=2:v=0:a=1[a]"
            )
            
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", path1, "-i", path2,
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "[a]",
                "-c:v", codec
            ] + preset_args + [
                "-c:a", "aac",
                temp_concat_video
            ]
            
            self.log(f"   ↳ Đang nối video gốc thành tập tạm...")
            try:
                res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if res.returncode != 0 or not os.path.exists(temp_concat_video):
                    err_msg = res.stderr.strip().split("\n")[-3:] if res.stderr else ["No error output"]
                    self.log(f"   ❌ Lỗi ghép nối video: FFmpeg trả về mã lỗi {res.returncode} - {' | '.join(err_msg)}")
                    continue
            except Exception as e:
                self.log(f"   ❌ Lỗi nối file: {e}")
                continue
                
            # Step 2: Run pipeline (transcription, tts, subtitles, manual blur)
            self.log(f"   ↳ Đang tạo phụ đề, voice Vbee và áp dụng Blur...")
            
            # Map manual blur boxes from preview coordinate system to 1080x1920
            mapped_blur_boxes = []
            if self.blur_boxes:
                w1, h1 = self.video_width, self.video_height
                scale = min(1080 / w1, 1920 / h1)
                new_w = w1 * scale
                new_h = h1 * scale
                pad_x = (1080 - new_w) / 2
                pad_y = (1920 - new_h) / 2
                
                for (x1, y1, x2, y2) in self.blur_boxes:
                    bx1 = int(x1 * scale + pad_x)
                    by1 = int(y1 * scale + pad_y)
                    bx2 = int(x2 * scale + pad_x)
                    by2 = int(y2 * scale + pad_y)
                    mapped_blur_boxes.append([bx1, by1, bx2, by2])
            
            # Configure backup target language to Vietnamese
            cfg.TARGET_LANGUAGE = "Tiếng Việt"
            
            # Run pipeline
            try:
                # Override the default output path temporarily to final_output_path
                old_output_dir = cfg.OUTPUT_DIR
                cfg.OUTPUT_DIR = out_folder
                
                # Make sure to set add_voice to True, keep_bgm to the checkbox value, enable_blur to True.
                process_video_pipeline(
                    temp_concat_video,
                    progress_callback=None,
                    use_hw_accel=(platform.system() == "Darwin"),
                    add_sub=self.sub_var.get(),
                    add_voice=True,
                    sub_source=sub_src,
                    keep_bgm=self.bgm_var.get(),
                    processing_mode="Bình Thường (Tự Động 100%)",
                    enable_blur=True,
                    manual_blur_boxes=mapped_blur_boxes,
                    order_image_path=self.order_image_path,
                    enable_watermark=self.wm_var.get(),
                    is_ai_video_pair=True,
                    output_filename=f"vietsub_temp_pair_concat_{i}.mp4"
                )
                
                # The output file is written to outputs/vietsub_temp_pair_concat_i.mp4
                generated_output = os.path.join(out_folder, f"vietsub_temp_pair_concat_{i}.mp4")
                if os.path.exists(generated_output):
                    # Move to the final output file name
                    if os.path.exists(final_output_path):
                        os.remove(final_output_path)
                    os.rename(generated_output, final_output_path)
                    self.log(f"   ✅ HOÀN THÀNH: {output_name}")
                    success_count += 1
                else:
                    self.log(f"   ❌ Lỗi: Không thấy file output vietsub từ pipeline")
                    
                cfg.OUTPUT_DIR = old_output_dir
            except Exception as e:
                self.log(f"   ❌ Lỗi pipeline: {e}")
                
            # Clean up concat temp file
            if os.path.exists(temp_concat_video):
                try: os.remove(temp_concat_video)
                except: pass
                
        self.log(f"\n🎉 HOÀN THÀNH! Ghép thành công {success_count}/{num_pairs} cặp video.")
        self.is_running = False
        self.after(0, self._reset_ui)
        
    def _reset_ui(self):
        self.btn_start.configure(state="normal", fg_color=GRN)
        self.btn_stop.configure(state="disabled", text="🛑 Dừng Lại")

    def play_test_voice(self):
        if not hasattr(self, 'combo_voice') or not self.combo_voice: return
        voice_sel = self.combo_voice.get()
        code = self.vbee_voices.get(voice_sel, "vbee:hn_female_ngochuyen_full_48k-fhg")
        
        if "random" in code.lower():
            import random
            vbee_pool = [
                "hn_female_ngochuyen_full_48k-fhg",
                "hn_female_maiphuong_ngam_48k-fhg",
                "hn_female_thaotrinh_full_48k-fhg",
                "sg_female_huonggiang_full_48k-fhg",
                "sg_male_minhhoang_full_48k-fhg",
                "hn_male_minhquan_yt-stable",
                "hn_male_phuthang_news65dt_44k-fhg",
                "hue_male_duyphuong_full_48k-fhg",
                "n_hanoi_female_dieuhuong20260421111346189_news_vc",
                "n_tuyenquang_female_vuthilanhuong_advertise_vc",
                "n_hanoi_female_ngocanhdangg_book_vc",
                "n_hanoi_male_namnhenhangamap_story_vc",
                "n_hanoi_male_sizonguyen_education_vc",
                "n_hanoi_male_nhabaohoangnam_news_vc"
            ]
            code = f"vbee:{random.choice(vbee_pool)}"
            self.log(f"🎲 Thử giọng ngẫu nhiên với: {code}")

        if self.btn_test_voice: self.btn_test_voice.configure(state="disabled", text="⏳")
        
        import threading
        import platform
        import os
        
        def _t():
            try:
                from automation.utils.vbee_tts import test_vbee_voice
                ap = test_vbee_voice(code)
                if ap and os.path.exists(ap):
                    if platform.system() == "Darwin":
                        os.system(f"afplay '{ap}'")
            except Exception as e:
                self.log(f"❌ Lỗi thử giọng: {e}")
            finally:
                if self.btn_test_voice:
                    self.after(0, lambda: self.btn_test_voice.configure(state="normal", text="▶ Nghe Thử"))
                    
        threading.Thread(target=_t, daemon=True).start()
