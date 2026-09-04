import os
import sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- FIX CWD FOR MAC APP BUNDLE ---
os.chdir(get_resource_path(""))
# ----------------------------------

import customtkinter as ctk

# Add current directory and its path to sys.path so modules can import correctly
current_dir = get_resource_path("")
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import our custom UI frames
try:
    from automation.gui import VideoAutomationApp
    from watermark.watermark import WatermarkApp
    from douyin.douyin_gui import DouyinApp
    from bot.bot_gui import BotApp
    from threads.poster_gui import PosterApp as ThreadsApp
    from tiktok_upload.tiktok_gui import TikTokApp
    from trimmer.trimmer_gui import TrimmerApp
    from manual_editor.editor_gui import ManualEditorApp
    from manual_editor.tiktok_editor_gui import TikTokEditorApp
    from manual_editor.batch_cutter_gui import BatchCutterApp
    from ratio_converter.converter_gui import ConverterApp
    from ai_video import AIVideoApp
    from yt_compiler.compiler_gui import YoutubeCompilerApp
    from bgm_injector.bgm_injector_gui import BgmInjectorApp
    from tts_tool.tts_gui import TTSApp
except Exception as e:
    import traceback
    with open("/tmp/VideoAI_Error.txt", "a") as f:
        f.write(f"ImportError: {e}\n{traceback.format_exc()}\n")

# ==================================
# PREMIUM COLOR PALETTE (Light / Dark Mode)
# ==================================
C_BG_MAIN = ("#EFF1F5", "#1E1E2E")       # Base background
C_BG_SIDEBAR = ("#DCE0E8", "#11111B")    # Crust (Darker for sidebar)
C_BTN_NORMAL = "transparent"
C_BTN_HOVER = ("#BCC0CC", "#313244")     # Surface1
C_BTN_ACTIVE = ("#1E66F5", "#89B4FA")    # Blue Accent
C_TEXT_PRIMARY = ("#4C4F69", "#CDD6F4")  # Text
C_TEXT_MUTED = ("#6C6F85", "#A6ADC8")    # Subtext0
C_TEXT_ACTIVE = ("#EFF1F5", "#1E1E2E")   # Contrast text on active button

