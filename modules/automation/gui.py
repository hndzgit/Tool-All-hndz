"""
Video AI Pro — macOS 26 Style, Tiếng Việt
Dùng CTkButton thật thay vì Canvas buttons (sửa lỗi nút bấm).
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import os, sys, threading, time, platform, concurrent.futures
from PIL import Image, ImageDraw, ImageFont
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from utils.sync_and_sub import process_video_pipeline
from utils.blurrer import wrap_text
import config.config as cfg

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ── Màu sắc macOS 26 Liquid Glass (Light / Dark) ────────────────────────────
BG      = ("#f2f2f7", "#000000")   # Nền dưới cùng
BG2     = ("#ffffff", "#1c1c1e")   # Nền nổi (Floating Panel)
BG3     = ("#e5e5ea", "#2c2c2e")   # Thẻ nội dung (Cards)
BG4     = ("#d1d1d6", "#3a3a3c")   # Ô nhập liệu/Log
BORDER  = ("#c7c7cc", "#48484a")   # Viền giả kính
SEL     = ("#007aff", "#0a84ff")   # Xanh dương Apple
HOVER   = ("#d1d1d6", "#3a3a3c")   
T1      = ("#000000", "#ffffff")   # Chữ chính
T2      = ("#3c3c43", "#ebebf5")   # Chữ thứ cấp
T3      = ("#8e8e93", "#8e8e93")   # Chữ mờ
GRN     = ("#34c759", "#30d158")   # Xanh lá
ORG     = ("#ff9500", "#ff9f0a")   # Cam
RED     = ("#ff3b30", "#ff375f")   # Đỏ
PUR     = ("#af52de", "#bf5af2")   # Tím
TL_RED  = ("#ff5f57", "#ff5f57")   
TL_YEL  = ("#febc2e", "#febc2e")   
TL_GRN  = ("#28c840", "#28c840")   

def F(sz=13, w="normal"): return ctk.CTkFont("SF Pro Display", sz, w)
def FM(sz=11): return ctk.CTkFont("SF Mono", sz)


# ══════════════════════════════════════════════════════════════
# JOB ROW
# ══════════════════════════════════════════════════════════════
class JobRow(ctk.CTkFrame):
    def __init__(self, master, full_path, remove_cb=None, **kw):
        super().__init__(master, fg_color=BG3, corner_radius=14,
                         border_color=BORDER, border_width=1, **kw)
        self.full_path = full_path
        name = os.path.basename(full_path)
        short = name if len(name) <= 42 else name[:39] + "…"

        ctk.CTkButton(
            self, text="✕", width=22, height=22,
            fg_color="transparent", hover_color="#4A1010",
            text_color=T3, corner_radius=6, font=F(11),
            command=lambda: remove_cb(full_path) if remove_cb else None
        ).pack(side="left", padx=(8, 4), pady=10)

        ctk.CTkLabel(self, text="🎬", font=F(16)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(self, text=short, anchor="w", font=F(12), text_color=T1
                     ).pack(side="left", fill="x")

        self.lbl_st = ctk.CTkLabel(
            self, text="Chờ", width=80, anchor="center",
            font=F(11), text_color=T3, fg_color=BG4, corner_radius=7
        )
        self.lbl_st.pack(side="right", padx=(4, 10), pady=10)

        # Nút Mở File trong Finder / Explorer
        self.btn_reveal = ctk.CTkButton(
            self, text="📂", width=22, height=22,
            fg_color="transparent", hover_color=HOVER,
            text_color=T2, corner_radius=6, font=F(12),
            command=self.reveal_in_finder
        )
        self.btn_reveal.pack(side="right", padx=(4, 0), pady=10)

        self.bar = ctk.CTkProgressBar(
            self, height=3, corner_radius=2, fg_color=BG4, progress_color=SEL
        )
        self.bar.set(0)
        self.bar.pack(side="right", padx=8, fill="x", expand=True)

    def reveal_in_finder(self):
        import subprocess
        if os.path.exists(self.full_path):
            if platform.system() == "Darwin":
                subprocess.run(["open", "-R", self.full_path])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", os.path.normpath(self.full_path)])

    def update_progress(self, v):
        try:
            if not self.winfo_exists(): return
            self.bar.set(v)
            self.bar.configure(progress_color=GRN if v >= 1.0 else SEL)
        except Exception:
            pass

    def update_status(self, text, color=T2):
        try:
            if not self.winfo_exists(): return
            self.lbl_st.configure(text=text, text_color=color)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════
class VideoAutomationApp(ctk.CTkFrame):
    def __init__(self, master=None, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self.selected_files = []
        self.completed_files = set()
        self.completed_job_rows = []  # Lưu lịch sử hàng hoàn thành để giới hạn số lượng trên UI
        self.job_widgets = {}
        self.pause_event = threading.Event()
        self.pause_event.set() # Bật cờ cho phép chạy mặc định
        self.custom_output_dir = cfg.OUTPUT_DIR
        self._nav_btns = {}
        # switch refs (created lazily in settings panel)
        self.switch_amf = self.switch_sub = self.switch_voice = self.switch_keep_bgm = None
        self.vbee_voice_options = {}
        self.combo_vbee_voice = None
        self.btn_test_voice = None
        
        live_cfg = cfg.load_settings()
        self.main_order_image_path = live_cfg.get("order_image_path", "")
        self.sub_source_var = ctk.StringVar(value=live_cfg.get("sub_source", "audio"))
        self.sub_source_var.trace_add("write", lambda *args: cfg.save_settings({"sub_source": self.sub_source_var.get()}))
        
        self.theme_menu = None
        self.lbl_output_dir_display = None
        self._setup_ui()
        self.load_queue_state()

    def save_queue_state(self):
        """Lưu danh sách file đang dở dang và file đã hoàn thành vào queue.json"""
        if not hasattr(cfg, 'QUEUE_FILE'): return
        try:
            state = {
                "selected": self.selected_files,
                "completed": list(self.completed_files)
            }
            with open(cfg.QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Lắp ráp trí nhớ bị lỗi: {e}")

    def load_queue_state(self):
        """Khôi phục Ký ức Queue khi khởi động App"""
        if not hasattr(cfg, 'QUEUE_FILE') or not os.path.exists(cfg.QUEUE_FILE): return
        try:
            with open(cfg.QUEUE_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return  # File rỗng, bỏ qua
            state = json.loads(content)
            
            # Lọc những file vẫn còn tồn tại thật sự trên ổ cứng
            s_files = [f for f in state.get("selected", []) if os.path.exists(f)]
            c_files = set([f for f in state.get("completed", []) if f in s_files])
            
            if s_files:
                self.selected_files = s_files
                self.completed_files = c_files
                self._show_joblist()
                self.log(f"🧠 Đã phục hồi Ký Ức: {len(s_files)} video đang làm dở!")
                self.update_global_progress()
                
        except Exception as e:
            print(f"Lỗi đọc Ký ức Queue: {e}")

    def update_global_progress(self):
        """Cập nhật phần trăm tiến trình chung trên UI"""
        if not hasattr(self, 'progress_global') or not self.progress_global.winfo_exists():
            return
        n = len(self.selected_files)
        c = len(self.completed_files)
        if n > 0:
            pct = c / n
            self.progress_global.set(pct)
            if hasattr(self, 'lbl_global_pct') and self.lbl_global_pct.winfo_exists():
                self.lbl_global_pct.configure(text=f"{int(pct * 100)}% ({c}/{n})")
        else:
            self.progress_global.set(0)
            if hasattr(self, 'lbl_global_pct') and self.lbl_global_pct.winfo_exists():
                self.lbl_global_pct.configure(text="0% (0/0)")

    def create_active_job_row(self, fp, p_mode):
        """Tạo động widget JobRow cho video đang được xử lý trên UI chính"""
        if not hasattr(self, 'scroll_jobs') or not self.scroll_jobs.winfo_exists():
            return
            
        # Ẩn nhãn thông báo "Chưa có video..." nếu đang hiển thị
        if hasattr(self, 'lbl_no_active_jobs') and self.lbl_no_active_jobs.winfo_exists():
            self.lbl_no_active_jobs.pack_forget()
            
        # Tạo widget mới nếu chưa tồn tại
        if fp not in self.job_widgets:
            row = JobRow(self.scroll_jobs, fp, self.remove_job)
            row.pack(fill="x", pady=3, padx=2)
            self.job_widgets[fp] = row
            
        self.job_widgets[fp].update_status(f"Đang xử lý {p_mode[:12]}…", ORG)

    def update_job_progress(self, fp, pct):
        """Cập nhật tiến trình chạy của riêng từng video"""
        job = self.job_widgets.get(fp)
        if job:
            job.update_progress(pct / 100)

    def finish_job(self, fp, status_text, color):
        """Đánh dấu hoàn thành cho video và dọn dẹp lịch sử cũ để tránh lag"""
        job = self.job_widgets.get(fp)
        if job:
            job.update_progress(1.0)
            job.update_status(status_text, color)
            
            # Ghi nhận vào hàng đợi lịch sử
            if fp not in self.completed_job_rows:
                self.completed_job_rows.append(fp)
                
            # Duy trì tối đa 5 hàng đã xong gần nhất để giải phóng tài nguyên
            if len(self.completed_job_rows) > 5:
                oldest_fp = self.completed_job_rows.pop(0)
                oldest_widget = self.job_widgets.get(oldest_fp)
                if oldest_widget and oldest_widget.winfo_exists():
                    oldest_widget.destroy()
                if oldest_fp in self.job_widgets:
                    del self.job_widgets[oldest_fp]

    def update_dashboard_counter(self):
        """Cập nhật đếm số lượng video hoàn thành trên UI"""
        if hasattr(self, 'lbl_job_count') and self.lbl_job_count.winfo_exists():
            n = len(self.selected_files)
            c = len(self.completed_files)
            self.lbl_job_count.configure(text=f"Đã hoàn thành {c}/{n} video")
        self.update_global_progress()

    def _setup_ui(self):
        self.grid_rowconfigure(2, weight=1) # Main content takes the height
        self.grid_columnconfigure(0, weight=1) # One column layout
        self._build_titlebar()
        self._build_topbar()    # builds nav buttons horizontally
        self._build_main()      # creates _title_lbl and _body
        self._build_statusbar()
        self._nav("pipeline")   # safe to call now that all widgets exist

    # ─── TITLEBAR ────────────────────────────────────────────────
    def _build_titlebar(self):
        bar = ctk.CTkFrame(self, height=38, fg_color=BG, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)



        ctk.CTkLabel(bar, text="Video AI Pro", font=F(13), text_color=T3).pack(expand=True)

    # ─── TOPBAR (Replaced Sidebar) ───────────────────────────────
    def _build_topbar(self):
        tb = ctk.CTkFrame(self, height=45, fg_color=BG2, corner_radius=0)
        tb.grid(row=1, column=0, sticky="ew")
        
        scroll = ctk.CTkScrollableFrame(tb, height=35, fg_color="transparent",
                                         orientation="horizontal")
        scroll.pack(fill="x", expand=True, padx=10, pady=2)

        def nav(label, page):
            btn = ctk.CTkButton(
                scroll, text=f"{label}",
                fg_color="transparent", hover_color=HOVER,
                text_color=T2, corner_radius=8,
                font=F(12, "bold"), height=30,
                command=lambda p=page: self._nav(p)
            )
            btn.pack(side="left", padx=5)
            self._nav_btns[page] = btn

        nav("▶ Pipeline Chính",   "pipeline")
        nav("⚙️ Cài Đặt",          "settings")
        nav("👁 Phụ Đề",           "preview")
        nav("🔑 API Keys",         "api")
        nav("💧 Watermark",        "watermark")
        nav("🛡 Chống Reup",       "antireup")
        nav("📱 Dọc 9:16",         "vertical")
        nav("🖼 Ảnh Bìa",          "thumbnail")

        # Initial nav called from _setup_ui after _build_main() is ready

    def _nav(self, page):
        actions = {
            "pipeline": self._show_pipeline,
            "settings": self._show_settings,
            "preview":  self._show_preview_settings,
            "api":      self._show_api_settings,
            "watermark":self._show_watermark_settings,
            "antireup": self._show_anti_reup_settings,
            "vertical": self._show_vertical_settings,
            "thumbnail": self._show_thumbnail_settings,
        }
        # Guard: skip if UI not fully built yet
        if not hasattr(self, "_title_lbl"):
            return
        # Update nav highlight
        for p, b in self._nav_btns.items():
            if p == page:
                b.configure(fg_color=SEL, text_color=T1, hover_color=SEL)
            else:
                b.configure(fg_color="transparent", text_color=T2, hover_color=HOVER)

        if page == "pipeline" and hasattr(self, "qset"):
            self.qset.grid()
        elif hasattr(self, "qset"):
            self.qset.grid_remove()

        # Ẩn nút "Bắt Đầu" ở các Tab không liên quan để tránh nhầm lẫn
        if hasattr(self, "btn_start"):
            if page == "pipeline":
                self.btn_start.pack(side="left")
            else:
                self.btn_start.pack_forget()

        if page in actions:
            # Xoá nội dung cũ
            for widget in self._body.winfo_children():
                widget.destroy()
            
            # Gắn lại frame với khoảng đệm để chuẩn bị hiệu ứng Slide-up
            self._body.grid_configure(pady=(30, 0))
            
            # Render nội dung mới
            actions[page]()
            
            # Hiệu ứng Apple Slide-Up (60fps)
            def slide_up(current_pad):
                if current_pad > 0:
                    next_pad = max(0, int(current_pad * 0.6) - 1)
                    if hasattr(self, "_body") and self._body.winfo_exists():
                        self._body.grid_configure(pady=(next_pad, 0))
                        self.after(16, lambda: slide_up(next_pad))
                else:
                    if hasattr(self, "_body") and self._body.winfo_exists():
                        self._body.grid_configure(pady=(0, 0))
            
            slide_up(30)

    # ─── MAIN CONTENT ────────────────────────────────────────────
    def _build_main(self):
        # Biến Main Panel thành thẻ Floating với Border Glassmorphism
        self._main = ctk.CTkFrame(self, fg_color=BG2, corner_radius=16, border_width=1, border_color=BORDER)
        self._main.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        self._main.grid_rowconfigure(1, weight=0) # qset (cố định)
        self._main.grid_rowconfigure(2, weight=1) # _body (chiếm phần còn lại)
        self._main.grid_rowconfigure(3, weight=0) # separator
        self._main.grid_rowconfigure(4, weight=0) # log_hdr
        self._main.grid_rowconfigure(5, weight=0) # logs
        self._main.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self._main, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=26, pady=(20, 10))
        hdr.grid_columnconfigure(0, weight=1)

        self._title_lbl = ctk.CTkLabel(hdr, text="Xử Lý Video",
                                        font=F(26, "bold"), text_color=T1)
        self._title_lbl.grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")
        
        self.btn_start = ctk.CTkButton(
            btn_frame, text="▶ Bắt Đầu", command=self.start_pipeline,
            fg_color=GRN, hover_color="#25A83A",
            text_color="black", corner_radius=20,
            font=F(14, "bold"), height=36, width=130
        )
        self.btn_start.pack(side="left")
        
        self.lbl_dashboard = ctk.CTkLabel(hdr, text="")  # compat

        # Khung cài đặt nhanh (Quick Settings)
        self.vbee_voice_options_vi = {
            "Xoay Vòng Ngẫu Nhiên (Random)": "vbee:random",
            "Ngọc Huyền 48k (Nữ HN)":  "vbee:hn_female_ngochuyen_full_48k-fhg",
            "Minh Quân YT 24k (Nam HN)": "vbee:hn_male_minhquan_yt_24k-pre",
            "Mạnh Dũng 24k (Nam HN)":   "vbee:hn_male_manhdung_full_24k-st",
            "Ngọc Huyền 24k (Nữ HN)":  "vbee:hn_female_ngochuyen_full_24k-st",
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
        self.vbee_voice_options_en = {
            "Chị Google (Tiếng Anh - Free Fallback)": "gtts:en",
            "Maddie (Nữ Mỹ - Vbee)": "vbee:en_female_maddie",
            "Lucas (Nam Mỹ - Vbee)": "vbee:en_male_lucas"
        }
        self.vbee_voice_options = self.vbee_voice_options_vi
        
        self.google_voice_options = {
            "Chị Google (Tiếng Việt)": "gtts:vi",
            "Chị Google (Tiếng Anh - US)": "gtts:en",
            "Chị Google (Tiếng Trung)": "gtts:zh-CN",
            "Chị Google (Tiếng Nhật)": "gtts:ja"
        }
        
        self.qset = ctk.CTkFrame(self._main, fg_color="transparent")
        self.qset.grid(row=1, column=0, sticky="ew", padx=26, pady=(0, 4))
        
        # Biến trạng thái 2 Giai Đoạn
        self.processing_mode = ctk.StringVar(value="Bình Thường (Tự Động)")
        self.phase2_audio_dir = ctk.StringVar(value="")

        # Hàng 1: Các nút gạt (Pill Design)
        sw_row = ctk.CTkFrame(self.qset, fg_color=BG3, corner_radius=16, border_width=1, border_color=BORDER)
        sw_row.pack(fill="x", pady=(0, 10))
        
        def add_sw(label, attr, default=True, command=None):
            f = ctk.CTkFrame(sw_row, fg_color="transparent")
            f.pack(side="left", expand=True, pady=8)
            s = ctk.CTkSwitch(f, text=label, font=F(12, "bold"), text_color=T1,
                              switch_width=36, switch_height=20, progress_color=SEL, command=command)
            if default: s.select()
            s.pack(side="left")
            setattr(self, attr, s)

        add_sw("Tăng Tốc GPU", "switch_amf", default=cfg.ENABLE_AMF)
        add_sw("Hiện Phụ Đề", "switch_sub", default=cfg.ENABLE_SUB)
        add_sw("Lồng Tiếng", "switch_voice", default=cfg.ENABLE_VOICE)
        add_sw("Giữ Nhạc Nền", "switch_keep_bgm", default=cfg.KEEP_BGM)
        add_sw("Che Sub Gốc (Blur)", "switch_blur", default=cfg.ENABLE_BLUR)

        # Nút Lưu Cấu Hình Nhanh
        self.btn_save_quick = ctk.CTkButton(
            sw_row, text="💾 Lưu Cấu Hình",
            fg_color=SEL, hover_color="#0066D6", text_color=T1,
            corner_radius=8, font=F(11, "bold"), height=26, width=110,
            command=self.save_quick_settings
        )
        self.btn_save_quick.pack(side="right", padx=(10, 16), pady=8)

        # Hàng 2: Chọn nguồn và giọng đọc
        self.v_row = ctk.CTkFrame(self.qset, fg_color=BG3, corner_radius=16, border_width=1, border_color=BORDER)
        self.v_row.pack(fill="x")
        
        ctk.CTkLabel(self.v_row, text="🎙 Nguồn:", font=F(12, "bold"), text_color=T2).pack(side="left", padx=(16, 4), pady=8)
        
        self.seg_tts_engine = ctk.CTkSegmentedButton(
            self.v_row, values=["Vbee (VIP)", "Google (Free)"],
            selected_color=SEL, selected_hover_color="#0066D6",
            unselected_color=BG4, unselected_hover_color=HOVER,
            text_color=T1, font=F(11, "bold"), height=26,
            command=self.on_engine_change
        )
        self.seg_tts_engine.pack(side="left", padx=(0, 10))
        
        cur = cfg.VBEE_VOICE
        self.seg_tts_engine.set("Google (Free)" if cur.startswith("gtts:") else "Vbee (VIP)")
        
        self.combo_vbee_voice = ctk.CTkOptionMenu(
            self.v_row, values=["Đang tải..."],
            command=self.save_voice_setting,
            fg_color=BG4, button_color=BG2, button_hover_color=HOVER,
            dropdown_fg_color=BG3, dropdown_hover_color=HOVER,
            text_color=T1, font=F(12), corner_radius=8, width=160, height=28
        )
        self.combo_vbee_voice.pack(side="left", padx=(0, 12), fill="x", expand=True)
        self.update_voice_dropdown()
        
        self.btn_test_voice = ctk.CTkButton(
            self.v_row, text="▶ Nghe Thử", command=self.play_test_voice,
            fg_color=BG4, hover_color=HOVER, text_color=ORG,
            corner_radius=8, font=F(12, "bold"), height=28, width=100
        )
        self.btn_test_voice.pack(side="right", padx=(0, 10))

        # Hàng 3: Chọn Chế Độ Phân Đoạn (2-Phase Workflow)
        self.p_row = ctk.CTkFrame(self.qset, fg_color=BG3, corner_radius=16, border_width=1, border_color=BORDER)
        self.p_row.pack(fill="x", pady=(10, 0))
        
        ctk.CTkLabel(self.p_row, text="⚙️ Tiến Trình Chạy:", font=F(12, "bold"), text_color=T2).pack(side="left", padx=(16, 8), pady=8)
        
        self.combo_processing_mode = ctk.CTkOptionMenu(
            self.p_row, 
            values=["Tự Động 100% (Tất Cả Trong Một)", "Chỉ Tách Video Mờ & Phụ Đề (Giai Đoạn 1)", "Chỉ Ghép Âm Thanh Mới (Giai Đoạn 2)"],
            command=self.on_processing_mode_dropdown_change,
            fg_color=BG4, button_color=BG2, button_hover_color=HOVER,
            dropdown_fg_color=BG3, dropdown_hover_color=HOVER,
            text_color=T1, font=F(12, "bold"), corner_radius=8, width=280, height=28
        )
        saved_mode = getattr(cfg, "PROCESSING_MODE", "Tự Động 100% (Tất Cả Trong Một)")
        self.combo_processing_mode.set(saved_mode)
        self.combo_processing_mode.pack(side="left", padx=(0, 12))
        self.after(200, lambda: self.on_processing_mode_dropdown_change(saved_mode))
        
        # Thư mục lưu xuất
        self.btn_change_out = ctk.CTkButton(
            self.p_row, text="📁 Nơi Lưu Video Xuất", command=self.change_output_dir,
            fg_color=BG4, hover_color=HOVER, text_color=T2,
            corner_radius=8, font=F(12), height=28, width=160
        )
        self.btn_change_out.pack(side="right", padx=(10, 10))
        
        # Hàng 3.5: Chọn Tên Sản Phẩm Chỉ Định (Định hướng AI)
        self.prod_row = ctk.CTkFrame(self.qset, fg_color=BG3, corner_radius=16, border_width=1, border_color=BORDER)
        self.prod_row.pack(fill="x", pady=(10, 0))
        
        ctk.CTkLabel(self.prod_row, text="🏷️ Tên Sản Phẩm:", font=F(12, "bold"), text_color=T2).pack(side="left", padx=(16, 8), pady=8)
        
        self.specified_product_name = ctk.StringVar(value=getattr(cfg, "SPECIFIED_PRODUCT_NAME", ""))
        self.entry_product_name = ctk.CTkEntry(
            self.prod_row, 
            placeholder_text="Nhập tên sản phẩm để AI nhận diện chuẩn xác (ví dụ: Bàn phím Attack Shark M87)...",
            textvariable=self.specified_product_name,
            font=F(12), fg_color=BG, border_width=0, height=28
        )
        self.entry_product_name.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def save_product():
            name = self.specified_product_name.get().strip()
            cfg.save_settings({"specified_product_name": name})
            setattr(cfg, "SPECIFIED_PRODUCT_NAME", name)
            btn_save_prod.configure(text="✅ Đã Lưu", fg_color=GRN, text_color="black")
            self.after(1500, lambda: btn_save_prod.configure(text="💾 Lưu Tên", fg_color=SEL, text_color=T1))
            self.log(f"🏷️ Đã găm tên sản phẩm: {name if name else '(Tự Động Nhận Diện)'}")

        btn_save_prod = ctk.CTkButton(
            self.prod_row, text="💾 Lưu Tên", command=save_product,
            fg_color=SEL, hover_color="#0066D6", text_color=T1,
            corner_radius=8, font=F(12, "bold"), height=28, width=100
        )
        btn_save_prod.pack(side="right", padx=(0, 10))
        
        # Hàng 4: Chọn Nơi Lưu SRT và Nhập MP3 (Chỉ hiện khi bật Cứu Hộ)
        self.rescue_row = ctk.CTkFrame(self.qset, fg_color=BG3, corner_radius=16, border_width=1, border_color=BORDER)
        
        self.rescue_srt_dir = ctk.StringVar(value=cfg.RESCUE_SRT_DIR)
        self.rescue_mp3_dir = ctk.StringVar(value=cfg.RESCUE_MP3_DIR)
        
        ctk.CTkLabel(self.rescue_row, text="📥 Lưu SRT:", font=F(12, "bold"), text_color=T2).pack(side="left", padx=(16, 4), pady=8)
        ctk.CTkLabel(self.rescue_row, textvariable=self.rescue_srt_dir, font=F(11), text_color=ORG, width=150, fg_color=BG4, corner_radius=4).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(self.rescue_row, text="Chọn", width=50, height=24, fg_color=PUR, command=lambda: self._ask_dir(self.rescue_srt_dir, "rescue_srt_dir")).pack(side="left", padx=(0, 16))
        
        ctk.CTkLabel(self.rescue_row, text="📤 Nạp Âm Thanh:", font=F(12, "bold"), text_color=T2).pack(side="left", padx=(0, 4), pady=8)
        ctk.CTkLabel(self.rescue_row, textvariable=self.rescue_mp3_dir, font=F(11), text_color=GRN, width=150, fg_color=BG4, corner_radius=4).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(self.rescue_row, text="Chọn", width=50, height=24, fg_color=PUR, command=lambda: self._ask_dir(self.rescue_mp3_dir, "rescue_mp3_dir")).pack(side="left", padx=(0, 10))

        # Body
        self._body = ctk.CTkFrame(self._main, fg_color="transparent")
        self._body.grid(row=2, column=0, sticky="nsew", padx=16)
        self._body.grid_rowconfigure(0, weight=1)
        self._body.grid_columnconfigure(0, weight=1)

        self._show_dropzone()

        # Log separator
        ctk.CTkFrame(self._main, fg_color=BORDER, height=1).grid(
            row=3, column=0, sticky="ew", padx=16)

        log_hdr = ctk.CTkFrame(self._main, fg_color="transparent", height=26)
        log_hdr.grid(row=4, column=0, sticky="ew", padx=26, pady=(12, 0))
        ctk.CTkLabel(log_hdr, text="Nhật Ký Hệ Thống", font=F(11, "bold"), text_color=T3
                     ).pack(side="left")

        self.textbox_logs = ctk.CTkTextbox(
            self._main, state="disabled", wrap="word",
            font=FM(11), height=110,
            fg_color=BG, text_color=GRN,
            corner_radius=12, border_width=1, border_color=BORDER,
            scrollbar_button_color=BORDER
        )
        self.textbox_logs.grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 16))
        self.log_frame = self.textbox_logs
        self.queue_frame = self._body

    def _ask_dir(self, var, config_key=None):
        d = filedialog.askdirectory(parent=self)
        if d:
            var.set(d)
            if config_key:
                cfg.save_settings({config_key: d})
        
    def on_processing_mode_dropdown_change(self, choice):
        # Reset completed status when mode changes, so that user can run the new phase/mode
        old_mode = getattr(cfg, "PROCESSING_MODE", "Tự Động 100% (Tất Cả Trong Một)")
        if choice != old_mode:
            self.completed_files.clear()
            self.completed_job_rows.clear()
            self.update_global_progress()
            self.update_dashboard_counter()
            self.save_queue_state()
            self.log(f"🔄 Đã chuyển chế độ: {choice}. Trạng thái hoàn thành được reset để chạy mới!")
            
        cfg.save_settings({"processing_mode": choice})
        setattr(cfg, "PROCESSING_MODE", choice)

        if "Giai Đoạn" in choice:
            self.v_row.pack_forget()
            self.rescue_row.pack(fill="x", pady=(10, 0), after=self.p_row)
        else:
            self.rescue_row.pack_forget()
            self.v_row.pack(fill="x", after=self.qset.winfo_children()[0]) # Đặt lại vị trí ban đầu

    # ── Drop Zone ────────────────────────────────────────────────
    def _show_dropzone(self):
        for w in self._body.winfo_children(): w.destroy()

        outer = ctk.CTkFrame(self._body, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=26, pady=10)

        # Dropzone thẻ khổng lồ kính mờ
        dz = ctk.CTkFrame(
            outer, fg_color=BG3,
            border_color=BORDER, border_width=1,
            corner_radius=22, width=420, height=290
        )
        dz.pack()
        dz.pack_propagate(False)

        ctk.CTkLabel(dz, text="📂", font=F(42), text_color=T3).pack(pady=(8, 4))
        ctk.CTkLabel(dz, text="Kéo thả video vào đây",
                     font=F(16), text_color=T1).pack()
        ctk.CTkLabel(dz, text="hoặc nhấn nút bên dưới để chọn",
                     font=F(12), text_color=T3).pack(pady=(2, 0))
        ctk.CTkLabel(dz, text="Hỗ trợ: mp4, mov, avi, mkv",
                     font=F(11), text_color=T3).pack(pady=(2, 14))

        btn_row = ctk.CTkFrame(dz, fg_color="transparent")
        btn_row.pack()
        ctk.CTkButton(
            btn_row, text="Chọn File", command=self.select_files,
            fg_color=SEL, hover_color="#0066D6",
            text_color=T1, corner_radius=20,
            font=F(13, "bold"), height=36, width=120
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            btn_row, text="📁  Chọn Thư Mục", command=self.select_folder,
            fg_color=BG3, hover_color=HOVER,
            text_color=T2, corner_radius=20,
            font=F(13), height=36, width=150
        ).pack(side="left", padx=6)

    # ── Job List ──────────────────────────────────────────────────
    def _show_joblist(self):
        for w in self._body.winfo_children(): w.destroy()

        # Header row
        jh = ctk.CTkFrame(self._body, fg_color="transparent", height=36)
        jh.pack(fill="x", padx=20, pady=(8, 0))

        n = len(self.selected_files)
        c = len(self.completed_files)
        self.lbl_job_count = ctk.CTkLabel(jh, text=f"Đã hoàn thành {c}/{n} video",
                     font=F(12, "bold"), text_color=T2)
        self.lbl_job_count.pack(side="left", anchor="w")

        btn_area = ctk.CTkFrame(jh, fg_color="transparent")
        btn_area.pack(side="right", anchor="e")
        
        # Thêm 5 Nút Bấm Xịn Xò: Pause/Resume, Clear All, Smart Cleanup
        for txt, cmd in [("＋ Thêm", self.select_files),
                         ("📁 Thư Mục", self.select_folder),
                         ("⏸ Tạm Dừng", self.toggle_pause),
                         ("🧹 Xóa Hết", self.clear_queue),
                         ("🗑 Dọn Rác Gốc", self.open_smart_cleanup)]:
            col = "#FF5252" if "Dọn" in txt or "Xóa" in txt else T2
            if "Tạm" in txt: col = ORG
            btn = ctk.CTkButton(btn_area, text=txt, command=cmd,
                           fg_color=BG3, hover_color=HOVER, text_color=col,
                           corner_radius=8, font=F(11), height=28, width=70)
            btn.pack(side="left", padx=3)
            # Bộ nhớ theo mảng của phím Pause
            if "Tạm" in txt:
                self.btn_pause = btn
                if hasattr(self, 'pause_event') and not self.pause_event.is_set():
                    self.btn_pause.configure(text="▶ Tiếp Tục", text_color=GRN)

        ctk.CTkFrame(self._body, fg_color=BORDER, height=1).pack(
            fill="x", padx=14, pady=4)

        # Overview Glassmorphism Card
        self.card_overview = ctk.CTkFrame(
            self._body, fg_color=BG3, corner_radius=16, border_width=1, border_color=BORDER
        )
        self.card_overview.pack(fill="x", padx=16, pady=8)
        self.card_overview.grid_columnconfigure(0, weight=1)
        
        lbl_info = ctk.CTkLabel(self.card_overview, text="📊 TIẾN TRÌNH CHUNG", font=F(12, "bold"), text_color=T2)
        lbl_info.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        
        self.lbl_global_pct = ctk.CTkLabel(self.card_overview, text="0%", font=F(13, "bold"), text_color=SEL)
        self.lbl_global_pct.grid(row=0, column=1, sticky="e", padx=16, pady=(12, 4))
        
        self.progress_global = ctk.CTkProgressBar(
            self.card_overview, height=8, corner_radius=4, fg_color=BG4, progress_color=SEL
        )
        self.progress_global.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 12))
        self.progress_global.set(0)

        # Sub-header for active/running jobs
        self.sh_active = ctk.CTkFrame(self._body, fg_color="transparent", height=24)
        self.sh_active.pack(fill="x", padx=20, pady=(6, 2))
        self.lbl_sh_title = ctk.CTkLabel(
            self.sh_active, text="🚀 VIDEO ĐANG XỬ LÝ (CHẠY TRỰC TIẾP TỪ THƯ MỤC):",
            font=F(11, "bold"), text_color=ORG
        )
        self.lbl_sh_title.pack(side="left")

        # Scrollable Active Jobs
        self.scroll_jobs = ctk.CTkScrollableFrame(
            self._body, fg_color="transparent",
            scrollbar_button_color=BORDER
        )
        self.scroll_jobs.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self.lbl_no_active_jobs = ctk.CTkLabel(
            self.scroll_jobs, text="Chưa có video nào đang chạy. Nhấn 'Bắt Đầu' phía trên để chạy.",
            font=F(12), text_color=T3
        )
        self.lbl_no_active_jobs.pack(pady=40)
        
        # Update progress immediately
        self.update_global_progress()
            
    def _animate_job_slide(self, row, current_pad, target_pad):
        if not row.winfo_exists(): return
        if current_pad > target_pad:
            # Gia tốc trượt mượt (Ease-Out)
            next_pad = max(target_pad, int(current_pad * 0.6))
            if next_pad <= target_pad + 1: next_pad = target_pad
            row.pack_configure(pady=(next_pad, 3))
            self.after(16, lambda: self._animate_job_slide(row, next_pad, target_pad))
    def open_smart_cleanup(self):
        p = ctk.CTkToplevel(self)
        p.title("Dọn Rác Thông Minh (Xóa File Gốc Đã Xử Lý)")
        p.geometry("600x380")
        p.attributes('-topmost', 1)
        p.lift()
        
        # Center
        p.update_idletasks()
        x = (p.winfo_screenwidth() // 2) - (600 // 2)
        y = (p.winfo_screenheight() // 2) - (380 // 2)
        p.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(p, text="🗑 Dọn Dẹp Video Gốc", font=F(20, "bold"), text_color=ORG).pack(pady=(25, 10))
        ctk.CTkLabel(p, text="Tính năng này sẽ Quét toàn bộ Thư mục chứa 600 file Gốc sơ khai.\nVideo nào đã được xuất thành công bên ổ Đầu Ra sẽ bị XÓA VĨNH VIỄN khỏi máy.", 
                     font=F(13), text_color=T2, justify="center").pack(pady=(0, 20))
                     
        f1 = ctk.CTkFrame(p, fg_color=BG3, corner_radius=10)
        f1.pack(fill="x", padx=20, pady=10)
        
        source_dir = ctk.StringVar()
        if self.selected_files:
            source_dir.set(os.path.dirname(list(self.selected_files)[0]))
        
        ctk.CTkLabel(f1, text="Thư mục chứa File Gốc (Trộn lẫn):", font=F(12, "bold"), text_color=T1).pack(anchor="w", padx=15, pady=(15, 5))
        
        row1 = ctk.CTkFrame(f1, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkEntry(row1, textvariable=source_dir, font=F(12), fg_color=BG, border_width=0).pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def pick_source():
            d = filedialog.askdirectory(parent=p)
            if d: source_dir.set(d)
            
        ctk.CTkButton(row1, text="Chọn", width=60, fg_color=PUR, command=pick_source).pack(side="right")
        
        lbl_status = ctk.CTkLabel(p, text="", font=F(12), text_color=GRN)
        lbl_status.pack(pady=5)
        
        def run_clean():
            src = source_dir.get()
            if not src or not os.path.isdir(src):
                lbl_status.configure(text="⚠️ Vui lòng chọn Thư mục Gốc hợp lệ!", text_color=RED)
                return
                
            import config.config as cfg
            out_dir = cfg.OUTPUT_DIR
            out_files = os.listdir(out_dir) if os.path.exists(out_dir) else []
            p1_dir = os.path.join(out_dir, "GIAI_DOAN_1_XUAT_THO", "Video_Cam_Tam_Thoi")
            p1_files = os.listdir(p1_dir) if os.path.exists(p1_dir) else []
            
            success_basenames = set()
            for f in out_files:
                if f.startswith("HOAN_THIEN_"):
                    success_basenames.add(f.replace("HOAN_THIEN_", ""))
            for f in p1_files:
                if "_Video_Mute_" in f:
                    base = f.split("_Video_Mute_")[1]
                    success_basenames.add(base)
                    
            if not success_basenames:
                lbl_status.configure(text="⚠️ Thư mục Đầu Ra không có Video nào hoàn thiện!", text_color=ORG)
                return
                
            deleted = 0
            for f in os.listdir(src):
                if f in success_basenames:
                    fp = os.path.join(src, f)
                    try:
                        os.remove(fp)
                        deleted += 1
                        if fp in self.selected_files:
                            self.after(0, lambda p=fp: self.remove_job(p))
                    except:
                        pass
            
            lbl_status.configure(text=f"✅ Đã dọn dẹp (Xóa vĩnh viễn) {deleted} Video Gốc!", text_color=GRN)
            self.log(f"Đã dọn dẹp {deleted} rác từ: {src}")
            
        ctk.CTkButton(p, text="🔥 BẮT ĐẦU DỌN", font=F(14, "bold"), fg_color=RED, hover_color="#C82333", command=run_clean, height=40, width=200).pack(pady=15)

    # ── Settings Panel (inline) ───────────────────────────────────
    def _show_settings(self):
        self._title_lbl.configure(text="Cài Đặt")
        for w in self._body.winfo_children(): w.destroy()

        sc = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        sc.grid(row=0, column=0, sticky="nsew", padx=18, pady=8)

        def sec(text):
            ctk.CTkLabel(sc, text=text.upper(), font=F(9, "bold"), text_color=T3
                         ).pack(anchor="w", pady=(14, 3))

        def row_card(label, right_widget_fn):
            f = ctk.CTkFrame(sc, fg_color=BG3, corner_radius=14,
                              border_color=BORDER, border_width=1)
            f.pack(fill="x", pady=4)
            ctk.CTkLabel(f, text=label, font=F(14), text_color=T1,
                         anchor="w").pack(side="left", padx=16, pady=12)
            right_widget_fn(f)

        sec("Đầu Ra")
        def mk_out(f):
            self.lbl_output_dir_display = ctk.CTkLabel(
                f, text=f"…/{os.path.basename(self.custom_output_dir)}/",
                font=F(11), text_color=T3)
            self.lbl_output_dir_display.pack(side="right", padx=(0, 6))
            ctk.CTkButton(f, text="Đổi…", command=self.change_output_dir,
                          fg_color=BG4, hover_color=HOVER, text_color=SEL,
                          corner_radius=8, font=F(11), height=28, width=70
                          ).pack(side="right", padx=8)

        row_card("Thư Mục Lưu", mk_out)

        sec("Nguồn Phụ Đề")
        def mk_rb(f):
            self.rbtn_sub_auto = ctk.CTkRadioButton(
                f, text="🎙️ Nghe bằng Tai (Nhanh, Dễ nhầm từ lóng)",
                variable=self.sub_source_var, value="audio",
                font=F(11), text_color=T2, fg_color=SEL
            )
            self.rbtn_sub_auto.pack(side="left", padx=14)
            
            self.rbtn_sub_ocr = ctk.CTkRadioButton(
                f, text="👁 Nhìn bằng Mắt (Chuẩn xác 100% chữ có sẵn)",
                variable=self.sub_source_var, value="ocr",
                font=F(11), text_color=ORG, fg_color=ORG
            )
            self.rbtn_sub_ocr.pack(side="left", padx=14)

        def mk_rb_new(f):
            self.rbtn_sub_auto = ctk.CTkRadioButton(
                f, text="🎙️ Nghe bằng Tai (Nhanh)",
                variable=self.sub_source_var, value="audio",
                font=F(11), text_color=T2, fg_color=SEL
            )
            self.rbtn_sub_auto.pack(side="left", padx=10)
            
            self.rbtn_sub_ocr = ctk.CTkRadioButton(
                f, text="👁 Nhìn bằng Mắt (OCR)",
                variable=self.sub_source_var, value="ocr",
                font=F(11), text_color=ORG, fg_color=ORG
            )
            self.rbtn_sub_ocr.pack(side="left", padx=10)

            self.rbtn_sub_image = ctk.CTkRadioButton(
                f, text="📸 Phân Tích Ảnh Đơn Hàng (Gemini)",
                variable=self.sub_source_var, value="image",
                font=F(11), text_color=T2, fg_color=SEL
            )
            self.rbtn_sub_image.pack(side="left", padx=10)

        row_card("Chế Độ Phụ Đề", mk_rb_new)

        def mk_order_img(f):
            self.lbl_main_order_img = ctk.CTkLabel(
                f, text=os.path.basename(self.main_order_image_path) if self.main_order_image_path else "Chưa chọn ảnh đơn hàng",
                font=F(11), text_color=GRN if self.main_order_image_path else T3
            )
            self.lbl_main_order_img.pack(side="left", padx=16)
            
            ctk.CTkButton(
                f, text="Chọn Ảnh...", command=self.choose_main_order_image,
                fg_color=BG4, hover_color=HOVER, text_color=SEL,
                corner_radius=8, font=F(11), height=28, width=100
            ).pack(side="right", padx=12, pady=8)
            
        row_card("Ảnh Đơn Hàng (Chế độ Ảnh)", mk_order_img)

        sec("Ngôn Ngữ Dịch Thuật")
        
        def mk_src_lang(f):
            self.combo_source_lang = ctk.CTkOptionMenu(
                f, values=["Tự Động (AI)", "Tiếng Trung", "Tiếng Anh", "Tiếng Việt"],
                command=lambda v: (cfg.save_settings({"source_language": v}), setattr(cfg, "SOURCE_LANGUAGE", v)),
                fg_color=BG4, button_color=BG3, text_color=T1, font=F(11), corner_radius=8, width=180
            )
            self.combo_source_lang.set(getattr(cfg, "SOURCE_LANGUAGE", "Tự Động (AI)"))
            self.combo_source_lang.pack(side="right", padx=12, pady=8)
            
        row_card("Dịch từ (Ngôn Ngữ Gốc)", mk_src_lang)

        def on_target_lang_change(v):
            cfg.save_settings({"target_language": v})
            setattr(cfg, "TARGET_LANGUAGE", v)
            self.update_voice_dropdown(v)

        def mk_tgt_lang(f):
            self.combo_target_lang = ctk.CTkOptionMenu(
                f, values=["Tiếng Việt", "Tiếng Anh", "Tiếng Trung", "Tiếng Nhật", "Không Dịch (Giữ Nguyên Bản)"],
                command=on_target_lang_change,
                fg_color=BG4, button_color=BG3, text_color=T1, font=F(11), corner_radius=8, width=180
            )
            self.combo_target_lang.set(cfg.TARGET_LANGUAGE)
            self.combo_target_lang.pack(side="right", padx=12, pady=8)
            
        row_card("Dịch sang (Ngôn Ngữ Đích)", mk_tgt_lang)

        sec("Hiệu Ứng Bổ Sung")
        def mk_logo(f):
            self.combo_static_logo = ctk.CTkOptionMenu(
                f, values=["Không", "Tự Động (AI)", "Góc Phải Trên", "Góc Trái Trên", "Góc Phải Dưới", "Góc Trái Dưới"],
                command=lambda v: (cfg.save_settings({"static_logo_blur": v}), setattr(cfg, "STATIC_LOGO_BLUR", v)),
                fg_color=BG4, button_color=BG3, text_color=T1, font=F(11), corner_radius=8, width=180
            )
            self.combo_static_logo.set(cfg.STATIC_LOGO_BLUR)
            self.combo_static_logo.pack(side="right", padx=12, pady=8)
            
        row_card("Che Logo Cố Định", mk_logo)
        
        def mk_ocr_roi(f):
            roi_map = {
                "30% Dưới Cùng (Nhanh, cho TikTok/Douyin)": 0.30,
                "50% Nửa Dưới (Khuyên dùng)": 0.50,
                "70% Dưới": 0.70,
                "100% Toàn Màn Hình (Chậm)": 1.0
            }
            # Tìm label hiện tại dựa vào cfg.ROI_RATIO
            cur_label = list(roi_map.keys())[1] # Mặc định 50%
            for k, v in roi_map.items():
                if abs(cfg.ROI_RATIO - v) < 0.01:
                    cur_label = k
                    break
                    
            def on_roi_change(v):
                val = roi_map[v]
                cfg.save_settings({"ocr_roi_ratio": val})
                cfg.ROI_RATIO = val
                
            self.combo_ocr_roi = ctk.CTkOptionMenu(
                f, values=list(roi_map.keys()),
                command=on_roi_change,
                fg_color=BG4, button_color=BG3, text_color=T1, font=F(11), corner_radius=8, width=280
            )
            self.combo_ocr_roi.set(cur_label)
            self.combo_ocr_roi.pack(side="right", padx=12, pady=8)
            
        row_card("Vùng Quét Chữ OCR", mk_ocr_roi)

        sec("Hiệu Năng")
        def mk_perf(f):
            self.lbl_threads = ctk.CTkLabel(f, text=f"Chạy {cfg.MAX_CONCURRENT_JOBS} Luồng Tốc Độ Cao", font=F(11,"bold"), text_color=ORG)
            self.lbl_threads.pack(side="left", padx=12, pady=8)
            def update_thread_label(v):
                val = int(v)
                self.lbl_threads.configure(text=f"Chạy {val} Luồng Tốc Độ Cao")
                cfg.save_settings({"max_concurrent_jobs": val})
                cfg.MAX_CONCURRENT_JOBS = val
            self.slider_threads = ctk.CTkSlider(f, from_=1, to=8, number_of_steps=7, command=update_thread_label, progress_color=ORG)
            self.slider_threads.set(cfg.MAX_CONCURRENT_JOBS)
            self.slider_threads.pack(side="right", padx=12, fill="x", expand=True)

        row_card("Đa Luồng (Cùng Lúc)", mk_perf)

        sec("Giao Diện")
        def mk_theme(f):
            self.theme_menu = ctk.CTkOptionMenu(
                f, values=["Dark", "Light", "System"],
                command=self.change_theme,
                fg_color=BG4, button_color=BG3, text_color=T1,
                font=F(11), corner_radius=8, width=120
            )
            self.theme_menu.pack(side="right", padx=12, pady=8)

        row_card("Chủ Đề", mk_theme)

        bottom_row = ctk.CTkFrame(sc, fg_color="transparent")
        bottom_row.pack(fill="x", pady=(20, 10), padx=5)

        ctk.CTkButton(
            bottom_row, text="← Quay Lại",
            fg_color="transparent", hover_color=HOVER, text_color=T3,
            font=F(12, "bold"), command=self._show_pipeline, height=36, width=100
        ).pack(side="left")

        def on_click_save():
            # Force save all configurations to settings.json
            cfg.save_settings({
                "sub_source": self.sub_source_var.get(),
                "order_image_path": getattr(self, "main_order_image_path", "")
            })
            btn_save.configure(text="✅ Đã Lưu Thành Công!", fg_color="#28A745", text_color="white") # Xanh lá
            self.after(1500, lambda: btn_save.configure(text="💾 LƯU CÀI ĐẶT", fg_color=SEL, text_color=T1))

        btn_save = ctk.CTkButton(
            bottom_row, text="💾 LƯU CÀI ĐẶT",
            fg_color=SEL, hover_color="#0056b3", text_color=T1,
            font=F(13, "bold"), command=on_click_save, height=36, width=180
        )
        btn_save.pack(side="right")

    def choose_main_order_image(self):
        path = filedialog.askopenfilename(title="Chọn Ảnh Đơn Hàng / Sản Phẩm", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.heic *.heif *.PNG *.JPG *.JPEG *.WEBP *.HEIC *.HEIF")])
        if path:
            self.main_order_image_path = path
            self.lbl_main_order_img.configure(text=os.path.basename(path), text_color=GRN)
            self.log(f"📸 Đã nạp ảnh đơn hàng (Main App): {os.path.basename(path)}")
            cfg.save_settings({"order_image_path": path})

    def _show_pipeline(self):
        self._title_lbl.configure(text="Xử Lý Video")
        if self.selected_files:
            self._show_joblist()
        else:
            self._show_dropzone()

    # ─── STATUSBAR ────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=26, fg_color=BG, corner_radius=0)
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)

        lf = ctk.CTkFrame(bar, fg_color="transparent")
        lf.pack(side="left", padx=14)
        
        self._st_lbl = ctk.CTkLabel(lf, text="🟢 Sẵn Sàng", font=F(11, "bold"), text_color=ORG)
        self._st_lbl.pack(side="left", pady=9)
        
        self.pulse_state = True
        self.after(800, self._animate_pulse)

        ctk.CTkLabel(bar, text="M1 Pro · GPU · Neural Engine",
                     font=F(11), text_color=T3).pack(side="right", padx=14)

    def _animate_pulse(self):
        if not hasattr(self, '_st_lbl') or not self._st_lbl.winfo_exists():
            return
            
        current_text = self._st_lbl.cget("text")
        # Chỉ tạo hiệu ứng nhịp thở (Breathing) khi đang xử lý
        if "Đang" in current_text or "Processing" in current_text:
            if self.pulse_state:
                self._st_lbl.configure(text_color=T3) # Làm mờ đi
            else:
                self._st_lbl.configure(text_color=ORG) # Sáng rực lên
            self.pulse_state = not self.pulse_state
        else:
            # Sẵn sàng hoặc Lỗi -> Đứng im
            if "Lỗi" in current_text: self._st_lbl.configure(text_color=RED)
            elif "Sẵn Sàng" in current_text: self._st_lbl.configure(text_color=ORG)
            self.pulse_state = True
            
        self.after(800, self._animate_pulse)

    def _setstatus(self, text, color):
        icon = "🟢"
        if "Đang" in text or "Processing" in text:
            icon = "🟠"
        elif "Lỗi" in text or "Error" in text:
            icon = "🔴"
            
        self._st_lbl.configure(text=f"{icon} {text}", text_color=color)

    # ══════════════════════════════════════════════════════════════
    # POPUP DIALOGS
    # ══════════════════════════════════════════════════════════════
    def _popup(self, title, w=440, h=440):
        p = ctk.CTkToplevel(self)
        p.title(title); p.geometry(f"{w}x{h}")
        p.attributes("-topmost", True)
        p.configure(fg_color=BG)
        return p

    def _ptitle(self, p, text, sub=None):
        ctk.CTkLabel(p, text=text, font=F(18, "bold"), text_color=T1).pack(pady=(20,2))
        if sub: ctk.CTkLabel(p, text=sub, font=F(11), text_color=T2, justify="center").pack(pady=(0,10))

    def _field(self, p, label, key, s, show=""):
        ctk.CTkLabel(p, text=label, font=F(11), text_color=T2, anchor="w").pack(anchor="w", padx=26, pady=(8,0))
        e = ctk.CTkEntry(p, show=show, fg_color=BG4, border_color=BORDER,
                          font=F(12), text_color=T1, corner_radius=8)
        e.insert(0, str(s.get(key, "")))
        e.pack(fill="x", padx=26, pady=2)
        return e

    def _save_btn(self, p, text, cmd, color=SEL, tc=T1, w=160):
        ctk.CTkButton(p, text=text, command=cmd, fg_color=color, hover_color=color,
                      text_color=tc, corner_radius=20, font=F(13,"bold"),
                      height=36, width=w).pack(pady=14)

    def _show_api_settings(self):
        self._title_lbl.configure(text="Cài Đặt API Bất Tử")
        for w in self._body.winfo_children(): w.destroy()
        
        container = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(container, text="Dự phòng 5 Key Gemini để tự động luân phiên", font=F(12), text_color=T2).pack(pady=(0, 20))
        
        s = cfg.load_settings()
        
        e_g1 = self._field(container, "Gemini API Key 1 (Chính):", "gemini_api_key", s)
        e_g2 = self._field(container, "Gemini API Key 2 (Dự phòng):", "gemini_api_key_2", s)
        e_g3 = self._field(container, "Gemini API Key 3 (Dự phòng):", "gemini_api_key_3", s)
        e_g4 = self._field(container, "Gemini API Key 4 (Dự phòng):", "gemini_api_key_4", s)
        e_g5 = self._field(container, "Gemini API Key 5 (Dự phòng):", "gemini_api_key_5", s)
        
        ctk.CTkLabel(container, text="──────────────────────────", text_color=T2).pack(pady=10)
        
        e_v1 = self._field(container, "Vbee App ID:", "vbee_app_id", s)
        e_v2 = self._field(container, "Vbee API Key:", "vbee_api_key", s)
        
        def save():
            ns = {
                "gemini_api_key": e_g1.get().strip(),
                "gemini_api_key_2": e_g2.get().strip(),
                "gemini_api_key_3": e_g3.get().strip(),
                "gemini_api_key_4": e_g4.get().strip(),
                "gemini_api_key_5": e_g5.get().strip(),
                "vbee_app_id": e_v1.get().strip(), 
                "vbee_api_key": e_v2.get().strip()
            }
            cfg.save_settings(ns)
            cfg.GEMINI_API_KEY = ns["gemini_api_key"]
            cfg.GEMINI_API_KEY_2 = ns["gemini_api_key_2"]
            cfg.GEMINI_API_KEY_3 = ns["gemini_api_key_3"]
            cfg.GEMINI_API_KEY_4 = ns["gemini_api_key_4"]
            cfg.GEMINI_API_KEY_5 = ns["gemini_api_key_5"]
            cfg.VBEE_APP_ID = ns["vbee_app_id"]
            cfg.VBEE_API_KEY = ns["vbee_api_key"]
            self.log("✅ Đã lưu băng đạn 5 API Keys")
            
        self._save_btn(container, "Lưu Vĩnh Viễn", save)

    def _show_watermark_settings(self):
        self._title_lbl.configure(text="Đóng Dấu Video")
        for w in self._body.winfo_children(): w.destroy()
        
        p = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=10, pady=5)
        
        s = cfg.load_settings()
        sw = ctk.CTkSwitch(p, text="Kích Hoạt Watermark", font=F(12), text_color=T2,
                            button_color="#fff", progress_color=PUR, switch_width=44, switch_height=24)
        if s.get("enable_watermark", False): sw.select()
        sw.pack(pady=(10, 6))
        e_t = self._field(p, "Nội dung chữ:", "watermark_text", s)
        e_s = self._field(p, "Cỡ chữ:", "watermark_size", s)
        e_o = self._field(p, "Độ mờ (0.1–1.0):", "watermark_opacity", s)
        ctk.CTkLabel(p, text="Vị trí:", font=F(11), text_color=T2, anchor="w").pack(anchor="w", padx=26, pady=(8,0))
        cb = ctk.CTkComboBox(p, values=["Giữa màn hình","Góc trái - trên","Góc phải - trên","Góc trái - dưới","Góc phải - dưới"],
                              fg_color=BG4, border_color=BORDER, font=F(12), text_color=T1, corner_radius=8)
        cb.set(s.get("watermark_position", "Góc phải - dưới")); cb.pack(fill="x", padx=26, pady=2)
        def save():
            try:
                ns={"enable_watermark":bool(sw.get()),"watermark_text":e_t.get().strip(),"watermark_size":int(e_s.get()),"watermark_opacity":float(e_o.get()),"watermark_position":cb.get()}
                cfg.save_settings(ns)
                for k,v in ns.items(): setattr(cfg, k.upper(), v)
                self.log("✅ Đã lưu Watermark")
            except ValueError: pass
        self._save_btn(p, "Lưu", save, PUR)

    def _show_anti_reup_settings(self):
        self._title_lbl.configure(text="Chống Reup")
        for w in self._body.winfo_children(): w.destroy()
        
        p = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(p, text="Qua mặt hệ thống nhận diện Content ID", font=F(12), text_color=T2).pack(pady=(0, 20))
        
        s = cfg.load_settings()
        master = ctk.CTkSwitch(p, text="Kích Hoạt Chống Reup", font=F(13,"bold"), text_color=T1,
                                button_color="#fff", progress_color=RED, switch_width=44, switch_height=24)
        if s.get("enable_anti_reup", False): master.select()
        master.pack(pady=8)
        def chk(label, key, default=True):
            c = ctk.CTkCheckBox(p, text=label, font=F(12), text_color=T2,
                                 fg_color=SEL, border_color=BORDER, checkmark_color=T1, corner_radius=5)
            if s.get(key, default): c.select()
            c.pack(anchor="w", padx=26, pady=2); return c
        ctk.CTkLabel(p, text="VIDEO", font=F(9,"bold"), text_color=T3).pack(anchor="w", padx=26, pady=(8,0))
        c1=chk("Lật Ngang (Mirror)","reup_mirror"); c2=chk("Zoom & Bo Viền","reup_crop")
        c3=chk("Can Thiệp Màu Sắc","reup_color"); c4=chk("Tốc Độ < 3%","reup_speed"); c5=chk("Cắt Đầu/Cuối","reup_trim")
        ctk.CTkLabel(p, text="ÂM THANH", font=F(9,"bold"), text_color=T3).pack(anchor="w", padx=26, pady=(8,0))
        c6=chk("Pitch Shift","reup_audio_pitch"); c7=chk("Cân Bằng EQ","reup_audio_eq")
        ctk.CTkLabel(p, text="METADATA & EXTRA", font=F(9,"bold"), text_color=T3).pack(anchor="w", padx=26, pady=(8,0))
        c8=chk("Xóa Metadata Gốc","reup_metadata")
        c9=chk("Trích Xuất Ảnh Bìa (Thumbnail)","reup_thumbnail")
        def save():
            ns={"enable_anti_reup":int(master.get())==1,"reup_mirror":int(c1.get())==1,"reup_crop":int(c2.get())==1,
                "reup_color":int(c3.get())==1,"reup_speed":int(c4.get())==1,"reup_trim":int(c5.get())==1,
                "reup_audio_pitch":int(c6.get())==1,"reup_audio_eq":int(c7.get())==1,"reup_metadata":int(c8.get())==1,
                "reup_thumbnail":int(c9.get())==1}
            cfg.save_settings(ns); cfg.ENABLE_ANTI_REUP=ns["enable_anti_reup"]
            for k in ("reup_mirror","reup_crop","reup_color","reup_speed","reup_trim","reup_audio_pitch","reup_audio_eq","reup_metadata","reup_thumbnail"):
                setattr(cfg, k.upper(), ns[k])
            self.log("✅ Đã lưu Chống Reup")
        self._save_btn(p, "Lưu Cấu Hình", save, ORG, "black", 160)

    def _show_vertical_settings(self):
        self._title_lbl.configure(text="Chuyển Video Dọc 9:16")
        for w in self._body.winfo_children(): w.destroy()
        
        p = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(p, text="Bọc video ngang trong khung dọc Bokeh", font=F(12), text_color=T2).pack(pady=(0, 20))
        s = cfg.load_settings()
        sw = ctk.CTkSwitch(p, text="Kích Hoạt Chuyển Dọc", font=F(12), text_color=T2,
                            button_color="#fff", progress_color=SEL, switch_width=44, switch_height=24)
        if s.get("convert_to_vertical", False): sw.select()
        sw.pack(pady=14)
        def save():
            val=int(sw.get())==1; cfg.save_settings({"convert_to_vertical":val}); cfg.CONVERT_TO_VERTICAL=val
            self.log(f"{'✅ Bật' if val else '⛔ Tắt'} Chuyển Dọc Bokeh")
        self._save_btn(p, "Lưu", save)

    def _show_thumbnail_settings(self):
        self._title_lbl.configure(text="Bơm Thumbnail Ảnh Bìa")
        for w in self._body.winfo_children(): w.destroy()
        
        p = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(p, text="Tự động trích Thumbnail, phủ sương, dán Text to", font=F(12), text_color=T2).pack(pady=(0, 20))
        
        s = cfg.load_settings()
        sw = ctk.CTkSwitch(p, text="Dán Cover vào 0.2s đầu Video", font=F(12), text_color=T2,
                            button_color="#fff", progress_color=PUR, switch_width=44, switch_height=24)
        if s.get("enable_thumbnail", True): sw.select()
        sw.pack(pady=15)
        def save():
            ns = {"enable_thumbnail": bool(sw.get())}
            cfg.save_settings(ns)
            cfg.ENABLE_THUMBNAIL = ns["enable_thumbnail"]
            self.log(f"{'✅ Bật' if sw.get() else '⛔ Tắt'} hệ thống Ảnh Bìa")
        self._save_btn(p, "Lưu Thiết Lập", save)

    def _show_preview_settings(self):
        self._title_lbl.configure(text="Xem Trước Phụ Đề")
        for w in self._body.winfo_children(): w.destroy()
        
        p = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(p, text="Chỉnh font, cỡ chữ và vị trí Y", font=F(12), text_color=T2).pack(pady=(0, 20))
        
        s = cfg.load_settings()
        fonts = [f for f in os.listdir(cfg.ASSETS_DIR) if f.endswith((".ttf",".otf"))] or ["BeVietnamPro-Bold.ttf"]
        fv = ctk.StringVar(value=s.get("font_name", fonts[0]))
        fc = ctk.CTkFrame(p, fg_color="transparent")
        fc.pack(fill="x", padx=24, pady=(0,6))
        ctk.CTkLabel(fc, text="Font:", font=F(12), text_color=T2).pack(side="left", padx=(0,8))
        ctk.CTkComboBox(fc, values=fonts, variable=fv, width=340, fg_color=BG4, border_color=BORDER,
                         font=F(11), command=lambda _: _upd()).pack(side="left")
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=20)
        def col(title):
            f = ctk.CTkFrame(row, fg_color=BG3, corner_radius=10)
            f.pack(side="left", expand=True, fill="both", padx=6, pady=4)
            ctk.CTkLabel(f, text=title, font=F(11), text_color=T2).pack(pady=(8,2)); return f
        cl=col("Ngang (16:9)"); ll=ctk.CTkLabel(cl,text=""); ll.pack(pady=4)
        sl=ctk.DoubleVar(value=s.get("font_size_scale_ngang",1.0)); yl=ctk.DoubleVar(value=s.get("sub_y_pos_ngang",0.85))
        for lb,var,mx in [("Cỡ",sl,2.0),("Vị trí Y",yl,0.98)]:
            ctk.CTkLabel(cl,text=lb,font=F(10),text_color=T3).pack()
            ctk.CTkSlider(cl,from_=0.5,to=mx,variable=var,progress_color=SEL,command=lambda _:_upd()).pack(fill="x",padx=12,pady=(0,4))
        cp=col("Dọc (9:16)"); lp=ctk.CTkLabel(cp,text=""); lp.pack(pady=4)
        sp=ctk.DoubleVar(value=s.get("font_size_scale_doc",1.0)); yp=ctk.DoubleVar(value=s.get("sub_y_pos_doc",0.85))
        for lb,var,mx in [("Cỡ",sp,2.0),("Vị trí Y",yp,0.98)]:
            ctk.CTkLabel(cp,text=lb,font=F(10),text_color=T3).pack()
            ctk.CTkSlider(cp,from_=0.5,to=mx,variable=var,progress_color=SEL,command=lambda _:_upd()).pack(fill="x",padx=12,pady=(0,4))
        def _render(vert,sc,ypos,fp):
            bw,bh=(200,356) if vert else (480,270); img=Image.new("RGB",(bw,bh),(28,28,30)); d=ImageDraw.Draw(img)
            fs=int(max(14 if vert else 16,int((bw if vert else bh)*0.045))*sc*1.5)
            try: fn=ImageFont.truetype(fp,fs)
            except: fn=ImageFont.load_default()
            lines=[]
            for t in "Video AI Pro\ntự động phụ đề".split("\n"): lines.extend(wrap_text(t,bw*0.95,fn,d))
            y0=max(0,int(bh*ypos)-len(lines)*fs)
            for ln in lines:
                bb=d.textbbox((0,0),ln,font=fn); x=(bw-(bb[2]-bb[0]))//2
                d.text((x,y0),ln,font=fn,fill=(255,220,0),stroke_width=max(1,int(fs*0.05)),stroke_fill=(0,0,0))
                y0+=bb[3]-bb[1]+2
            return ctk.CTkImage(light_image=img,dark_image=img,size=(bw,bh))
        def _upd(*_):
            fp=os.path.join(cfg.ASSETS_DIR,fv.get())
            i1=_render(False,sl.get(),yl.get(),fp); ll.configure(image=i1); ll.image=i1
            i2=_render(True,sp.get(),yp.get(),fp); lp.configure(image=i2); lp.image=i2
        _upd()
        def save():
            ns={"font_name":fv.get(),"font_size_scale_ngang":round(sl.get(),2),"sub_y_pos_ngang":round(yl.get(),2),
                "font_size_scale_doc":round(sp.get(),2),"sub_y_pos_doc":round(yp.get(),2)}
            cfg.save_settings(ns); cfg.FONT_NAME=ns["font_name"]; cfg.FONT_SIZE_SCALE_NGANG=ns["font_size_scale_ngang"]
            cfg.SUB_Y_POS_NGANG=ns["sub_y_pos_ngang"]; cfg.FONT_SIZE_SCALE_DOC=ns["font_size_scale_doc"]; cfg.SUB_Y_POS_DOC=ns["sub_y_pos_doc"]
            self.log("✅ Đã lưu cài đặt Phụ Đề")
        self._save_btn(p, "Lưu & Áp Dụng", save)

    # ══════════════════════════════════════════════════════════════
    # BUSINESS LOGIC
    # ══════════════════════════════════════════════════════════════
    def change_output_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.custom_output_dir = folder
            cfg.OUTPUT_DIR = folder
            cfg.save_settings({"output_dir": folder})
            if self.lbl_output_dir_display:
                self.lbl_output_dir_display.configure(text=f"…/{os.path.basename(folder)}/")
            self.log(f"📁 Đầu ra → {folder}")

    def on_processing_mode_change(self, mode):
        self.log(f"⚙️ Chế độ xử lý: {mode}")
        if "Giai Đoạn 2" in mode:
            self.btn_select_p2_audio.pack(side="left", padx=(0, 10))
        else:
            self.btn_select_p2_audio.pack_forget()

    def select_p2_audio_dir(self):
        d = filedialog.askdirectory(title="Chọn Thư Mục chứa MP3 Vbee Thủ Công")
        if d:
            self.phase2_audio_dir.set(d)
            self.log(f"📁 Nguồn MP3 (Giai Đoạn 2): {d}")
            self.btn_select_p2_audio.configure(text="✅ Đã Chọn Nguồn MP3", fg_color="#28a745", text_color="white")

    def select_files(self):
        files = filedialog.askopenfilenames(title="Chọn Video",
            filetypes=[("Video","*.mp4 *.avi *.mov *.mkv")])
        if files: self.add_to_queue(files)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if f.lower().endswith(('.mp4','.avi','.mov','.mkv'))]
            self.add_to_queue(files)

    def remove_job(self, path):
        if path in self.selected_files: self.selected_files.remove(path)
        if path in self.completed_files: self.completed_files.remove(path)
        if path in self.completed_job_rows: self.completed_job_rows.remove(path)
        if path in self.job_widgets:
            widget = self.job_widgets[path]
            if widget.winfo_exists():
                widget.destroy()
            del self.job_widgets[path]
        
        self.update_dashboard_counter()
        self.save_queue_state()
        self.update_global_progress()
        
        if not self.selected_files:
            self._show_dropzone()

    def clear_queue(self):
        """Dọn sạch bách UI chỉ trong 1 nút bấm"""
        self.selected_files.clear()
        self.completed_files.clear()
        self.completed_job_rows.clear()
        self.job_widgets.clear()
        self._show_dropzone()
        
        self.update_dashboard_counter()
        self.save_queue_state()
        
        self.log("🧹 Đã làm sạch toàn bộ hàng đợi UI!")
        
    def toggle_pause(self):
        """Bật/Tắt Cờ chờ giữa các Vòng lặp"""
        if not hasattr(self, 'pause_event'): return
        
        # Nếu Tiến Trình đã Dừng Hẳn (Nút Bắt Đầu màu xanh), bấm Tiếp Tục -> Coi như Bấm Bắt Đầu
        if self.btn_start.cget("state") == "normal" and self.btn_start.cget("text") == "▶ Bắt Đầu":
            if not self.pause_event.is_set():
                self.pause_event.set()
                if hasattr(self, 'btn_pause') and self.btn_pause.winfo_exists():
                    self.btn_pause.configure(text="⏸ Tạm Dừng", text_color=ORG)
            self.start_pipeline()
            return
            
        if self.pause_event.is_set():
            self.pause_event.clear()
            if hasattr(self, 'btn_pause') and self.btn_pause.winfo_exists():
                self.btn_pause.configure(text="▶ Tiếp Tục", text_color=GRN)
            self.log("⏸ TẠM DỪNG: Sẽ tạm ngừng lấy thêm Video sau khi 1 chu trình hoàn tất!")
        else:
            self.pause_event.set()
            if hasattr(self, 'btn_pause') and self.btn_pause.winfo_exists():
                self.btn_pause.configure(text="⏸ Tạm Dừng", text_color=ORG)
            self.log("▶ TIẾP TỤC: Đã mở cổng băng chuyền nhồi Video!")

    def add_to_queue(self, paths):
        added = []
        for p in paths:
            if p not in self.selected_files:
                self.selected_files.append(p)
                added.append(p)
                
        if not added: return
        
        self._title_lbl.configure(text="Xử Lý Video")
        
        # Nếu màn hình danh sách đang hiển thị, chỉ việc cập nhật UI thay vì clear toàn bộ
        if hasattr(self, 'scroll_jobs') and self.scroll_jobs.winfo_exists():
            self.update_dashboard_counter()
            self.save_queue_state()
            self.update_global_progress()
        else:
            self._show_joblist()
            
        self.log(f"  ＋  Đã thêm {len(added)} file vào hàng đợi")
        self.lbl_file_count = None  # compat placeholder

    def log(self, message):
        if not hasattr(self, 'textbox_logs') or not self.textbox_logs:
            print(f"[Log Giao Diện Tạm]: {message}")
            return
            
        self.textbox_logs.configure(state="normal")
        self.textbox_logs.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.textbox_logs.configure(state="disabled")
        self.textbox_logs.yview("end")

    def change_theme(self, t): ctk.set_appearance_mode(t)

    def start_pipeline(self):
        if not self.selected_files:
            self.log("  ⚠  Chưa có video nào trong hàng đợi!"); return
            
        # Reset cờ Tạm Dừng để bắt đầu mẻ mới không bị kẹt
        if hasattr(self, 'pause_event'):
            self.pause_event.set()
        if hasattr(self, 'btn_pause') and self.btn_pause.winfo_exists():
            self.btn_pause.configure(text="⏸ Tạm Dừng", text_color=ORG)
            
        # Tự động reset hàng đợi nếu tất cả các file trong queue đã hoàn thành
        if all(fp in self.completed_files for fp in self.selected_files):
            self.completed_files.clear()
            self.completed_job_rows.clear()
            self.update_global_progress()
            self.update_dashboard_counter()
            self.save_queue_state()
            self.log("🔄 Toàn bộ hàng đợi đã hoàn thành. Tự động reset trạng thái để chạy lại!")
            
        self.btn_start.configure(state="disabled", text="⏳", fg_color=BG3)
        self._setstatus("Đang Xử Lý…", ORG)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self.log("─" * 42); self.log("  Pipeline bắt đầu…"); self.log("─" * 42)

        def _one(fp, idx):
            # CHECK CHỐNG XOÁ RÁC: Nếu Sếp đã bấm X xoá mất File khỏi Danh Sách Queue -> Vứt luôn 
            if fp not in self.selected_files: return
            if fp in self.completed_files: return
            if not os.path.exists(fp): return
            
            # CHỐT HÃM PHANH TẠM DỪNG TIẾN TRÌNH RENDER 
            if hasattr(self, 'pause_event'):
                self.pause_event.wait()
            
            # Lấy thông số Cấu Hình Real-time (Cho phép Sếp bẻ lái ngay giữa Không Trung!)
            amf   = bool(self.switch_amf.get())   if self.switch_amf   else True
            sub   = bool(self.switch_sub.get())   if self.switch_sub   else True
            voice = bool(self.switch_voice.get()) if self.switch_voice else True
            sub_src = self.sub_source_var.get() if self.sub_source_var else "audio"
            bgm   = bool(self.switch_keep_bgm.get()) if self.switch_keep_bgm else True
            blur  = bool(self.switch_blur.get())  if self.switch_blur  else True
            
            p_mode = self.combo_processing_mode.get()
            p2_dir = self.rescue_mp3_dir.get() if "Giai Đoạn 2" in p_mode else ""
            p1_dir = self.rescue_srt_dir.get() if ("Giai Đoạn 1" in p_mode or "Giai Đoạn 2" in p_mode) else ""
            
            # Đề phòng lỗi thiếu thư mục MP3 lúc bẻ ngang sang GĐ2
            if "Giai Đoạn 2" in p_mode and (not p2_dir or not os.path.exists(p2_dir)):
                self.log(f"⚠️ Video {os.path.basename(fp)} đang chờ ghép MP3 nhưng Thư mục MP3 Giai Đoạn 2 chưa cấu hình. Đang bỏ qua!")
                return
            
            # Double chốt
            if fp not in self.selected_files: return
            
            name = os.path.basename(fp)
            # Create JobRow dynamically on main thread
            self.after(0, lambda: self.create_active_job_row(fp, p_mode))
            
            try:
                # If sub source is image, verify image path is loaded
                if sub_src == "image" and not self.main_order_image_path:
                    self.log(f"⚠️ Chưa chọn ảnh đơn hàng cho video: {name}. Bỏ qua!")
                    self.after(0, lambda: self.finish_job(fp, "Lỗi: Thiếu Ảnh", RED))
                    return
                    
                process_video_pipeline(fp,
                    progress_callback=lambda pct: self.after(0, lambda: self.update_job_progress(fp, pct)),
                    use_hw_accel=amf, add_sub=sub, add_voice=voice,
                    sub_source=sub_src, keep_bgm=bgm,
                    processing_mode=p_mode,
                    phase2_audio_dir=p2_dir,
                    file_index=idx + 1,
                    phase1_export_dir=p1_dir,
                    enable_blur=blur,
                    order_image_path=self.main_order_image_path)
                
                # Success callback
                self.after(0, lambda: self.finish_job(fp, "Hoàn Thành ✓", GRN))
                self.completed_files.add(fp)
                
                # Cập nhật Đếm số & Disk Save
                self.after(0, self.update_dashboard_counter)
                self.save_queue_state()
                
                self.log(f"  ✓  {name}")
            except Exception as e:
                self.log(f"  ✕  {name}: {e}")
                self.after(0, lambda: self.finish_job(fp, "Lỗi!", RED))

        from utils.sync_and_sub import cleanup_temp_files
        cleanup_temp_files()
        
        # BỎ XOÁ LỊCH SỬ Ở ĐÂY ĐỂ DỮ LIỆU CŨ KHÔNG BỊ RERUN
        # self.completed_files.clear()
        
        # Một Băng Chuyền Chung Nhất - Chờ Đón Sự Lái Lụa Của Sếp (Chuyển chế độ lúc nào cũng ăn)
        with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.MAX_CONCURRENT_JOBS) as ex:
            futures = [ex.submit(_one, fp, i) for i, fp in enumerate(self.selected_files)]
            concurrent.futures.wait(futures)
            
        self.log("🎉 XỬ LÝ TOÀN BỘ FILE TRONG HÀNG ĐỢI ĐÃ KẾT THÚC!")
        self.after(0, lambda: (self.btn_start.configure(state="normal", text="▶ Bắt Đầu", fg_color=GRN), self._setstatus("Trạng Thái: Rảnh", T3)))

        self.log("─" * 42); self.log("  Tất cả hoàn tất!")
        self.after(0, lambda: (
            self.btn_start.configure(state="normal", text="▶  Bắt Đầu", fg_color=GRN),
            self._setstatus("Hoàn Tất", GRN)
        ))

    def update_voice_dropdown(self, target_lang=None):
        if not hasattr(self, 'combo_vbee_voice') or not self.combo_vbee_voice:
            return
        if not target_lang:
            target_lang = cfg.TARGET_LANGUAGE
            
        engine = self.seg_tts_engine.get()
        
        # Determine options based on language and engine
        if "Việt" in target_lang:
            if engine == "Vbee (VIP)":
                self.current_opts_dict = self.vbee_voice_options_vi
            else:
                self.current_opts_dict = {"Chị Google (Tiếng Việt)": "gtts:vi"}
        elif "Anh" in target_lang:
            if engine == "Vbee (VIP)":
                self.current_opts_dict = self.vbee_voice_options_en
            else:
                self.current_opts_dict = {"Chị Google (Tiếng Anh - US)": "gtts:en"}
        elif "Trung" in target_lang:
            self.current_opts_dict = {"Chị Google (Tiếng Trung)": "gtts:zh-CN"}
        elif "Nhật" in target_lang:
            self.current_opts_dict = {"Chị Google (Tiếng Nhật)": "gtts:ja"}
        else: # Không Dịch
            if engine == "Vbee (VIP)":
                self.current_opts_dict = self.vbee_voice_options_vi
            else:
                self.current_opts_dict = {"Chị Google (Tiếng Việt)": "gtts:vi"}
                
        # Update combo values
        vals = list(self.current_opts_dict.keys())
        self.combo_vbee_voice.configure(values=vals)
        
        cur_val = self.combo_vbee_voice.get()
        if cur_val not in vals:
            self.combo_vbee_voice.set(vals[0])
            self.save_voice_setting(vals[0])
        else:
            self.combo_vbee_voice.set(cur_val)

    def on_engine_change(self, choice):
        self.update_voice_dropdown()

    def save_quick_settings(self):
        settings = {
            "enable_amf": bool(self.switch_amf.get()) if self.switch_amf else True,
            "enable_sub": bool(self.switch_sub.get()) if self.switch_sub else True,
            "enable_voice": bool(self.switch_voice.get()) if self.switch_voice else True,
            "keep_bgm": bool(self.switch_keep_bgm.get()) if self.switch_keep_bgm else True,
            "enable_blur": bool(self.switch_blur.get()) if self.switch_blur else True,
        }
        cfg.save_settings(settings)
        for k, v in settings.items():
            setattr(cfg, k.upper(), v)
        self.log("💾 Đã lưu cấu hình thiết lập nhanh thành công!")
        
        if hasattr(self, 'btn_save_quick') and self.btn_save_quick:
            self.btn_save_quick.configure(text="✅ Đã Lưu", fg_color=GRN, text_color="black")
            self.after(1500, lambda: self.btn_save_quick.configure(text="💾 Lưu Cấu Hình", fg_color=SEL, text_color=T1))

    def save_voice_setting(self, choice=None):
        if not self.combo_vbee_voice: return
        voice_name = self.combo_vbee_voice.get()
        code = self.current_opts_dict.get(voice_name,
                                            "vbee:hn_female_ngochuyen_full_48k-fhg")
        cfg.VBEE_VOICE = code
        cfg.save_settings({"vbee_voice": code})
        
        # Tự động thay đổi Ngôn Ngữ Dịch Thuật khớp với Giọng Đọc
        new_lang = "Tiếng Việt"
        if ":en" in code.lower() or "tiếng anh" in voice_name.lower():
            new_lang = "Tiếng Anh"
        elif ":zh" in code.lower() or "tiếng trung" in voice_name.lower():
            new_lang = "Tiếng Trung"
        elif ":ja" in code.lower() or "tiếng nhật" in voice_name.lower():
            new_lang = "Tiếng Nhật"
            
        cfg.TARGET_LANGUAGE = new_lang
        cfg.save_settings({"target_language": new_lang})
        
        if hasattr(self, 'combo_target_lang') and self.combo_target_lang:
            try:
                self.combo_target_lang.set(new_lang)
            except Exception:
                pass
                
        self.log(f"  🎙  Giọng → {voice_name} (Auto-sync Dịch: {new_lang})")

    def play_test_voice(self):
        if not self.combo_vbee_voice: return
        code = self.current_opts_dict.get(self.combo_vbee_voice.get(),
                                            "vbee:hn_female_ngochuyen_full_48k-fhg")
        
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
        def _t():
            try:
                if code.startswith("gtts:"):
                    from utils.gtts_engine import test_gtts_voice; ap=test_gtts_voice(code)
                else:
                    from utils.vbee_tts import test_vbee_voice; ap=test_vbee_voice(code)
                if ap and os.path.exists(ap):
                    if platform.system()=="Darwin": os.system(f"afplay '{ap}'")
            except Exception as e: self.log(f"  ✕  Thử giọng: {e}")
            finally:
                if self.btn_test_voice:
                    self.after(0, lambda: self.btn_test_voice.configure(state="normal", text="▶ Thử Giọng"))
        threading.Thread(target=_t, daemon=True).start()

    # Compatibility attributes
    @property
    def lbl_file_count(self): return None
    @lbl_file_count.setter
    def lbl_file_count(self, v): pass


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = ctk.CTk()
    app.geometry("1080x700")
    app.minsize(900, 580)
    app.title("Video AI Pro")
    app.configure(fg_color=BG2)
    app.grid_rowconfigure(0, weight=1)
    app.grid_columnconfigure(0, weight=1)
    frame = VideoAutomationApp(app)
    frame.grid(row=0, column=0, sticky="nsew")
    app.mainloop()