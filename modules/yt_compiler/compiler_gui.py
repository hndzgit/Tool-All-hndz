import os
import cv2
import threading
import time
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFont

from yt_compiler.render_engine import compile_videos_batch

# Theme Colors
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

def F(size=12, weight="normal"):
    return ctk.CTkFont(family="Arial", size=size, weight=weight)

class YoutubeCompilerApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        # Asset Paths (Relative to modules directory)
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ROBOTO_FONT = os.path.join(current_dir, "automation", "assets", "Roboto-Bold.ttf")
        self.BE_VIETNAM_FONT = os.path.join(current_dir, "automation", "assets", "BeVietnamPro-Bold.ttf")

        self.FONTS = {
            "Roboto Bold": self.ROBOTO_FONT if os.path.exists(self.ROBOTO_FONT) else "/System/Library/Fonts/Helvetica.ttc",
            "Be Vietnam Pro": self.BE_VIETNAM_FONT if os.path.exists(self.BE_VIETNAM_FONT) else "/System/Library/Fonts/Helvetica.ttc",
            "Arial / Standard": "/System/Library/Fonts/Helvetica.ttc"
        }

        # Program State
        self.video_paths = []
        self.output_dir = ""
        self.intro_path = None
        self.outro_path = None
        self.bgm_path = None
        self.silent_bgm_path = None
        self.dyn_bg_path = None
        self.custom_bg_path = None
        self.solid_color_hex = "#000000"
        
        # Thumbnail Settings & Preview Locks
        self.thumbnail_border_color = "Cam (#FE640B)"
        self.thumbnail_text_color = "Vàng (#FFFF00)"
        self.thumbnail_banner_color = "Trắng (#FFFFFF)"
        self.thumbnail_font_size = 44
        self.thumbnail_frame_offsets = [15.0, 33.0, 85.0]
        self.custom_thumbnail_path = None
        self.preview_thread_lock = threading.Lock()
        
        self.layers = [] # List of dict overlays (texts/watermarks)
        self.selected_layer_idx = None
        self.bg_image_pil = None # PIL Image for preview frame background
        self.tk_bg_image = None # PhotoImage cache

        # Threading/Progress states
        self.is_compiling = False
        self.stop_event = threading.Event()

        # Drag and Drop states
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # Canvas settings (16:9 ratio)
        self.canvas_w = 640
        self.canvas_h = 360
        self.scale = self.canvas_w / 1920.0 # Canvas scale multiplier (relative to 1920x1080)

        # Build GUI Panels
        self.grid_columnconfigure(0, weight=0) # Left Panel (Controls)
        self.grid_columnconfigure(1, weight=1) # Middle Panel (Preview)
        self.grid_columnconfigure(2, weight=0) # Right Panel (Layers)
        self.grid_rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_middle_panel()
        self._build_right_panel()

        # Select default frame background representation
        self.redraw_canvas()

        # Load saved settings and template
        self.load_settings()

    def _build_left_panel(self):
        self.left_panel = ctk.CTkScrollableFrame(self, width=320, corner_radius=10, fg_color=BG2, scrollbar_button_color=BG4)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(self.left_panel, text="🎥 GHÉP & EDIT VIDEO YT", font=F(16, "bold"), text_color=ORG).pack(pady=(20, 10))

        # --- VIDEO INPUTS ---
        f_in = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_in.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_in, text="1. Đầu Vào Video Con", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        self.btn_load_dir = ctk.CTkButton(f_in, text="📂 Chọn Thư Mục", command=self.choose_input_dir, fg_color=BG4, text_color=T1)
        self.btn_load_dir.pack(fill="x", padx=10, pady=4)

        self.btn_load_files = ctk.CTkButton(f_in, text="🎞 Chọn File Tùy Chọn", command=self.choose_input_files, fg_color=BG4, text_color=T1)
        self.btn_load_files.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_loaded = ctk.CTkLabel(f_in, text="Chưa nạp video", font=F(11), text_color=T3)
        self.lbl_loaded.pack(pady=(0, 5))

        # --- INTRO & OUTRO ---
        f_io = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        # f_io.pack(fill="x", padx=10, pady=5) # Removed by user request
        ctk.CTkLabel(f_io, text="Intro / Outro (Tùy chọn)", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        # Intro
        f_intro = ctk.CTkFrame(f_io, fg_color="transparent")
        f_intro.pack(fill="x", padx=5, pady=2)
        self.btn_intro = ctk.CTkButton(f_intro, text="🎬 Intro", command=self.choose_intro, width=70, height=24, font=F(11), fg_color=BG4)
        self.btn_intro.pack(side="left")
        self.lbl_intro = ctk.CTkLabel(f_intro, text="Chưa chọn", font=F(10), text_color=T3, anchor="w")
        self.lbl_intro.pack(side="left", padx=5, fill="x", expand=True)

        # Outro
        f_outro = ctk.CTkFrame(f_io, fg_color="transparent")
        f_outro.pack(fill="x", padx=5, pady=2)
        self.btn_outro = ctk.CTkButton(f_outro, text="🎬 Outro", command=self.choose_outro, width=70, height=24, font=F(11), fg_color=BG4)
        self.btn_outro.pack(side="left")
        self.lbl_outro = ctk.CTkLabel(f_outro, text="Chưa chọn", font=F(10), text_color=T3, anchor="w")
        self.lbl_outro.pack(side="left", padx=5, fill="x", expand=True)

        # --- VIDEO OUTPUT ---
        f_out = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_out.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_out, text="2. Thư Mục Xuất Bản", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        self.btn_out = ctk.CTkButton(f_out, text="💾 Chọn Nơi Lưu", command=self.choose_output_dir, fg_color=SEL, text_color=BG)
        self.btn_out.pack(fill="x", padx=10, pady=(0, 5))

        self.lbl_out_dir = ctk.CTkLabel(f_out, text="Mặc định: outputs/YouTube", font=F(11), text_color=T3)
        self.lbl_out_dir.pack(pady=(0, 5))

        # --- BGM & BACKGROUND STYLING ---
        f_bgm = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_bgm.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_bgm, text="Nhạc Nền & Cấu Hình Nền", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        # Background Style
        f_bg_style = ctk.CTkFrame(f_bgm, fg_color="transparent")
        f_bg_style.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(f_bg_style, text="Nền video dọc:", font=F(11), text_color=T2).pack(side="left")
        self.combo_bg_style = ctk.CTkComboBox(
            f_bg_style, 
            values=["Nền mờ (Blurred)", "Nền màu đơn sắc", "Nền ảnh/video tùy chọn"], 
            width=130, height=24, font=F(11),
            command=self.on_bg_style_changed
        )
        self.combo_bg_style.set("Nền mờ (Blurred)")
        self.combo_bg_style.pack(side="right")

        # Target Resolution Selector
        f_res = ctk.CTkFrame(f_bgm, fg_color="transparent")
        f_res.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(f_res, text="Độ phân giải:", font=F(11), text_color=T2).pack(side="left")
        self.combo_res = ctk.CTkComboBox(
            f_res, 
            values=["1280x720 (720p - Siêu nhanh)", "1920x1080 (1080p - Cực nét)"], 
            width=130, height=24, font=F(11)
        )
        self.combo_res.set("1280x720 (720p - Siêu nhanh)")
        self.combo_res.pack(side="right")

        # Color picker frame (initially hidden)
        self.f_solid_color = ctk.CTkFrame(f_bgm, fg_color="transparent")
        ctk.CTkLabel(self.f_solid_color, text="Màu nền đơn sắc:", font=F(11), text_color=T2).pack(side="left")
        self.btn_solid_color = ctk.CTkButton(
            self.f_solid_color, 
            text="Chọn màu", 
            fg_color=self.solid_color_hex, 
            text_color="white", 
            width=80, height=24, 
            command=self.choose_solid_color
        )
        self.btn_solid_color.pack(side="right")

        # Custom background file picker (initially hidden)
        self.f_custom_bg = ctk.CTkFrame(f_bgm, fg_color="transparent")
        self.btn_custom_bg = ctk.CTkButton(
            self.f_custom_bg, 
            text="Chọn tệp nền", 
            fg_color=BG4, 
            text_color=T1, 
            width=80, height=24, 
            command=self.choose_custom_bg
        )
        self.btn_custom_bg.pack(side="left")
        self.lbl_custom_bg = ctk.CTkLabel(self.f_custom_bg, text="Chưa chọn", font=F(10), text_color=T3, anchor="w")
        self.lbl_custom_bg.pack(side="left", padx=5, fill="x", expand=True)

        # BGM select
        f_bgm_file = ctk.CTkFrame(f_bgm, fg_color="transparent")
        f_bgm_file.pack(fill="x", padx=5, pady=2)
        self.btn_bgm = ctk.CTkButton(f_bgm_file, text="🎵 Nhạc nền", command=self.choose_bgm, width=70, height=24, font=F(11), fg_color=BG4)
        self.btn_bgm.pack(side="left")
        self.lbl_bgm = ctk.CTkLabel(f_bgm_file, text="Chưa chọn", font=F(10), text_color=T3, anchor="w")
        self.lbl_bgm.pack(side="left", padx=5, fill="x", expand=True)

        # Silent BGM fallback select
        f_silent_file = ctk.CTkFrame(f_bgm, fg_color="transparent")
        f_silent_file.pack(fill="x", padx=5, pady=2)
        self.btn_silent_bgm = ctk.CTkButton(f_silent_file, text="🔇 Nhạc clip câm", command=self.choose_silent_bgm, width=95, height=24, font=F(11), fg_color=BG4)
        self.btn_silent_bgm.pack(side="left")
        self.lbl_silent_bgm = ctk.CTkLabel(f_silent_file, text="Chưa chọn", font=F(10), text_color=T3, anchor="w")
        self.lbl_silent_bgm.pack(side="left", padx=5, fill="x", expand=True)

        # BGM volume slider
        self.f_bgm_vol = ctk.CTkFrame(f_bgm, fg_color="transparent")
        self.f_bgm_vol.pack(fill="x", padx=5, pady=2)
        self.lbl_bgm_vol = ctk.CTkLabel(self.f_bgm_vol, text="Âm lượng nhạc: 15%", font=F(11), text_color=T2)
        self.lbl_bgm_vol.pack(side="left")
        self.slider_bgm_vol = ctk.CTkSlider(self.f_bgm_vol, from_=0.0, to=1.0, width=110, height=16)
        self.slider_bgm_vol.set(0.15)
        self.slider_bgm_vol.pack(side="right")
        self.slider_bgm_vol.configure(command=self.on_bgm_vol_changed)

        # Audio Normalization checkbox
        self.norm_audio_var = ctk.BooleanVar(value=False)
        self.chk_norm_audio = ctk.CTkCheckBox(f_bgm, text="Cân bằng âm lượng (Normalize)", variable=self.norm_audio_var, font=F(11), text_color=T2)
        self.chk_norm_audio.pack(padx=10, pady=4, anchor="w")

        # BGM laundering bypass checkbox
        self.bypass_bgm_copyright_var = ctk.BooleanVar(value=True)
        self.chk_bypass_bgm = ctk.CTkCheckBox(f_bgm, text="Tẩy nhạc lách bản quyền BGM", variable=self.bypass_bgm_copyright_var, font=F(11), text_color=T2)
        self.chk_bypass_bgm.pack(padx=10, pady=(2, 6), anchor="w")

        # --- DURATION & CONFIGS ---
        f_cfg = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_cfg.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_cfg, text="4. Thời Lượng & Chế Độ", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        # Min / Max Durations in minutes
        f_dur = ctk.CTkFrame(f_cfg, fg_color="transparent")
        f_dur.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(f_dur, text="Thời lượng (Phút):", font=F(11), text_color=T2).pack(side="left")
        
        self.spin_min = ctk.CTkEntry(f_dur, width=45, height=22, font=F(11), justify="center")
        self.spin_min.insert(0, "8")
        self.spin_min.pack(side="left", padx=5)
        
        ctk.CTkLabel(f_dur, text="đến", font=F(11), text_color=T2).pack(side="left")
        
        self.spin_max = ctk.CTkEntry(f_dur, width=45, height=22, font=F(11), justify="center")
        self.spin_max.insert(0, "10")
        self.spin_max.pack(side="left", padx=5)

        # Shuffle mode
        self.shuffle_var = ctk.BooleanVar(value=False)
        self.chk_shuffle = ctk.CTkCheckBox(f_cfg, text="Trộn ngẫu nhiên clip con", variable=self.shuffle_var, font=F(11), text_color=T2)
        self.chk_shuffle.pack(padx=10, pady=5, anchor="w")

        # Save config button
        self.btn_save_cfg = ctk.CTkButton(
            f_cfg, 
            text="💾 LƯU CẤU HÌNH & TEMPLATE", 
            command=self.save_settings, 
            fg_color=BG4, 
            text_color=T1, 
            height=28
        )
        self.btn_save_cfg.pack(fill="x", padx=10, pady=(5, 10))

        # --- THUMBNAIL AUTO-GENERATION ---
        f_thumb = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_thumb.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_thumb, text="5. Tự Động Tạo Ảnh Bìa", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        self.auto_thumb_var = ctk.BooleanVar(value=True)
        self.chk_auto_thumb = ctk.CTkCheckBox(f_thumb, text="Tự tạo ảnh bìa ghép 3 ô", variable=self.auto_thumb_var, font=F(11), text_color=T2)
        self.chk_auto_thumb.pack(padx=10, pady=5, anchor="w")

        self.btn_configure_thumb = ctk.CTkButton(
            f_thumb, 
            text="🎨 Cấu hình & Xem trước", 
            command=self.open_thumbnail_dialog, 
            fg_color=BG4, 
            text_color=T1, 
            font=F(11, "bold"), 
            height=28
        )
        self.btn_configure_thumb.pack(fill="x", padx=10, pady=(2, 8))

        # Created in memory (unpacked) to preserve load/save compatibility
        self.entry_thumb_temp = ctk.CTkEntry(self, font=F(11))
        self.entry_thumb_temp.insert(0, "Tổng Hợp | MukbangChinaFood | Phần {index}")
        self.entry_thumb_start_idx = ctk.CTkEntry(self, font=F(11))
        self.entry_thumb_start_idx.insert(0, "1")

        # --- ADVANCED VIDEO EFFECTS (SPEED, VOICE, DYNAMIC BG) ---
        f_adv = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8)
        f_adv.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_adv, text="6. Tốc Độ, Giọng Nói & Nền Động", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        # Speed selector
        f_speed = ctk.CTkFrame(f_adv, fg_color="transparent")
        f_speed.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(f_speed, text="Tốc độ video:", font=F(11), text_color=T2).pack(side="left")
        self.combo_speed = ctk.CTkComboBox(f_speed, values=["x1.0", "x1.25", "x1.5", "x2.0", "x2.5", "x3.0"], width=90, height=22, font=F(11))
        self.combo_speed.set("x1.0")
        self.combo_speed.pack(side="right")

        # Voice changer
        f_voice = ctk.CTkFrame(f_adv, fg_color="transparent")
        f_voice.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(f_voice, text="Hiệu ứng giọng:", font=F(11), text_color=T2).pack(side="left")
        self.combo_voice = ctk.CTkComboBox(f_voice, values=["Bình thường", "Giọng Chipmunk", "Giọng Trầm/Robot", "Rung giọng", "Méo tiếng"], width=130, height=22, font=F(11))
        self.combo_voice.set("Bình thường")
        self.combo_voice.pack(side="right")

        # Dynamic background video
        f_dyn_bg = ctk.CTkFrame(f_adv, fg_color="transparent")
        f_dyn_bg.pack(fill="x", padx=10, pady=(2, 8))
        self.btn_dyn_bg = ctk.CTkButton(f_dyn_bg, text="🎬 Nền động", command=self.choose_dyn_bg, width=75, height=22, font=F(10), fg_color=BG4)
        self.btn_dyn_bg.pack(side="left")
        self.lbl_dyn_bg = ctk.CTkLabel(f_dyn_bg, text="Chưa chọn", font=F(10), text_color=T3, anchor="w")
        self.lbl_dyn_bg.pack(side="left", padx=5, fill="x", expand=True)

        # --- ACTIONS ---
        self.btn_compile = ctk.CTkButton(self.left_panel, text="🚀 GHÉP & XUẤT HÀNG LOẠT", command=self.start_compilation, fg_color=GRN, text_color=BG, font=F(14, "bold"), height=40)
        self.btn_compile.pack(fill="x", padx=10, pady=10)

        self.btn_stop = ctk.CTkButton(self.left_panel, text="🛑 DỪNG", command=self.stop_compilation, fg_color=RED, text_color=BG, font=F(14, "bold"), height=40, state="disabled")
        self.btn_stop.pack(fill="x", padx=10, pady=(0, 10))

        # --- LOGS & PROGRESS ---
        self.progress_bar = ctk.CTkProgressBar(self.left_panel, width=280)
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=10, pady=5)

        self.lbl_status = ctk.CTkLabel(self.left_panel, text="Sẵn sàng", font=F(11), text_color=ORG)
        self.lbl_status.pack(pady=2)

        self.log_box = ctk.CTkTextbox(self.left_panel, height=120, font=F(10), fg_color="#0D1117", text_color="#A3E635")
        self.log_box.pack(fill="x", padx=10, pady=(5, 20))
        self.log_box.configure(state="disabled")

    def _build_middle_panel(self):
        self.middle_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.middle_panel.grid(row=0, column=1, sticky="nsew", padx=10)

        ctk.CTkLabel(self.middle_panel, text="MÀN HÌNH PREVIEW (KÉO THẢ OVERLAYS)", font=F(14, "bold"), text_color=T3).pack(pady=(15, 5))

        # Preview background selection combobox
        f_preview_select = ctk.CTkFrame(self.middle_panel, fg_color="transparent")
        f_preview_select.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f_preview_select, text="Hình nền Preview:", font=F(11), text_color=T2).pack(side="left")
        self.combo_preview_bg = ctk.CTkOptionMenu(
            f_preview_select,
            values=["Khung lưới mặc định"],
            command=self.on_preview_bg_changed,
            width=220,
            height=24,
            font=F(11)
        )
        self.combo_preview_bg.pack(side="left", padx=10)

        # Canvas Frame to keep 16:9 ratio
        self.canvas_frame = ctk.CTkFrame(self.middle_panel, fg_color="black", border_width=1, border_color=BG4)
        self.canvas_frame.pack(expand=True, fill="both", padx=20, pady=10)

        # Main Tkinter canvas for preview & interaction
        self.canvas = tk.Canvas(
            self.canvas_frame,
            bg="#11111B",
            width=self.canvas_w,
            height=self.canvas_h,
            highlightthickness=0,
            cursor="hand2"
        )
        self.canvas.pack(expand=True)

        # Bind Mouse Interactions for drag and drop
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)

        # Overlay Guidelines Indicator text
        self.lbl_tip = ctk.CTkLabel(
            self.middle_panel,
            text="💡 Mẹo: Nhấp và Kéo thả để di chuyển chữ/watermark. Nhấp đúp vào Chữ để chỉnh sửa văn bản.",
            font=F(11),
            text_color=T2
        )
        self.lbl_tip.pack(pady=(0, 10))

    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(self, width=280, fg_color=BG2, corner_radius=10)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self.right_panel.grid_propagate(False)

        ctk.CTkLabel(self.right_panel, text="📑 DANH SÁCH LAYER", font=F(14, "bold"), text_color=T3).pack(pady=(15, 5))

        # Row 1: Thêm Chữ & Thêm Watermark
        f_add1 = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        f_add1.pack(fill="x", padx=10, pady=2)

        self.btn_add_text = ctk.CTkButton(f_add1, text="[+] Thêm Chữ", command=self.add_text_layer, fg_color=PUR, text_color=BG, width=120)
        self.btn_add_text.pack(side="left", padx=(0, 2), fill="x", expand=True)

        self.btn_add_wm = ctk.CTkButton(f_add1, text="[+] Thêm Watermark", command=self.add_watermark_layer, fg_color=BG4, text_color=T1, width=120)
        self.btn_add_wm.pack(side="right", padx=(2, 0), fill="x", expand=True)

        # Row 2: Thêm Số Tập / Phần
        f_add2 = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        f_add2.pack(fill="x", padx=10, pady=(2, 5))

        self.btn_add_part = ctk.CTkButton(f_add2, text="[+] Thêm Phần (Phần 1, Phần 2...)", command=self.add_part_layer, fg_color=ORG[1], text_color=BG[1])
        self.btn_add_part.pack(fill="x", expand=True)

        # Layer Listbox frame
        self.layer_frame = ctk.CTkScrollableFrame(self.right_panel, height=200, fg_color=BG3, scrollbar_button_color=BG4)
        self.layer_frame.pack(fill="x", padx=10, pady=5)

        # Layer Ordering Buttons
        f_order = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        f_order.pack(fill="x", padx=10, pady=2)
        self.btn_move_up = ctk.CTkButton(f_order, text="▲ Lên trên", command=self.move_layer_up, fg_color=BG4, text_color=T1, height=24, font=F(11))
        self.btn_move_up.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.btn_move_down = ctk.CTkButton(f_order, text="▼ Xuống dưới", command=self.move_layer_down, fg_color=BG4, text_color=T1, height=24, font=F(11))
        self.btn_move_down.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # Properties Editor Panel (Dynamic depending on layer type)
        ctk.CTkLabel(self.right_panel, text="🛠 THUỘC TÍNH LAYER", font=F(12, "bold"), text_color=T2).pack(pady=(15, 5))
        self.prop_panel = ctk.CTkFrame(self.right_panel, fg_color=BG3, height=220, corner_radius=8)
        self.prop_panel.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.prop_panel.pack_propagate(False)

        self.show_properties_panel()

    def update_log(self, message):
        def _append():
            self.log_box.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.log_box.insert("end", f"[{ts}] {message}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)

        # Write to log file in modules/yt_compiler/yt_compiler_run.log
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt_compiler_run.log")
        try:
            full_ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{full_ts}] {message}\n")
        except Exception as e:
            print(f"Failed to append to log file: {e}")

    # --- ADVANCED UI CONFIGURATION EVENTS ---
    def on_bg_style_changed(self, choice):
        if choice == "Nền màu đơn sắc":
            self.f_solid_color.pack(fill="x", padx=5, pady=2, before=self.btn_bgm)
            self.f_custom_bg.pack_forget()
        elif choice == "Nền ảnh/video tùy chọn":
            self.f_custom_bg.pack(fill="x", padx=5, pady=2, before=self.btn_bgm)
            self.f_solid_color.pack_forget()
        else:
            self.f_solid_color.pack_forget()
            self.f_custom_bg.pack_forget()
        self.redraw_canvas()

    def choose_solid_color(self):
        color = colorchooser.askcolor(color=self.solid_color_hex, title="Chọn màu nền video dọc")[1]
        if color:
            self.solid_color_hex = color
            self.btn_solid_color.configure(fg_color=color, text_color="black" if self.is_light_color(color) else "white")
            self.redraw_canvas()

    def choose_custom_bg(self):
        path = filedialog.askopenfilename(
            title="Chọn Tệp Ảnh hoặc Video Nền",
            filetypes=[("Media Files", "*.png *.jpg *.jpeg *.bmp *.webp *.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.3gp")]
        )
        if path:
            self.custom_bg_path = path
            self.lbl_custom_bg.configure(text=os.path.basename(path), text_color=GRN)
            # Live preview support for static images
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
                try:
                    self.bg_image_pil = Image.open(path).convert("RGB")
                except Exception as e:
                    print(f"Failed to load custom bg image: {e}")
            self.redraw_canvas()
        else:
            self.custom_bg_path = None
            self.lbl_custom_bg.configure(text="Chưa chọn", text_color=T3)
            self.redraw_canvas()

    def open_thumbnail_dialog(self):
        # Create toplevel window dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Cấu hình & Xem trước Ảnh bìa")
        dialog.geometry("900 softened sizing")
        dialog.geometry("920x540")
        dialog.resizable(False, False)
        dialog.configure(fg_color=BG[1])
        
        # Make modal
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        self.thumb_dialog = dialog
        
        # Layout Config (Left: Scrollable Controls, Right: Live Preview)
        dialog.grid_columnconfigure(0, weight=0, minsize=370)
        dialog.grid_columnconfigure(1, weight=1)
        dialog.grid_rowconfigure(0, weight=1)
        
        # Left Scrollable Frame for settings
        f_left = ctk.CTkScrollableFrame(dialog, fg_color=BG2[1], corner_radius=10, width=340, scrollbar_button_color=BG4[1])
        f_left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(f_left, text="🎨 Cấu hình Banner Ảnh Bìa", font=F(13, "bold"), text_color=ORG[1]).pack(pady=(10, 10))
        
        # 1. Text Template
        f_temp = ctk.CTkFrame(f_left, fg_color="transparent")
        f_temp.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(f_temp, text="Mẫu chữ banner (dùng {index}):", font=F(11), text_color=T2[1]).pack(anchor="w")
        self.dlg_thumb_temp = ctk.CTkEntry(f_temp, font=F(11), height=24, width=280)
        self.dlg_thumb_temp.insert(0, self.entry_thumb_temp.get())
        self.dlg_thumb_temp.pack(fill="x", pady=2)
        
        # 2. Start Index
        f_idx = ctk.CTkFrame(f_left, fg_color="transparent")
        f_idx.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(f_idx, text="Phần bắt đầu:", font=F(11), text_color=T2[1]).pack(side="left")
        self.dlg_thumb_start_idx = ctk.CTkEntry(f_idx, width=70, height=24, font=F(11), justify="center")
        self.dlg_thumb_start_idx.insert(0, self.entry_thumb_start_idx.get())
        self.dlg_thumb_start_idx.pack(side="right")

        # 3. Font Size input
        f_font_size = ctk.CTkFrame(f_left, fg_color="transparent")
        f_font_size.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(f_font_size, text="Cỡ chữ banner:", font=F(11), text_color=T2[1]).pack(side="left")
        self.entry_thumb_font_size = ctk.CTkEntry(f_font_size, width=70, height=24, font=F(11), justify="center")
        self.entry_thumb_font_size.insert(0, str(self.thumbnail_font_size))
        self.entry_thumb_font_size.pack(side="right")
        
        # 4. Colors Setup
        f_colors = ctk.CTkFrame(f_left, fg_color="transparent")
        f_colors.pack(fill="x", padx=10, pady=4)
        
        ctk.CTkLabel(f_colors, text="Màu viền banner:", font=F(11), text_color=T2[1]).pack(anchor="w")
        self.combo_thumb_border = ctk.CTkOptionMenu(
            f_colors, 
            values=["Cam (#FE640B)", "Đỏ (#D20F39)", "Đen (#000000)", "Xanh (#1E66F5)"],
            font=F(11), height=22
        )
        self.combo_thumb_border.set(self.thumbnail_border_color)
        self.combo_thumb_border.pack(fill="x", pady=(2, 6))
        
        ctk.CTkLabel(f_colors, text="Màu chữ banner:", font=F(11), text_color=T2[1]).pack(anchor="w")
        self.combo_thumb_text = ctk.CTkOptionMenu(
            f_colors, 
            values=["Đỏ (#D20F39)", "Cam (#FE640B)", "Vàng (#FFFF00)", "Xanh (#1E66F5)"],
            font=F(11), height=22
        )
        self.combo_thumb_text.set(self.thumbnail_text_color)
        self.combo_thumb_text.pack(fill="x", pady=(2, 6))

        # 5. Banner background setup
        ctk.CTkLabel(f_colors, text="Màu nền banner:", font=F(11), text_color=T2[1]).pack(anchor="w")
        self.combo_thumb_banner_bg = ctk.CTkOptionMenu(
            f_colors, 
            values=["Trắng (#FFFFFF)", "Đen (#000000)", "Trong suốt", "Cam (#FE640B)", "Xanh (#1E66F5)"],
            font=F(11), height=22
        )
        self.combo_thumb_banner_bg.set(self.thumbnail_banner_color)
        self.combo_thumb_banner_bg.pack(fill="x", pady=(2, 6))

        # 6. Scrubbing Positions (Sliders)
        f_scrub_title = ctk.CTkFrame(f_left, fg_color="transparent")
        f_scrub_title.pack(fill="x", padx=10, pady=(10, 2))
        ctk.CTkLabel(f_scrub_title, text="🎯 Chọn Điểm Hay Nhất (Food/Highlight)", font=F(11, "bold"), text_color=ORG[1]).pack(anchor="w")

        # Frame 1 Slider
        f_scrub1 = ctk.CTkFrame(f_left, fg_color="transparent")
        f_scrub1.pack(fill="x", padx=10, pady=2)
        f_scrub1_lbls = ctk.CTkFrame(f_scrub1, fg_color="transparent")
        f_scrub1_lbls.pack(fill="x")
        ctk.CTkLabel(f_scrub1_lbls, text="Vị trí Khung 1 (Trái):", font=F(10), text_color=T2[1]).pack(side="left")
        self.lbl_f1_val = ctk.CTkLabel(f_scrub1_lbls, text=f"{int(self.thumbnail_frame_offsets[0])}%", font=F(10, "bold"), text_color=ORG[1])
        self.lbl_f1_val.pack(side="right")
        self.slider_f1 = ctk.CTkSlider(f_scrub1, from_=0, to=100, number_of_steps=100, height=16)
        self.slider_f1.set(self.thumbnail_frame_offsets[0])
        self.slider_f1.pack(fill="x", pady=2)
        self.slider_f1.configure(command=lambda val: self.lbl_f1_val.configure(text=f"{int(val)}%"))
        self.slider_f1.bind("<ButtonRelease-1>", lambda e: self.update_thumb_preview())

        # Frame 2 Slider
        f_scrub2 = ctk.CTkFrame(f_left, fg_color="transparent")
        f_scrub2.pack(fill="x", padx=10, pady=2)
        f_scrub2_lbls = ctk.CTkFrame(f_scrub2, fg_color="transparent")
        f_scrub2_lbls.pack(fill="x")
        ctk.CTkLabel(f_scrub2_lbls, text="Vị trí Khung 2 (Giữa):", font=F(10), text_color=T2[1]).pack(side="left")
        self.lbl_f2_val = ctk.CTkLabel(f_scrub2_lbls, text=f"{int(self.thumbnail_frame_offsets[1])}%", font=F(10, "bold"), text_color=ORG[1])
        self.lbl_f2_val.pack(side="right")
        self.slider_f2 = ctk.CTkSlider(f_scrub2, from_=0, to=100, number_of_steps=100, height=16)
        self.slider_f2.set(self.thumbnail_frame_offsets[1])
        self.slider_f2.pack(fill="x", pady=2)
        self.slider_f2.configure(command=lambda val: self.lbl_f2_val.configure(text=f"{int(val)}%"))
        self.slider_f2.bind("<ButtonRelease-1>", lambda e: self.update_thumb_preview())

        # Frame 3 Slider
        f_scrub3 = ctk.CTkFrame(f_left, fg_color="transparent")
        f_scrub3.pack(fill="x", padx=10, pady=2)
        f_scrub3_lbls = ctk.CTkFrame(f_scrub3, fg_color="transparent")
        f_scrub3_lbls.pack(fill="x")
        ctk.CTkLabel(f_scrub3_lbls, text="Vị trí Khung 3 (Phải):", font=F(10), text_color=T2[1]).pack(side="left")
        self.lbl_f3_val = ctk.CTkLabel(f_scrub3_lbls, text=f"{int(self.thumbnail_frame_offsets[2])}%", font=F(10, "bold"), text_color=ORG[1])
        self.lbl_f3_val.pack(side="right")
        self.slider_f3 = ctk.CTkSlider(f_scrub3, from_=0, to=100, number_of_steps=100, height=16)
        self.slider_f3.set(self.thumbnail_frame_offsets[2])
        self.slider_f3.pack(fill="x", pady=2)
        self.slider_f3.configure(command=lambda val: self.lbl_f3_val.configure(text=f"{int(val)}%"))
        self.slider_f3.bind("<ButtonRelease-1>", lambda e: self.update_thumb_preview())

        # 7. Custom Thumbnail import
        f_custom = ctk.CTkFrame(f_left, fg_color="transparent")
        f_custom.pack(fill="x", padx=10, pady=10)
        self.btn_import_thumb = ctk.CTkButton(
            f_custom,
            text="📂 Chọn Ảnh Bìa Có Sẵn",
            command=self.choose_custom_thumbnail,
            fg_color=BG4[1],
            text_color=T1[1],
            font=F(11),
            height=28
        )
        self.btn_import_thumb.pack(fill="x")
        self.lbl_custom_thumb = ctk.CTkLabel(
            f_custom, 
            text=os.path.basename(self.custom_thumbnail_path) if self.custom_thumbnail_path else "Hoặc import file ảnh riêng",
            font=F(10),
            text_color=GRN[1] if self.custom_thumbnail_path else T3[1]
        )
        self.lbl_custom_thumb.pack(pady=2)
        
        # Bind dialog update events to update live preview
        self.dlg_thumb_temp.bind("<KeyRelease>", lambda e: self.update_thumb_preview())
        self.dlg_thumb_start_idx.bind("<KeyRelease>", lambda e: self.update_thumb_preview())
        self.entry_thumb_font_size.bind("<KeyRelease>", lambda e: self.update_thumb_preview())
        self.combo_thumb_border.configure(command=lambda choice: self.update_thumb_preview())
        self.combo_thumb_text.configure(command=lambda choice: self.update_thumb_preview())
        self.combo_thumb_banner_bg.configure(command=lambda choice: self.update_thumb_preview())
        
        # Apply Button
        def apply_and_close():
            self.entry_thumb_temp.delete(0, tk.END)
            self.entry_thumb_temp.insert(0, self.dlg_thumb_temp.get())
            self.entry_thumb_start_idx.delete(0, tk.END)
            self.entry_thumb_start_idx.insert(0, self.dlg_thumb_start_idx.get())
            self.thumbnail_border_color = self.combo_thumb_border.get()
            self.thumbnail_text_color = self.combo_thumb_text.get()
            self.thumbnail_banner_color = self.combo_thumb_banner_bg.get()
            
            try:
                self.thumbnail_font_size = int(self.entry_thumb_font_size.get())
            except:
                self.thumbnail_font_size = 44
                
            self.thumbnail_frame_offsets = [
                self.slider_f1.get(),
                self.slider_f2.get(),
                self.slider_f3.get()
            ]
            dialog.grab_release()
            dialog.destroy()
            
        btn_apply = ctk.CTkButton(f_left, text="💾 ÁP DỤNG & LƯU", command=apply_and_close, fg_color=GRN[1], text_color=BG[1], font=F(12, "bold"), height=32)
        btn_apply.pack(fill="x", padx=10, pady=15)
        
        # Right Frame
        f_right = ctk.CTkFrame(dialog, fg_color=BG2[1], corner_radius=10)
        f_right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(f_right, text="👁️ Ảnh bìa của video đầu tiên (Xem trước)", font=F(13, "bold"), text_color=T1[1]).pack(pady=(15, 5))
        
        self.lbl_thumb_preview = ctk.CTkLabel(f_right, text="[Chưa nạp video con để xem trước]", fg_color="#0D1117", corner_radius=8, width=480, height=270, font=F(11))
        self.lbl_thumb_preview.pack(pady=10)
        
        self.lbl_thumb_status = ctk.CTkLabel(f_right, text="Sẵn sàng", font=F(10), text_color=T3[1])
        self.lbl_thumb_status.pack(pady=2)
        
        self.update_thumb_preview()
        if self.video_paths:
            # Run background scanner automatically on open
            self.run_auto_food_scanner()

    def run_auto_food_scanner(self):
        if not self.video_paths:
            return
        threading.Thread(target=self._auto_food_scanner_worker, daemon=True).start()

    def _auto_food_scanner_worker(self):
        try:
            from yt_compiler.thumbnail_maker import find_best_food_frame_percentage
            
            p1 = find_best_food_frame_percentage(self.video_paths[0], default_pct=15.0)
            p2 = p1
            p3 = p1
            
            if len(self.video_paths) >= 2:
                p2 = find_best_food_frame_percentage(self.video_paths[1], default_pct=33.0)
            if len(self.video_paths) >= 3:
                p3 = find_best_food_frame_percentage(self.video_paths[2], default_pct=85.0)
                
            self.after(0, self._apply_scanned_food_percentages, p1, p2, p3)
        except:
            pass

    def _apply_scanned_food_percentages(self, p1, p2, p3):
        try:
            self.slider_f1.set(p1)
            self.lbl_f1_val.configure(text=f"{int(p1)}%")
            
            self.slider_f2.set(p2)
            self.lbl_f2_val.configure(text=f"{int(p2)}%")
            
            self.slider_f3.set(p3)
            self.lbl_f3_val.configure(text=f"{int(p3)}%")
            
            self.update_thumb_preview()
        except:
            pass

    def choose_custom_thumbnail(self):
        path = filedialog.askopenfilename(
            title="Chọn Tệp Ảnh Bìa Tùy Chọn",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if path:
            self.custom_thumbnail_path = path
            self.lbl_custom_thumb.configure(text=os.path.basename(path), text_color=GRN[1])
            try:
                img = Image.open(path).convert("RGB")
                img_resized = img.resize((480, 270), Image.Resampling.LANCZOS)
                self._render_thumb_pil_preview(img_resized)
            except Exception as e:
                print(f"Failed to load custom thumbnail preview: {e}")
        else:
            self.custom_thumbnail_path = None
            self.lbl_custom_thumb.configure(text="Hoặc import file ảnh riêng", text_color=T3[1])
            self.update_thumb_preview()

    def update_thumb_preview(self):
        if self.custom_thumbnail_path and os.path.exists(self.custom_thumbnail_path):
            return
            
        if not self.video_paths:
            self._show_blank_thumb_preview()
            return
            
        # Cancel any pending preview rendering timer to debounce typing/sliding
        if hasattr(self, "_thumb_preview_timer") and self._thumb_preview_timer:
            self.after_cancel(self._thumb_preview_timer)
            
        self._thumb_preview_timer = self.after(600, self._trigger_thumb_preview_worker)

    def _trigger_thumb_preview_worker(self):
        if hasattr(self, "lbl_thumb_status") and self.lbl_thumb_status.winfo_exists():
            self.lbl_thumb_status.configure(text="Đang trích xuất khung hình...")
        threading.Thread(target=self._generate_thumb_preview_worker, daemon=True).start()

    def _show_blank_thumb_preview(self):
        if hasattr(self, "lbl_thumb_preview") and self.lbl_thumb_preview.winfo_exists():
            self.lbl_thumb_preview.configure(image=None, text="[Nạp video con bên ngoài để xem trước ảnh bìa]")

    def _generate_thumb_preview_worker(self):
        if not self.preview_thread_lock.acquire(blocking=False):
            return
        try:
            preview_videos = self.video_paths[:3] if len(self.video_paths) >= 3 else self.video_paths
            v_path = self.video_paths[0]
            
            color_map = {
                "Cam (#FE640B)": "#FE640B",
                "Đỏ (#D20F39)": "#D20F39",
                "Đen (#000000)": "#000000",
                "Xanh (#1E66F5)": "#1E66F5",
                "Vàng (#FFFF00)": "#FFFF00"
            }
            border_hex = color_map.get(self.combo_thumb_border.get(), "#FE640B")
            text_hex = color_map.get(self.combo_thumb_text.get(), "#D20F39")
            stroke_hex = "#450a0a" if text_hex == "#D20F39" else "#000000"

            banner_bg_sel = self.combo_thumb_banner_bg.get()
            banner_bg_map = {
                "Trắng (#FFFFFF)": "white",
                "Đen (#000000)": "black",
                "Trong suốt": "#00000000",
                "Cam (#FE640B)": "#FE640B",
                "Xanh (#1E66F5)": "#1E66F5"
            }
            banner_bg = banner_bg_map.get(banner_bg_sel, "white")

            try:
                f_size = int(self.entry_thumb_font_size.get())
            except:
                f_size = 44

            p_list = [
                self.slider_f1.get(),
                self.slider_f2.get(),
                self.slider_f3.get()
            ]

            try:
                curr_idx = int(self.dlg_thumb_start_idx.get())
            except:
                curr_idx = 1

            template_str = self.dlg_thumb_temp.get()
            title_text = template_str.replace("{index}", str(curr_idx))

            temp_path = os.path.join(os.path.dirname(v_path), "temp_dialog_live_preview.jpg")

            from yt_compiler.thumbnail_maker import create_collage_thumbnail
            success = create_collage_thumbnail(
                video_list=preview_videos,
                title_text=title_text,
                output_thumb_path=temp_path,
                banner_border_color=border_hex,
                text_fill_color=text_hex,
                text_stroke_color=stroke_hex,
                frame_percentages=p_list,
                font_size=f_size,
                banner_bg_color=banner_bg,
                auto_scan_food=False
            )

            if success and os.path.exists(temp_path):
                img = Image.open(temp_path).convert("RGB")
                img_resized = img.resize((480, 270), Image.Resampling.LANCZOS)
                self.after(0, self._render_thumb_pil_preview, img_resized)
                try: os.remove(temp_path)
                except: pass
        except Exception as err:
            print(f"Error in thumbnail dialog preview thread: {err}")
        finally:
            self.preview_thread_lock.release()

    def _render_thumb_pil_preview(self, pil_img):
        try:
            if hasattr(self, "lbl_thumb_preview") and self.lbl_thumb_preview.winfo_exists():
                ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(480, 270))
                self.lbl_thumb_preview.configure(image=ctk_image, text="")
                self.lbl_thumb_preview.image = ctk_image
            if hasattr(self, "lbl_thumb_status") and self.lbl_thumb_status.winfo_exists():
                self.lbl_thumb_status.configure(text="Sẵn sàng")
        except Exception as e:
            print(f"Failed to display thumbnail preview: {e}")

    def on_bgm_vol_changed(self, val):
        self.lbl_bgm_vol.configure(text=f"Âm lượng nhạc: {int(float(val)*100)}%")

    # --- VIDEO SELECTIONS ---
    def choose_input_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Chứa Video Con")
        if not folder:
            return
        
        valid_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.ts', '.mpeg', '.mpg', '.3gp', '.m4v')
        files = os.listdir(folder)
        self.video_paths = [os.path.join(folder, f) for f in files if f.lower().endswith(valid_exts)]
        self._on_videos_loaded()

    def choose_input_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn Các File Video Con",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.mpeg *.mpg *.3gp *.m4v"), ("All Files", "*.*")]
        )
        if not files:
            return
        self.video_paths = list(files)
        self._on_videos_loaded()

    def _on_videos_loaded(self):
        if self.video_paths:
            self.lbl_loaded.configure(text=f"Đã nạp: {len(self.video_paths)} videos", text_color=GRN)
            self.update_log(f"🔎 Đã nạp {len(self.video_paths)} clip con vào danh sách hàng loạt.")
            
            # Update Preview frame list OptionMenu
            vals = ["Khung lưới mặc định"]
            for idx, path in enumerate(self.video_paths):
                vals.append(f"Clip {idx+1}: {os.path.basename(path)}")
            self.combo_preview_bg.configure(values=vals)
            
            # Auto-select the first clip to show it on preview immediately
            first_clip_val = vals[1]
            self.combo_preview_bg.set(first_clip_val)
            self.on_preview_bg_changed(first_clip_val)
        else:
            self.lbl_loaded.configure(text="Không nạp video nào!", text_color=RED)

    def choose_intro(self):
        path = filedialog.askopenfilename(
            title="Chọn Video Intro",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.mpeg *.mpg *.3gp *.m4v")]
        )
        if path:
            self.intro_path = path
            self.lbl_intro.configure(text=os.path.basename(path), text_color=GRN)
        else:
            self.intro_path = None
            self.lbl_intro.configure(text="Chưa chọn", text_color=T3)

    def choose_outro(self):
        path = filedialog.askopenfilename(
            title="Chọn Video Outro",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.mpeg *.mpg *.3gp *.m4v")]
        )
        if path:
            self.outro_path = path
            self.lbl_outro.configure(text=os.path.basename(path), text_color=GRN)
        else:
            self.outro_path = None
            self.lbl_outro.configure(text="Chưa chọn", text_color=T3)

    def choose_dyn_bg(self):
        path = filedialog.askopenfilename(
            title="Chọn Video Nền Động (MP4/MOV)",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.mpeg *.mpg *.3gp *.m4v")]
        )
        if path:
            self.dyn_bg_path = path
            self.lbl_dyn_bg.configure(text=os.path.basename(path), text_color=GRN)
        else:
            self.dyn_bg_path = None
            self.lbl_dyn_bg.configure(text="Chưa chọn", text_color=T3)

    def choose_bgm(self):
        path = filedialog.askopenfilename(
            title="Chọn Tệp Nhạc Nền (BGM)",
            filetypes=[("Audio/Video Files", "*.mp3 *.wav *.m4a *.ogg *.aac *.mp4 *.mov *.mkv *.avi *.flac")]
        )
        if path:
            self.bgm_path = path
            self.lbl_bgm.configure(text=os.path.basename(path), text_color=GRN)
        else:
            self.bgm_path = None
            self.lbl_bgm.configure(text="Chưa chọn", text_color=T3)

    def choose_silent_bgm(self):
        path = filedialog.askopenfilename(
            title="Chọn Tệp Nhạc Cho Clip Câm",
            filetypes=[("Audio/Video Files", "*.mp3 *.wav *.m4a *.ogg *.aac *.mp4 *.mov *.mkv *.avi *.flac")]
        )
        if path:
            self.silent_bgm_path = path
            self.lbl_silent_bgm.configure(text=os.path.basename(path), text_color=GRN)
        else:
            self.silent_bgm_path = None
            self.lbl_silent_bgm.configure(text="Chưa chọn", text_color=T3)

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Lưu Video Ghép")
        if folder:
            self.output_dir = folder
            self.lbl_out_dir.configure(text=f"Lưu tại: .../{os.path.basename(folder)}", text_color=GRN)
            self.update_log(f"📂 Đã chọn thư mục đầu ra: {folder}")

    # --- PREVIEW IMAGE SELECTOR ---
    def on_preview_bg_changed(self, choice):
        if choice == "Khung lưới mặc định":
            self.bg_image_pil = None
        else:
            try:
                clip_idx = int(choice.split(":")[0].replace("Clip ", "")) - 1
                video_path = self.video_paths[clip_idx]
                
                # Extract first frame
                cap = cv2.VideoCapture(video_path)
                ret, frame = cap.read()
                cap.release()
                if ret:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.bg_image_pil = Image.fromarray(frame)
                else:
                    self.bg_image_pil = None
                    self.update_log(f"⚠️ Không thể trích xuất frame xem trước từ clip {clip_idx+1}")
            except Exception as e:
                print(f"Error loading preview frame: {e}")
                self.bg_image_pil = None
                
        self.redraw_canvas()

    # --- LAYER MANAGEMENTS ---
    def add_text_layer(self):
        new_text = {
            "type": "text",
            "text": "Nhấn đúp để sửa chữ",
            "x": 960,
            "y": 800,
            "font_name": "Be Vietnam Pro",
            "font_path": self.FONTS["Be Vietnam Pro"],
            "size": 50,
            "color": "#FFFF00",
            "border_color": "#000000",
            "angle": 0,
            "stroke_width": 3,
            "bg_box_enabled": False,
            "bg_box_color": "#000000",
            "bg_box_opacity": 0.6,
            "shadow_enabled": False,
            "shadow_color": "#000000",
            "shadow_offset": 4
        }
        self.layers.append(new_text)
        self.selected_layer_idx = len(self.layers) - 1
        self.redraw_canvas()
        self.update_layer_list()
        self.show_properties_panel()

    def add_part_layer(self):
        new_text = {
            "type": "text",
            "text": "Phần {index}",
            "x": 960,
            "y": 900,
            "font_name": "Be Vietnam Pro",
            "font_path": self.FONTS["Be Vietnam Pro"],
            "size": 60,
            "color": "#FFFF00",
            "border_color": "#000000",
            "angle": 0,
            "stroke_width": 4,
            "bg_box_enabled": False,
            "bg_box_color": "#000000",
            "bg_box_opacity": 0.6,
            "shadow_enabled": False,
            "shadow_color": "#000000",
            "shadow_offset": 4
        }
        self.layers.append(new_text)
        self.selected_layer_idx = len(self.layers) - 1
        self.redraw_canvas()
        self.update_layer_list()
        self.show_properties_panel()

    def add_watermark_layer(self):
        path = filedialog.askopenfilename(
            title="Chọn Ảnh Logo/Watermark",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if not path:
            return
        
        new_wm = {
            "type": "watermark",
            "path": path,
            "x": 100,
            "y": 100,
            "w": 150,
            "h": 150,
            "opacity": 0.8
        }
        self.layers.append(new_wm)
        self.selected_layer_idx = len(self.layers) - 1
        self.redraw_canvas()
        self.update_layer_list()
        self.show_properties_panel()

    def delete_layer(self, idx):
        if idx < len(self.layers):
            self.layers.pop(idx)
            self.selected_layer_idx = None
            self.redraw_canvas()
            self.update_layer_list()
            self.show_properties_panel()

    def move_layer_up(self):
        # Swap with element to the right (drawn later = Z-index higher)
        idx = self.selected_layer_idx
        if idx is not None and idx < len(self.layers) - 1:
            self.layers[idx], self.layers[idx+1] = self.layers[idx+1], self.layers[idx]
            self.selected_layer_idx = idx + 1
            self.redraw_canvas()
            self.update_layer_list()

    def move_layer_down(self):
        # Swap with element to the left (drawn earlier = Z-index lower)
        idx = self.selected_layer_idx
        if idx is not None and idx > 0:
            self.layers[idx], self.layers[idx-1] = self.layers[idx-1], self.layers[idx]
            self.selected_layer_idx = idx - 1
            self.redraw_canvas()
            self.update_layer_list()

    def update_layer_list(self):
        for widget in self.layer_frame.winfo_children():
            widget.destroy()

        for idx, layer in enumerate(self.layers):
            row = ctk.CTkFrame(self.layer_frame, fg_color=BG4 if idx == self.selected_layer_idx else "transparent", height=32, corner_radius=4)
            row.pack(fill="x", pady=2, padx=2)
            row.pack_propagate(False)

            label_text = f"[{layer['type'].upper()}] "
            if layer["type"] == "text":
                label_text += layer["text"][:15] + ("..." if len(layer["text"]) > 15 else "")
            else:
                label_text += os.path.basename(layer["path"])[:15]

            def select_action(event, i=idx):
                self.selected_layer_idx = i
                self.redraw_canvas()
                self.update_layer_list()
                self.show_properties_panel()

            lbl = ctk.CTkLabel(row, text=label_text, font=F(11, "bold"), text_color=T1, cursor="hand2")
            lbl.pack(side="left", padx=5, fill="x", expand=True)
            lbl.bind("<Button-1>", select_action)
            row.bind("<Button-1>", select_action)

            btn_del = ctk.CTkButton(
                row,
                text="✕",
                width=20,
                height=20,
                fg_color="transparent",
                text_color=RED,
                hover_color=RED,
                font=F(10, "bold"),
                command=lambda i=idx: self.delete_layer(i)
            )
            btn_del.pack(side="right", padx=5)

    def show_properties_panel(self):
        for widget in self.prop_panel.winfo_children():
            widget.destroy()

        if self.selected_layer_idx is None or self.selected_layer_idx >= len(self.layers):
            ctk.CTkLabel(
                self.prop_panel,
                text="Chọn một layer\ntrên Preview hoặc\nDanh sách Layer\nđể sửa thuộc tính.",
                font=F(12, "bold"),
                text_color=T3
            ).pack(expand=True)
            return

        layer = self.layers[self.selected_layer_idx]

        if layer["type"] == "text":
            # 1. Content Input
            f_content = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_content.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(f_content, text="Nội dung:", font=F(11), text_color=T2).pack(anchor="w")
            
            self.entry_text = ctk.CTkEntry(f_content, font=F(12), height=28)
            self.entry_text.insert(0, layer["text"])
            self.entry_text.pack(fill="x", pady=2)
            
            def on_text_changed(event):
                layer["text"] = self.entry_text.get()
                self.redraw_canvas()
                self.update_layer_list()
            self.entry_text.bind("<KeyRelease>", on_text_changed)

            # 2. Font Size Slider
            f_size = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_size.pack(fill="x", padx=10, pady=5)
            self.lbl_size_val = ctk.CTkLabel(f_size, text=f"Cỡ chữ: {layer['size']}", font=F(11), text_color=T2)
            self.lbl_size_val.pack(side="left")
            
            slider_size = ctk.CTkSlider(f_size, from_=20, to=150, number_of_steps=130, width=120, height=16)
            slider_size.set(layer["size"])
            slider_size.pack(side="right")

            def on_size_changed(val):
                layer["size"] = int(val)
                self.lbl_size_val.configure(text=f"Cỡ chữ: {layer['size']}")
                self.redraw_canvas()
            slider_size.configure(command=on_size_changed)

            # 3. Font Family Dropdown
            f_font = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_font.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(f_font, text="Font chữ:", font=F(11), text_color=T2).pack(side="left")
            
            combo_font = ctk.CTkOptionMenu(f_font, values=list(self.FONTS.keys()), width=130, height=24)
            curr_key = "Arial / Standard"
            for k, v in self.FONTS.items():
                if v == layer["font_path"]:
                    curr_key = k
                    break
            combo_font.set(curr_key)
            combo_font.pack(side="right")

            def on_font_changed(choice):
                layer["font_name"] = choice
                layer["font_path"] = self.FONTS[choice]
                self.redraw_canvas()
            combo_font.configure(command=on_font_changed)

            # 4. Color Pickers (Text Fill & Stroke)
            f_colors = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_colors.pack(fill="x", padx=10, pady=5)

            self.btn_text_color = ctk.CTkButton(
                f_colors,
                text="Màu chữ",
                fg_color=layer["color"],
                text_color="black" if self.is_light_color(layer["color"]) else "white",
                height=26,
                command=lambda: self.choose_layer_color("color")
            )
            self.btn_text_color.pack(side="left", fill="x", expand=True, padx=(0, 5))

            self.btn_stroke_color = ctk.CTkButton(
                f_colors,
                text="Màu viền",
                fg_color=layer["border_color"],
                text_color="black" if self.is_light_color(layer["border_color"]) else "white",
                height=26,
                command=lambda: self.choose_layer_color("border_color")
            )
            self.btn_stroke_color.pack(side="right", fill="x", expand=True, padx=(5, 0))

            # 5. Rotate Angle
            f_angle = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_angle.pack(fill="x", padx=10, pady=5)
            self.lbl_angle_val = ctk.CTkLabel(f_angle, text=f"Xoay chữ: {layer.get('angle', 0)}°", font=F(11), text_color=T2)
            self.lbl_angle_val.pack(side="left")
            slider_angle = ctk.CTkSlider(f_angle, from_=-180, to=180, number_of_steps=360, width=120, height=16)
            slider_angle.set(layer.get("angle", 0))
            slider_angle.pack(side="right")
            def on_angle_changed(val):
                layer["angle"] = int(val)
                self.lbl_angle_val.configure(text=f"Xoay chữ: {layer['angle']}°")
                self.redraw_canvas()
            slider_angle.configure(command=on_angle_changed)

            # 6. Stroke Width
            f_stroke = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_stroke.pack(fill="x", padx=10, pady=5)
            self.lbl_stroke_val = ctk.CTkLabel(f_stroke, text=f"Viền chữ: {layer.get('stroke_width', 3)}px", font=F(11), text_color=T2)
            self.lbl_stroke_val.pack(side="left")
            slider_stroke = ctk.CTkSlider(f_stroke, from_=0, to=15, number_of_steps=15, width=120, height=16)
            slider_stroke.set(layer.get("stroke_width", 3))
            slider_stroke.pack(side="right")
            def on_stroke_changed(val):
                layer["stroke_width"] = int(val)
                self.lbl_stroke_val.configure(text=f"Viền chữ: {layer['stroke_width']}px")
                self.redraw_canvas()
            slider_stroke.configure(command=on_stroke_changed)

            # 7. Background Box
            f_bg_box = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_bg_box.pack(fill="x", padx=10, pady=5)
            bg_box_enabled_var = tk.BooleanVar(value=layer.get("bg_box_enabled", False))
            def on_bg_box_toggled():
                layer["bg_box_enabled"] = bg_box_enabled_var.get()
                self.redraw_canvas()
            chk_bg_box = ctk.CTkCheckBox(f_bg_box, text="Hộp nền chữ", variable=bg_box_enabled_var, command=on_bg_box_toggled, font=F(11), text_color=T2)
            chk_bg_box.pack(anchor="w")

            f_bg_box_detail = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_bg_box_detail.pack(fill="x", padx=10, pady=2)
            self.lbl_bg_opacity = ctk.CTkLabel(f_bg_box_detail, text=f"Độ mờ nền: {int(layer.get('bg_box_opacity', 0.6)*100)}%", font=F(10), text_color=T3)
            self.lbl_bg_opacity.pack(side="left")
            slider_bg_opacity = ctk.CTkSlider(f_bg_box_detail, from_=0.0, to=1.0, number_of_steps=100, width=120, height=16)
            slider_bg_opacity.set(layer.get("bg_box_opacity", 0.6))
            slider_bg_opacity.pack(side="right")
            def on_bg_opacity_changed(val):
                layer["bg_box_opacity"] = float(val)
                self.lbl_bg_opacity.configure(text=f"Độ mờ nền: {int(float(val)*100)}%")
                self.redraw_canvas()
            slider_bg_opacity.configure(command=on_bg_opacity_changed)

            self.btn_bg_box_color = ctk.CTkButton(
                self.prop_panel,
                text="Màu nền hộp",
                fg_color=layer.get("bg_box_color", "#000000"),
                text_color="black" if self.is_light_color(layer.get("bg_box_color", "#000000")) else "white",
                height=24,
                command=lambda: self.choose_layer_color("bg_box_color")
            )
            self.btn_bg_box_color.pack(fill="x", padx=10, pady=3)

            # 8. Drop Shadow
            f_shadow = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_shadow.pack(fill="x", padx=10, pady=5)
            shadow_enabled_var = tk.BooleanVar(value=layer.get("shadow_enabled", False))
            def on_shadow_toggled():
                layer["shadow_enabled"] = shadow_enabled_var.get()
                self.redraw_canvas()
            chk_shadow = ctk.CTkCheckBox(f_shadow, text="Đổ bóng chữ", variable=shadow_enabled_var, command=on_shadow_toggled, font=F(11), text_color=T2)
            chk_shadow.pack(anchor="w")

            f_shadow_detail = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_shadow_detail.pack(fill="x", padx=10, pady=2)
            self.lbl_shadow_offset = ctk.CTkLabel(f_shadow_detail, text=f"Độ lệch bóng: {layer.get('shadow_offset', 4)}px", font=F(10), text_color=T3)
            self.lbl_shadow_offset.pack(side="left")
            slider_shadow = ctk.CTkSlider(f_shadow_detail, from_=0, to=20, number_of_steps=20, width=120, height=16)
            slider_shadow.set(layer.get("shadow_offset", 4))
            slider_shadow.pack(side="right")
            def on_shadow_offset_changed(val):
                layer["shadow_offset"] = int(val)
                self.lbl_shadow_offset.configure(text=f"Độ lệch bóng: {layer['shadow_offset']}px")
                self.redraw_canvas()
            slider_shadow.configure(command=on_shadow_offset_changed)

            self.btn_shadow_color = ctk.CTkButton(
                self.prop_panel,
                text="Màu đổ bóng",
                fg_color=layer.get("shadow_color", "#000000"),
                text_color="black" if self.is_light_color(layer.get("shadow_color", "#000000")) else "white",
                height=24,
                command=lambda: self.choose_layer_color("shadow_color")
            )
            self.btn_shadow_color.pack(fill="x", padx=10, pady=3)

        elif layer["type"] == "watermark":
            # 1. Image Path Display
            f_path_lbl = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_path_lbl.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(f_path_lbl, text="Tệp Logo:", font=F(11), text_color=T2).pack(anchor="w")
            ctk.CTkLabel(f_path_lbl, text=os.path.basename(layer["path"]), font=F(11, "bold"), text_color=T1).pack(anchor="w")

            # 2. Width Slider (Size scale)
            f_scale = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_scale.pack(fill="x", padx=10, pady=10)
            self.lbl_scale_val = ctk.CTkLabel(f_scale, text=f"Kích thước: {layer['w']}px", font=F(11), text_color=T2)
            self.lbl_scale_val.pack(side="left")
            
            slider_scale = ctk.CTkSlider(f_scale, from_=50, to=800, number_of_steps=150, width=120, height=16)
            slider_scale.set(layer["w"])
            slider_scale.pack(side="right")

            def on_scale_changed(val):
                old_w = layer["w"]
                layer["w"] = int(val)
                ratio = layer["h"] / old_w if old_w > 0 else 1.0
                layer["h"] = int(layer["w"] * ratio)
                self.lbl_scale_val.configure(text=f"Kích thước: {layer['w']}px")
                self.redraw_canvas()
            slider_scale.configure(command=on_scale_changed)

            # 3. Opacity Slider
            f_opac = ctk.CTkFrame(self.prop_panel, fg_color="transparent")
            f_opac.pack(fill="x", padx=10, pady=10)
            self.lbl_opac_val = ctk.CTkLabel(f_opac, text=f"Độ mờ: {int(layer['opacity']*100)}%", font=F(11), text_color=T2)
            self.lbl_opac_val.pack(side="left")
            
            slider_opac = ctk.CTkSlider(f_opac, from_=0.1, to=1.0, number_of_steps=90, width=120, height=16)
            slider_opac.set(layer["opacity"])
            slider_opac.pack(side="right")

            def on_opac_changed(val):
                layer["opacity"] = float(val)
                self.lbl_opac_val.configure(text=f"Độ mờ: {int(layer['opacity']*100)}%")
                self.redraw_canvas()
            slider_opac.configure(command=on_opac_changed)

    def is_light_color(self, hex_str):
        try:
            h = hex_str.lstrip("#")
            rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2])
            return luminance > 128
        except:
            return True

    def choose_layer_color(self, attribute_name):
        layer = self.layers[self.selected_layer_idx]
        default_color = layer.get(attribute_name, "#000000")
        color = colorchooser.askcolor(color=default_color, title="Chọn màu sắc")[1]
        if color:
            layer[attribute_name] = color
            self.redraw_canvas()
            self.show_properties_panel()

    # --- PREVIEW RENDERINGS ---
    def redraw_canvas(self):
        self.canvas.delete("all")
        self.tk_bg_image = None
        self.tk_watermark_imgs = [] 
        self.tk_text_imgs = []

        # 1. Background image or solid color representation in preview
        if self.bg_image_pil:
            try:
                # Preview Standard Aspect Ratio conversions inside preview screen visually
                img_w, img_h = self.bg_image_pil.size
                aspect = img_w / img_h if img_h > 0 else 1.777
                is_16_9 = abs(aspect - (16.0/9.0)) < 0.01

                if is_16_9:
                    scaled_bg = self.bg_image_pil.resize((self.canvas_w, self.canvas_h), Image.Resampling.LANCZOS)
                    self.tk_bg_image = ImageTk.PhotoImage(scaled_bg)
                    self.canvas.create_image(0, 0, anchor="nw", image=self.tk_bg_image)
                else:
                    # Draw visual representation of blurred or solid color background padding
                    bg_style = self.combo_bg_style.get()
                    if bg_style == "Nền màu đơn sắc":
                        # Draw solid color preview background
                        self.canvas.create_rectangle(0, 0, self.canvas_w, self.canvas_h, fill=self.solid_color_hex, outline="")
                    else:
                        # Draw a beautiful, smooth blurred and darkened background using PIL filters
                        try:
                            from PIL import ImageFilter, ImageEnhance
                            # Apply Gaussian blur
                            blurred = self.bg_image_pil.filter(ImageFilter.GaussianBlur(10))
                            # Darken to 40% brightness to make foreground and text contrast better
                            enhancer = ImageEnhance.Brightness(blurred)
                            darkened = enhancer.enhance(0.4)
                            # Scale to fill the 16:9 canvas
                            scaled_blur_bg = darkened.resize((self.canvas_w, self.canvas_h), Image.Resampling.LANCZOS)
                            self.tk_bg_image = ImageTk.PhotoImage(scaled_blur_bg)
                            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_bg_image)
                        except Exception as pil_err:
                            print(f"PIL Preview filter failed: {pil_err}")
                            # Fallback grid/dark color
                            self.canvas.create_rectangle(0, 0, self.canvas_w, self.canvas_h, fill="#181825", outline="")

                    # Draw scaled fitting foreground video in center
                    fg_w = int(self.canvas_h * aspect)
                    fg_h = self.canvas_h
                    if fg_w > self.canvas_w:
                        fg_w = self.canvas_w
                        fg_h = int(self.canvas_w / aspect)
                    
                    fg_x = (self.canvas_w - fg_w) // 2
                    fg_y = (self.canvas_h - fg_h) // 2
                    
                    scaled_fg = self.bg_image_pil.resize((fg_w, fg_h), Image.Resampling.LANCZOS)
                    self.tk_fg_image = ImageTk.PhotoImage(scaled_fg)
                    self.canvas.create_image(fg_x, fg_y, anchor="nw", image=self.tk_fg_image)
            except Exception as e:
                print(f"Error drawing bg: {e}")
                self._draw_default_grid()
        else:
            self._draw_default_grid()

        # 2. Draw active layers
        for idx, layer in enumerate(self.layers):
            cx = layer["x"] * self.scale
            cy = layer["y"] * self.scale

            if layer["type"] == "text":
                c_size = max(10, int(layer["size"] * self.scale))
                
                # Setup Font using PIL
                try:
                    font = ImageFont.truetype(layer["font_path"], c_size)
                except:
                    font = ImageFont.load_default()
                    
                # Dynamic replacement of {index} for preview screen
                try:
                    display_idx = self.entry_thumb_start_idx.get()
                    if not display_idx:
                        display_idx = "1"
                except:
                    display_idx = "1"
                t_str = layer["text"].replace("{index}", display_idx)
                    
                # Measure text size
                draw_dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
                try:
                    bbox = draw_dummy.textbbox((0, 0), t_str, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                    offset_x = bbox[0]
                    offset_y = bbox[1]
                except:
                    tw, th = draw_dummy.textsize(t_str, font=font)
                    offset_x, offset_y = 0, 0
                    
                pad = max(10, int(c_size * 0.4))
                w_img = tw + pad * 2
                h_img = th + pad * 2
                
                txt_canvas = Image.new("RGBA", (w_img, h_img), (0,0,0,0))
                draw = ImageDraw.Draw(txt_canvas)
                
                # Draw Background Box
                if layer.get("bg_box_enabled", False):
                    bg_color = layer.get("bg_box_color", "#000000")
                    bg_alpha = int(layer.get("bg_box_opacity", 0.6) * 255)
                    h_val = bg_color.lstrip('#')
                    rgb = tuple(int(h_val[i:i+2], 16) for i in (0, 2, 4))
                    draw.rectangle(
                        [(pad - 4, pad - 4), (pad + tw + 4, pad + th + 4)],
                        fill=rgb + (bg_alpha,)
                    )
                    
                # Draw Drop Shadow
                if layer.get("shadow_enabled", False):
                    sh_color = layer.get("shadow_color", "#000000")
                    sh_offset = int(layer.get("shadow_offset", 4) * self.scale)
                    h_val = sh_color.lstrip('#')
                    rgb = tuple(int(h_val[i:i+2], 16) for i in (0, 2, 4))
                    draw.text((pad - offset_x + sh_offset, pad - offset_y + sh_offset), 
                              t_str, font=font, fill=rgb + (255,))
                              
                # Draw main text with stroke
                stroke_w = int(layer.get("stroke_width", 3) * self.scale)
                stroke_color = layer.get("border_color", "#000000")
                fill_color = layer.get("color", "#FFFF00")
                draw.text((pad - offset_x, pad - offset_y), t_str, font=font, 
                          fill=fill_color, stroke_width=stroke_w, stroke_fill=stroke_color)
                          
                # Rotate image
                angle = float(layer.get("angle", 0))
                if angle != 0:
                    rotated_img = txt_canvas.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
                else:
                    rotated_img = txt_canvas
                    
                tk_txt_img = ImageTk.PhotoImage(rotated_img)
                self.tk_text_imgs.append(tk_txt_img)
                
                # Draw on canvas centered
                self.canvas.create_image(cx, cy, anchor="center", image=tk_txt_img)
                
                # Draw selection border
                if idx == self.selected_layer_idx:
                    rw, rh = rotated_img.size
                    self.canvas.create_rectangle(
                        cx - rw/2 - 2,
                        cy - rh/2 - 2,
                        cx + rw/2 + 2,
                        cy + rh/2 + 2,
                        outline="#89B4FA",
                        dash=(3, 3),
                        width=1.5
                    )

            elif layer["type"] == "watermark":
                wm_w = max(10, int(layer["w"] * self.scale))
                wm_h = max(10, int(layer["h"] * self.scale))

                if idx == self.selected_layer_idx:
                    self.canvas.create_rectangle(
                        cx - 5,
                        cy - 5,
                        cx + wm_w + 5,
                        cy + wm_h + 5,
                        outline="#89B4FA",
                        dash=(3, 3),
                        width=1.5
                    )

                if os.path.exists(layer["path"]):
                    try:
                        img = Image.open(layer["path"]).convert("RGBA")
                        img = img.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
                        alpha = img.split()[3]
                        alpha = alpha.point(lambda p: int(p * layer["opacity"]))
                        img.putalpha(alpha)

                        tk_wm_img = ImageTk.PhotoImage(img)
                        self.tk_watermark_imgs.append(tk_wm_img) 

                        self.canvas.create_image(cx, cy, anchor="nw", image=tk_wm_img)
                    except Exception as e:
                        self.canvas.create_rectangle(cx, cy, cx + wm_w, cy + wm_h, fill="red", outline="white")
                        self.canvas.create_text(cx + wm_w/2, cy + wm_h/2, text="LOGO ERROR", fill="white", font=F(10))

    def _draw_default_grid(self):
        bg_style = self.combo_bg_style.get()
        if bg_style == "Nền màu đơn sắc":
            self.canvas.create_rectangle(0, 0, self.canvas_w, self.canvas_h, fill=self.solid_color_hex, outline="")
        else:
            self.canvas.create_rectangle(0, 0, self.canvas_w, self.canvas_h, fill="#181825", outline="")
        
        for i in range(1, 4):
            vx = (self.canvas_w / 4) * i
            self.canvas.create_line(vx, 0, vx, self.canvas_h, fill="#313244", dash=(2, 2))
            hy = (self.canvas_h / 4) * i
            self.canvas.create_line(0, hy, self.canvas_w, hy, fill="#313244", dash=(2, 2))

        self.canvas.create_text(
            self.canvas_w/2,
            self.canvas_h/2,
            text="AI PREVIEW SCREEN (16:9 - 1920x1080)\n[Nạp video hoặc thêm chữ/watermark]",
            fill="#7F849C",
            font=F(12, "bold"),
            justify="center"
        )

    # --- CANVAS MOUSE INTERACTIONS ---
    def on_canvas_press(self, event):
        mouse_x = event.x
        mouse_y = event.y

        self.dragging = False
        self.selected_layer_idx = None

        for idx in range(len(self.layers) - 1, -1, -1):
            layer = self.layers[idx]
            cx = layer["x"] * self.scale
            cy = layer["y"] * self.scale

            if layer["type"] == "text":
                c_size = max(10, int(layer["size"] * self.scale))
                text_len = len(layer["text"])
                w_approx = text_len * c_size * 0.55
                h_approx = c_size

                if (cx - w_approx/2 - 10 <= mouse_x <= cx + w_approx/2 + 10 and
                    cy - h_approx/2 - 10 <= mouse_y <= cy + h_approx/2 + 10):
                    self.selected_layer_idx = idx
                    self.dragging = True
                    self.drag_offset_x = (mouse_x / self.scale) - layer["x"]
                    self.drag_offset_y = (mouse_y / self.scale) - layer["y"]
                    break

            elif layer["type"] == "watermark":
                wm_w = layer["w"] * self.scale
                wm_h = layer["h"] * self.scale

                if (cx - 10 <= mouse_x <= cx + wm_w + 10 and
                    cy - 10 <= mouse_y <= cy + wm_h + 10):
                    self.selected_layer_idx = idx
                    self.dragging = True
                    self.drag_offset_x = (mouse_x / self.scale) - layer["x"]
                    self.drag_offset_y = (mouse_y / self.scale) - layer["y"]
                    break

        self.redraw_canvas()
        self.update_layer_list()
        self.show_properties_panel()

    def on_canvas_drag(self, event):
        if not self.dragging or self.selected_layer_idx is None:
            return

        layer = self.layers[self.selected_layer_idx]
        new_x = int((event.x / self.scale) - self.drag_offset_x)
        new_y = int((event.y / self.scale) - self.drag_offset_y)

        if layer["type"] == "text":
            layer["x"] = max(0, min(1920, new_x))
            layer["y"] = max(0, min(1080, new_y))
        else:
            layer["x"] = max(-layer["w"], min(1920, new_x))
            layer["y"] = max(-layer["h"], min(1080, new_y))

        self.redraw_canvas()
        self.show_properties_panel()

    def on_canvas_release(self, event):
        self.dragging = False

    def on_canvas_double_click(self, event):
        if self.selected_layer_idx is None:
            return
        
        layer = self.layers[self.selected_layer_idx]
        if layer["type"] == "text":
            dialog = ctk.CTkInputDialog(text="Sửa nội dung Chữ:", title="Chỉnh sửa Chữ")
            new_text = dialog.get_input()
            if new_text is not None and new_text.strip():
                layer["text"] = new_text
                self.redraw_canvas()
                self.update_layer_list()
                self.show_properties_panel()

    # --- BATCH COMPILATION EXECUTOR ---
    def stop_compilation(self):
        if self.is_compiling:
            self.update_log("🛑 Đang gửi yêu cầu dừng biên dịch...")
            self.stop_event.set()
            self.btn_stop.configure(state="disabled", text="ĐANG HUỶ...")

    def start_compilation(self):
        if self.is_compiling:
            return

        if not self.video_paths:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn video đầu vào con trước!")
            return

        # Output folder default
        out_dir = self.output_dir
        if not out_dir:
            current_workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            out_dir = os.path.join(current_workspace_dir, "outputs", "YouTube")

        try:
            min_m = float(self.spin_min.get())
            max_m = float(self.spin_max.get())
            min_s = int(min_m * 60)
            max_s = int(max_m * 60)
            if min_s >= max_s or min_s <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi cấu hình", "Thời lượng nhập vào không hợp lệ!")
            return

        # Prepare parameters
        self.is_compiling = True
        self.stop_event.clear()
        self.progress_bar.set(0.0)
        self.lbl_status.configure(text="Đang xử lý...", text_color=ORG)
        self.update_log("🚀 Khởi tạo tiến trình biên tập và ghép nối video hàng loạt...")

        # Disable buttons
        self.btn_compile.configure(state="disabled", fg_color="#94A3B8")
        self.btn_stop.configure(state="normal", text="🛑 DỪNG")
        self.btn_load_dir.configure(state="disabled")
        self.btn_load_files.configure(state="disabled")
        self.btn_intro.configure(state="disabled")
        self.btn_outro.configure(state="disabled")
        self.btn_bgm.configure(state="disabled")
        self.btn_out.configure(state="disabled")

        # Run compilation in worker thread
        threading.Thread(
            target=self.compiler_worker,
            args=(out_dir, min_s, max_s),
            daemon=True
        ).start()

    def compiler_worker(self, out_dir, min_s, max_s):
        try:
            # Extract overlays
            text_overlays = []
            watermarks = []

            for layer in self.layers:
                if layer["type"] == "text":
                    text_overlays.append({
                        "text": layer["text"],
                        "x": layer["x"],
                        "y": layer["y"],
                        "size": layer["size"],
                        "color": layer["color"],
                        "border_color": layer["border_color"],
                        "font_path": layer["font_path"],
                        "angle": layer.get("angle", 0),
                        "stroke_width": layer.get("stroke_width", 3),
                        "bg_box_enabled": layer.get("bg_box_enabled", False),
                        "bg_box_color": layer.get("bg_box_color", "#000000"),
                        "bg_box_opacity": layer.get("bg_box_opacity", 0.6),
                        "shadow_enabled": layer.get("shadow_enabled", False),
                        "shadow_color": layer.get("shadow_color", "#000000"),
                        "shadow_offset": layer.get("shadow_offset", 4)
                    })
                elif layer["type"] == "watermark":
                    watermarks.append({
                        "path": layer["path"],
                        "x": layer["x"],
                        "y": layer["y"],
                        "w": layer["w"],
                        "h": layer["h"],
                        "opacity": layer["opacity"]
                    })

            def progress_cb(status_text, progress_val):
                self.after(0, lambda: self.lbl_status.configure(text=status_text))
                self.after(0, lambda: self.progress_bar.set(progress_val))
                self.update_log(status_text)

            style_sel = self.combo_bg_style.get()
            if style_sel == "Nền màu đơn sắc":
                bg_style = "solid"
            elif style_sel == "Nền ảnh/video tùy chọn":
                bg_style = "custom"
            else:
                bg_style = "blur"

            custom_bg_val = getattr(self, "custom_bg_path", None)
            if bg_style == "custom" and custom_bg_val:
                active_dyn_bg = custom_bg_val
            else:
                active_dyn_bg = getattr(self, "dyn_bg_path", None)

            # Get target resolution
            choice = self.combo_res.get()
            if "1920x1080" in choice:
                w, h = 1920, 1080
            else:
                w, h = 1280, 720

            # Parse start index safely
            try:
                start_idx = int(self.entry_thumb_start_idx.get())
            except:
                start_idx = 63

            # Call rendering library
            results = compile_videos_batch(
                video_paths=self.video_paths,
                output_dir=out_dir,
                min_duration=min_s,
                max_duration=max_s,
                shuffle=self.shuffle_var.get(),
                text_overlays=text_overlays,
                watermarks=watermarks,
                progress_callback=progress_cb,
                stop_event=self.stop_event,
                intro_path=None,
                outro_path=None,
                bgm_path=self.bgm_path,
                bgm_volume=float(self.slider_bgm_vol.get()),
                bg_style=bg_style,
                bg_color=self.solid_color_hex,
                normalize_audio=self.norm_audio_var.get(),
                bypass_bgm_copyright=self.bypass_bgm_copyright_var.get(),
                silent_music_path=self.silent_bgm_path,
                width=w,
                height=h,
                auto_make_thumbnail=self.auto_thumb_var.get(),
                thumbnail_title_template=self.entry_thumb_temp.get(),
                thumbnail_start_index=start_idx,
                speed=float(self.combo_speed.get().replace("x", "")),
                voice_effect=self.combo_voice.get(),
                dyn_bg_path=active_dyn_bg,
                thumbnail_border_color=self.thumbnail_border_color,
                thumbnail_text_color=self.thumbnail_text_color,
                custom_thumbnail_path=self.custom_thumbnail_path,
                thumbnail_font_size=self.thumbnail_font_size,
                thumbnail_banner_color=self.thumbnail_banner_color,
                thumbnail_frame_offsets=self.thumbnail_frame_offsets
            )

            self.update_log(f"✅ Hoàn thành ghép {len(results)} videos YouTube tại: {out_dir}")
            for path in results:
                self.update_log(f"   - {os.path.basename(path)}")
            
            # Copy log file to output directory so the user can easily read it
            try:
                import shutil
                dest_log = os.path.join(out_dir, "yt_compiler_run.log")
                src_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt_compiler_run.log")
                if os.path.exists(src_log):
                    shutil.copy2(src_log, dest_log)
            except Exception as log_err:
                print(f"Failed to copy log to output: {log_err}")

            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self.lbl_status.configure(text="Hoàn tất thành công!", text_color=GRN))
            self.after(0, lambda: messagebox.showinfo("Hoàn tất", f"Đã ghép xong {len(results)} videos YouTube thành công!"))

        except InterruptedError:
            self.update_log("🛑 Tiến trình đã bị huỷ bởi người dùng.")
            self.after(0, lambda: self.lbl_status.configure(text="Đã dừng", text_color=RED))
            self.after(0, lambda: self.progress_bar.set(0.0))
        except Exception as e:
            err_msg = f"❌ Lỗi: {str(e)}"
            self.update_log(err_msg)
            self.after(0, lambda: self.lbl_status.configure(text="Lỗi xảy ra", text_color=RED))
            self.after(0, lambda: messagebox.showerror("Lỗi biên dịch", f"Có lỗi xảy ra: {e}"))
        finally:
            self.is_compiling = False
            self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.btn_compile.configure(state="normal", fg_color=GRN)
        self.btn_stop.configure(state="disabled", text="🛑 DỪNG")
        self.btn_load_dir.configure(state="normal")
        self.btn_load_files.configure(state="normal")
        self.btn_intro.configure(state="normal")
        self.btn_outro.configure(state="normal")
        self.btn_bgm.configure(state="normal")
        self.btn_out.configure(state="normal")

    def load_settings(self):
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compiler_settings.json")
        if os.path.exists(settings_file):
            try:
                import json
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                min_m = data.get("min_duration", "8")
                max_m = data.get("max_duration", "10")
                self.spin_min.delete(0, tk.END)
                self.spin_min.insert(0, str(min_m))
                self.spin_max.delete(0, tk.END)
                self.spin_max.insert(0, str(max_m))
                
                self.shuffle_var.set(data.get("shuffle", False))
                
                bg_style = data.get("bg_style", "Nền mờ (Blurred)")
                self.combo_bg_style.set(bg_style)
                self.on_bg_style_changed(bg_style)
                
                custom_bg = data.get("custom_bg_path", "")
                if custom_bg and os.path.exists(custom_bg):
                    self.custom_bg_path = custom_bg
                    self.lbl_custom_bg.configure(text=os.path.basename(custom_bg), text_color=GRN)
                    ext = os.path.splitext(custom_bg)[1].lower()
                    if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
                        try:
                            self.bg_image_pil = Image.open(custom_bg).convert("RGB")
                        except:
                            pass
                else:
                    self.custom_bg_path = None
                    self.lbl_custom_bg.configure(text="Chưa chọn", text_color=T3)
                
                self.solid_color_hex = data.get("solid_color_hex", "#000000")
                self.btn_solid_color.configure(
                    fg_color=self.solid_color_hex, 
                    text_color="black" if self.is_light_color(self.solid_color_hex) else "white"
                )
                
                bgm = data.get("bgm_path", "")
                if bgm and os.path.exists(bgm):
                    self.bgm_path = bgm
                    self.lbl_bgm.configure(text=os.path.basename(bgm), text_color=GRN)
                else:
                    self.bgm_path = None
                    self.lbl_bgm.configure(text="Chưa chọn", text_color=T3)
                    
                silent_bgm = data.get("silent_bgm_path", "")
                if silent_bgm and os.path.exists(silent_bgm):
                    self.silent_bgm_path = silent_bgm
                    self.lbl_silent_bgm.configure(text=os.path.basename(silent_bgm), text_color=GRN)
                else:
                    self.silent_bgm_path = None
                    self.lbl_silent_bgm.configure(text="Chưa chọn", text_color=T3)
                    
                vol = data.get("bgm_volume", 0.15)
                self.slider_bgm_vol.set(vol)
                self.on_bgm_vol_changed(vol)
                
                intro = data.get("intro_path", "")
                if intro and os.path.exists(intro):
                    self.intro_path = intro
                    self.lbl_intro.configure(text=os.path.basename(intro), text_color=GRN)
                else:
                    self.intro_path = None
                    self.lbl_intro.configure(text="Chưa chọn", text_color=T3)
                    
                outro = data.get("outro_path", "")
                if outro and os.path.exists(outro):
                    self.outro_path = outro
                    self.lbl_outro.configure(text=os.path.basename(outro), text_color=GRN)
                else:
                    self.outro_path = None
                    self.lbl_outro.configure(text="Chưa chọn", text_color=T3)
                    
                self.norm_audio_var.set(data.get("normalize_audio", False))
                self.bypass_bgm_copyright_var.set(data.get("bypass_bgm_copyright", True))
                
                # Load thumbnail configs
                self.auto_thumb_var.set(data.get("auto_make_thumbnail", True))
                self.entry_thumb_temp.delete(0, tk.END)
                self.entry_thumb_temp.insert(0, data.get("thumbnail_title_template", "Tổng Hợp | MukbangChinaFood | Phần {index}"))
                self.entry_thumb_start_idx.delete(0, tk.END)
                self.entry_thumb_start_idx.insert(0, str(data.get("thumbnail_start_index", "1")))
                self.thumbnail_border_color = data.get("thumbnail_border_color", "Cam (#FE640B)")
                self.thumbnail_text_color = data.get("thumbnail_text_color", "Vàng (#FFFF00)")
                self.thumbnail_banner_color = data.get("thumbnail_banner_color", "Trắng (#FFFFFF)")
                self.thumbnail_font_size = data.get("thumbnail_font_size", 44)
                self.thumbnail_frame_offsets = data.get("thumbnail_frame_offsets", [15.0, 33.0, 85.0])
                custom_thumb = data.get("custom_thumbnail_path", "")
                if custom_thumb and os.path.exists(custom_thumb):
                    self.custom_thumbnail_path = custom_thumb
                else:
                    self.custom_thumbnail_path = None
                
                # Load advanced effects
                self.combo_speed.set(data.get("speed", "x1.0"))
                self.combo_voice.set(data.get("voice_effect", "Bình thường"))
                dyn_bg = data.get("dyn_bg_path", "")
                if dyn_bg and os.path.exists(dyn_bg):
                    self.dyn_bg_path = dyn_bg
                    self.lbl_dyn_bg.configure(text=os.path.basename(dyn_bg), text_color=GRN)
                else:
                    self.dyn_bg_path = None
                    self.lbl_dyn_bg.configure(text="Chưa chọn", text_color=T3)

                # Load resolution
                res_val = data.get("resolution", "1280x720 (720p - Siêu nhanh)")
                self.combo_res.set(res_val)
                
                out_dir = data.get("output_dir", "")
                if out_dir and os.path.exists(out_dir):
                    self.output_dir = out_dir
                    self.lbl_out_dir.configure(text=f"Lưu tại: .../{os.path.basename(out_dir)}", text_color=GRN)
                
                self.layers = []
                loaded_layers = data.get("layers", [])
                for layer in loaded_layers:
                    l_type = layer.get("type", "text")
                    if l_type == "text":
                        font_name = layer.get("font_name", "Be Vietnam Pro")
                        self.layers.append({
                            "type": "text",
                            "text": layer.get("text", "Nhập chữ"),
                            "x": layer.get("x", 960),
                            "y": layer.get("y", 540),
                            "font_name": font_name,
                            "font_path": self.FONTS.get(font_name, "/System/Library/Fonts/Helvetica.ttc"),
                            "size": layer.get("size", 50),
                            "color": layer.get("color", "#FFFF00"),
                            "border_color": layer.get("border_color", "#000000"),
                            "angle": layer.get("angle", 0),
                            "stroke_width": layer.get("stroke_width", 3),
                            "bg_box_enabled": layer.get("bg_box_enabled", False),
                            "bg_box_color": layer.get("bg_box_color", "#000000"),
                            "bg_box_opacity": layer.get("bg_box_opacity", 0.6),
                            "shadow_enabled": layer.get("shadow_enabled", False),
                            "shadow_color": layer.get("shadow_color", "#000000"),
                            "shadow_offset": layer.get("shadow_offset", 4)
                        })
                    elif l_type == "watermark":
                        w_path = layer.get("path", "")
                        if os.path.exists(w_path):
                            self.layers.append({
                                "type": "watermark",
                                "path": w_path,
                                "x": layer.get("x", 100),
                                "y": layer.get("y", 100),
                                "w": layer.get("w", 150),
                                "h": layer.get("h", 150),
                                "opacity": layer.get("opacity", 0.8)
                            })
                
                self.selected_layer_idx = None
                self.update_layer_list()
                self.show_properties_panel()
                self.update_log("💾 Đã tự động nạp cấu hình và template từ lần chạy trước.")
            except Exception as e:
                print(f"Failed to load compiler settings: {e}")

    def save_settings(self):
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compiler_settings.json")
        try:
            import json
            layers_data = []
            for layer in self.layers:
                if layer["type"] == "text":
                    layers_data.append({
                        "type": "text",
                        "text": layer["text"],
                        "x": layer["x"],
                        "y": layer["y"],
                        "font_name": layer["font_name"],
                        "size": layer["size"],
                        "color": layer["color"],
                        "border_color": layer["border_color"],
                        "angle": layer.get("angle", 0),
                        "stroke_width": layer.get("stroke_width", 3),
                        "bg_box_enabled": layer.get("bg_box_enabled", False),
                        "bg_box_color": layer.get("bg_box_color", "#000000"),
                        "bg_box_opacity": layer.get("bg_box_opacity", 0.6),
                        "shadow_enabled": layer.get("shadow_enabled", False),
                        "shadow_color": layer.get("shadow_color", "#000000"),
                        "shadow_offset": layer.get("shadow_offset", 4)
                    })
                elif layer["type"] == "watermark":
                    layers_data.append({
                        "type": "watermark",
                        "path": layer["path"],
                        "x": layer["x"],
                        "y": layer["y"],
                        "w": layer["w"],
                        "h": layer["h"],
                        "opacity": layer["opacity"]
                    })
            
            data = {
                "min_duration": self.spin_min.get(),
                "max_duration": self.spin_max.get(),
                "shuffle": self.shuffle_var.get(),
                "bg_style": self.combo_bg_style.get(),
                "custom_bg_path": self.custom_bg_path or "",
                "solid_color_hex": self.solid_color_hex,
                "bgm_path": self.bgm_path or "",
                "silent_bgm_path": self.silent_bgm_path or "",
                "bgm_volume": float(self.slider_bgm_vol.get()),
                "intro_path": self.intro_path or "",
                "outro_path": self.outro_path or "",
                "normalize_audio": self.norm_audio_var.get(),
                "bypass_bgm_copyright": self.bypass_bgm_copyright_var.get(),
                "auto_make_thumbnail": self.auto_thumb_var.get(),
                "thumbnail_title_template": self.entry_thumb_temp.get(),
                "thumbnail_start_index": self.entry_thumb_start_idx.get(),
                "thumbnail_border_color": self.thumbnail_border_color,
                "thumbnail_text_color": self.thumbnail_text_color,
                "thumbnail_banner_color": self.thumbnail_banner_color,
                "thumbnail_font_size": self.thumbnail_font_size,
                "thumbnail_frame_offsets": self.thumbnail_frame_offsets,
                "custom_thumbnail_path": self.custom_thumbnail_path or "",
                "speed": self.combo_speed.get(),
                "voice_effect": self.combo_voice.get(),
                "dyn_bg_path": getattr(self, "dyn_bg_path", None) or "",
                "resolution": self.combo_res.get(),
                "output_dir": self.output_dir or "",
                "layers": layers_data
            }
            
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self.update_log("💾 Cấu hình và thiết kế template đã được lưu thành công!")
            messagebox.showinfo("Lưu cấu hình", "Đã lưu toàn bộ cấu hình giao diện và thiết kế template thành công!")
        except Exception as e:
            self.update_log(f"❌ Không thể lưu cấu hình: {e}")
            messagebox.showerror("Lỗi lưu", f"Lỗi khi lưu cấu hình: {e}")