def F(size=13, weight="normal"):
    """Helper cho Font chữ"""
    return ctk.CTkFont(family="Inter", size=size, weight=weight)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Video AI Pro Studio")
        self.geometry("1150x800")
        self.minsize(1050, 700)
        self.configure(fg_color=C_BG_MAIN)

        # Set grid layout 1x2 (Sidebar + Content)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ==================================
        # SIDEBAR (PREMIUM DESIGN)
        # ==================================
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=C_BG_SIDEBAR)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(14, weight=1) # Spacer đẩy menu xuống đáy

        # LOGO AREA
        logo_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(30, 20), sticky="ew")
        
        self.logo_label = ctk.CTkLabel(logo_frame, text="✦ AI STUDIO", font=F(24, "bold"), text_color=C_BTN_ACTIVE)
        self.logo_label.pack(side="left")

        # CỤM 1: XỬ LÝ VIDEO
        self._create_sidebar_header("XỬ LÝ & EDIT VIDEO", row=1)
        self.btn_automation = self._create_sidebar_btn("▶  AI Pipeline (Chính)", "automation", row=2)
        self.btn_ai_video = self._create_sidebar_btn("🤖 Video AI Cặp", "ai_video", row=3)
        self.btn_editor = self._create_sidebar_btn("🎬 Edit & Lách Bản Quyền YT", "editor", row=4)
        self.btn_tiktok_editor = self._create_sidebar_btn("🎬 Edit & Lách TikTok (Dọc)", "tiktok_editor", row=5)
        self.btn_trimmer = self._create_sidebar_btn("✂️ Cắt Video 59s", "trimmer", row=6)
        self.btn_batch_cutter = self._create_sidebar_btn("✂️ Cắt Video Hàng Loạt", "batch_cutter", row=7)
        self.btn_converter = self._create_sidebar_btn("📱 Đổi Ngang -> Dọc", "converter", row=8)
        self.btn_yt_compiler = self._create_sidebar_btn("🎥 Ghép & Edit Video YT", "yt_compiler", row=9)
        self.btn_bgm_injector = self._create_sidebar_btn("🎵 Gắn Nhạc Hàng Loạt", "bgm_injector", row=10)
        self.btn_watermark = self._create_sidebar_btn("💧 Auto Watermark", "watermark", row=11, pady=(5, 15))

        # CỤM 2: MẠNG XÃ HỘI
        self._create_sidebar_header("ĐĂNG TẢI & NGUỒN", row=12)
        self.btn_tiktok = self._create_sidebar_btn("🎵 TikTok Auto-Up", "tiktok", row=13)
        self.btn_threads = self._create_sidebar_btn("🧵 Threads Affiliate", "threads", row=14)
        self.btn_douyin = self._create_sidebar_btn("📥 Tải Nguồn MXH", "douyin", row=15, pady=(5, 15))

        # CỤM 3: CÔNG CỤ PHỤ
        self._create_sidebar_header("CÔNG CỤ KHÁC", row=16)
        self.btn_bot = self._create_sidebar_btn("💬 Telegram Bot", "bot", row=17)
        self.btn_tts = self._create_sidebar_btn("🗣️ Text to Speech", "tts", row=18)

        # NÚT ĐỔI GIAO DIỆN Ở ĐÁY SIDEBAR
        self.theme_menu = ctk.CTkOptionMenu(
            self.sidebar_frame, 
            values=["Dark", "Light", "System"], 
            command=self.change_theme,
            fg_color=C_BTN_HOVER,
            button_color=C_BTN_HOVER,
            button_hover_color=C_BTN_ACTIVE,
            text_color=C_TEXT_PRIMARY,
            font=F(12),
            height=32
        )
        self.theme_menu.grid(row=19, column=0, padx=20, pady=(10, 20), sticky="ew")

        # ==================================
        # MAIN CONTENT AREA
        # ==================================
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_content.grid_rowconfigure(0, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.current_frame_name = None

        # Initialize all frames
        self._init_all_frames()

    def _create_sidebar_header(self, text, row):
        """Tạo tiêu đề nhóm menu (Header) cực tinh tế"""
        lbl = ctk.CTkLabel(
            self.sidebar_frame, 
            text=text, 
            font=F(11, "bold"), 
            text_color=C_TEXT_MUTED
        )
        lbl.grid(row=row, column=0, sticky="w", padx=20, pady=(15, 5))

    def _create_sidebar_btn(self, text, frame_name, row, pady=5):
        """Tạo nút Sidebar bo góc mềm mại, hover xịn"""
        btn = ctk.CTkButton(
            self.sidebar_frame, 
            text=text, 
            anchor="w",
            font=F(13, "bold"),
            fg_color=C_BTN_NORMAL,
            text_color=C_TEXT_PRIMARY,
            hover_color=C_BTN_HOVER,
            corner_radius=8,
            height=38,
            command=lambda: self.show_frame(frame_name)
        )
        btn.grid(row=row, column=0, padx=15, pady=pady, sticky="ew")
        return btn

    def _init_all_frames(self):
        try:
            print("Init VideoAutomationApp...")
            self.frames["automation"] = VideoAutomationApp(self.main_content)
            self.frames["automation"].grid(row=0, column=0, sticky="nsew")
            
            print("Init AIVideoApp...")
            self.frames["ai_video"] = AIVideoApp(self.main_content)
            self.frames["ai_video"].grid(row=0, column=0, sticky="nsew")
            
            print("Init ManualEditorApp...")
            self.frames["editor"] = ManualEditorApp(self.main_content)
            self.frames["editor"].grid(row=0, column=0, sticky="nsew")
            
            print("Init TikTokEditorApp...")
            self.frames["tiktok_editor"] = TikTokEditorApp(self.main_content)
            self.frames["tiktok_editor"].grid(row=0, column=0, sticky="nsew")
            
            print("Init TrimmerApp...")
            self.frames["trimmer"] = TrimmerApp(self.main_content)
            self.frames["trimmer"].grid(row=0, column=0, sticky="nsew")
            
            print("Init BatchCutterApp...")
            self.frames["batch_cutter"] = BatchCutterApp(self.main_content)
            self.frames["batch_cutter"].grid(row=0, column=0, sticky="nsew")
            
            print("Init ConverterApp...")
            self.frames["converter"] = ConverterApp(self.main_content)
            self.frames["converter"].grid(row=0, column=0, sticky="nsew")
            
            print("Init YoutubeCompilerApp...")
            self.frames["yt_compiler"] = YoutubeCompilerApp(self.main_content)
            self.frames["yt_compiler"].grid(row=0, column=0, sticky="nsew")

            print("Init WatermarkApp...")
            self.frames["watermark"] = WatermarkApp(self.main_content)
            self.frames["watermark"].grid(row=0, column=0, sticky="nsew")

            print("Init BgmInjectorApp...")
            self.frames["bgm_injector"] = BgmInjectorApp(self.main_content)
            self.frames["bgm_injector"].grid(row=0, column=0, sticky="nsew")

            print("Init TikTokApp...")
            self.frames["tiktok"] = TikTokApp(self.main_content)
            self.frames["tiktok"].grid(row=0, column=0, sticky="nsew")
            
            print("Init ThreadsApp...")
            self.frames["threads"] = ThreadsApp(self.main_content)
            self.frames["threads"].grid(row=0, column=0, sticky="nsew")

            print("Init DouyinApp...")
            self.frames["douyin"] = DouyinApp(self.main_content)
            self.frames["douyin"].grid(row=0, column=0, sticky="nsew")

            print("Init BotApp...")
            self.frames["bot"] = BotApp(self.main_content)
            self.frames["bot"].grid(row=0, column=0, sticky="nsew")

            print("Init TTSApp...")
            self.frames["tts"] = TTSApp(self.main_content)
            self.frames["tts"].grid(row=0, column=0, sticky="nsew")

            print("Done initializing all frames.")
            
            # Ẩn tất cả frame ban đầu
            for frame in self.frames.values():
                frame.grid_remove()
                
            # Show default frame
            self.show_frame("automation")
        except Exception as e:
            import traceback
            with open("/tmp/VideoAI_Error.txt", "a") as f:
                f.write(f"Init Error: {e}\n{traceback.format_exc()}\n")

    def show_frame(self, name):
        if self.current_frame_name == name:
            return # Đang ở frame đó rồi, không chuyển
            
        # Hide current frame
        if self.current_frame_name and self.current_frame_name in self.frames:
            self.frames[self.current_frame_name].grid_remove()
            
        self.current_frame_name = name
            
        # Tắt bật trạng thái nút (Highlight)
        buttons = {
            "automation": self.btn_automation,
            "ai_video": self.btn_ai_video,
            "editor": self.btn_editor,
            "tiktok_editor": self.btn_tiktok_editor,
            "trimmer": self.btn_trimmer,
            "batch_cutter": self.btn_batch_cutter,
            "converter": self.btn_converter,
            "yt_compiler": self.btn_yt_compiler,
            "watermark": self.btn_watermark,
            "bgm_injector": self.btn_bgm_injector,
            "tiktok": self.btn_tiktok,
            "threads": self.btn_threads,
            "douyin": self.btn_douyin,
            "bot": self.btn_bot,
            "tts": self.btn_tts
        }
        
        for key, btn in buttons.items():
            if key == name:
                btn.configure(fg_color=C_BTN_ACTIVE, text_color=C_TEXT_ACTIVE)
            else:
                btn.configure(fg_color=C_BTN_NORMAL, text_color=C_TEXT_PRIMARY)
                
        # Show requested frame with Slide-Up & Fade Animation
        if name in self.frames:
            target_frame = self.frames[name]
            
            # Khởi tạo thông số cho Animation (Ease-Out Quart)
            start_y_offset = 50
            target_frame.grid(row=0, column=0, sticky="nsew", pady=(start_y_offset, 0), padx=0)
            
            duration_ms = 350
            fps = 60
            total_frames = int(duration_ms / (1000 / fps))
            frame_delay = int(1000 / fps)
            
            def ease_out_quart(t):
                return 1 - pow(1 - t, 4)
                
            def animate_slide(current_frame):
                # Ngăn lỗi Animation tự gọi lại grid_configure sau khi đổi Tab
                if self.current_frame_name != name:
                    return
                    
                if current_frame <= total_frames:
                    t = current_frame / total_frames
                    eased_t = ease_out_quart(t)
                    # Tính toán padding Y
                    current_pad = int(start_y_offset * (1 - eased_t))
                    target_frame.grid_configure(pady=(current_pad, 0))
                    self.after(frame_delay, lambda: animate_slide(current_frame + 1))
                else:
                    target_frame.grid_configure(pady=(0, 0))
            
            animate_slide(1)
            
    def change_theme(self, new_theme):
        ctk.set_appearance_mode(new_theme)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()