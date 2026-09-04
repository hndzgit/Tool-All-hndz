import os
import threading
import time
import random
import customtkinter as ctk
from customtkinter import filedialog

from threads.styles import F, T1, T2, T3, BG2, BORDER, SEL, GRN, RED, ORG
from .playwright_tiktok import login_and_save_cookie, post_tiktok_video, get_user_data_dir

class TikTokApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.output_dir = ""
        self.videos = [] # List of mp4 paths
        self.history_file = ""
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        # --- CẤU HÌNH ROBOT ---
        f_api = ctk.CTkFrame(self, fg_color="transparent")
        f_api.pack(fill="x", padx=40, pady=(20, 10))
        
        info = "Chế độ: Auto-Playwright (TikTok).\nTool sẽ mở Trình duyệt Chrome, Sếp đăng nhập TikTok xong TẮT đi để Robot ghi nhớ."
        ctk.CTkLabel(f_api, text=info, font=F(12), text_color=T2, justify="center").pack(pady=5)
        
        self.btn_login = ctk.CTkButton(f_api, text="🔑 BẤM MỞ TRÌNH DUYỆT ĐỂ ĐĂNG NHẬP TIKTOK", height=40, width=320,
                                       command=self.open_login_browser, fg_color="#FE2C55", hover_color="#E0294D")
        self.btn_login.pack(pady=10)
        
        self.lbl_cookie_status = ctk.CTkLabel(f_api, text="Đang kiểm tra...", text_color=T3)
        self.lbl_cookie_status.pack()
        self.check_cookie()

        # --- CHƯƠNG TRÌNH ĐĂNG ---
        f_load = ctk.CTkFrame(self, fg_color="transparent")
        f_load.pack(fill="x", padx=40, pady=10)
        
        self.btn_load = ctk.CTkButton(f_load, text="📂 Chọn Thư Mục Chứa Video", font=F(12, "bold"), fg_color=BORDER, text_color="white", command=self.load_directory)
        self.btn_load.pack(side="left")
        
        self.lbl_loaded = ctk.CTkLabel(f_load, text="Chưa nạp Video", text_color=T3, font=F(12))
        self.lbl_loaded.pack(side="left", padx=10)
        
        # --- CẤU HÌNH HASHTAG CHUNG ---
        f_config = ctk.CTkFrame(self, fg_color="transparent")
        f_config.pack(fill="x", padx=40, pady=5)
        
        row_hash = ctk.CTkFrame(f_config, fg_color="transparent")
        row_hash.pack(fill="x", pady=(5, 5))
        ctk.CTkLabel(row_hash, text="🏷 HASHTAG CHUNG (Nếu có):", text_color="#10B981", font=F(12, "bold")).pack(side="left")
        self.e_hashtag = ctk.CTkEntry(row_hash, width=350, placeholder_text="#xuhuong #trending #review")
        self.e_hashtag.pack(side="left", padx=10)

        # Anti Spam Config Row
        row1 = ctk.CTkFrame(f_config, fg_color="transparent")
        row1.pack(fill="x", pady=5)
        ctk.CTkLabel(row1, text="⏳ Thời gian nghỉ Ngẫu Nhiên: Từ", text_color=T2).pack(side="left")
        self.e_delay_min = ctk.CTkEntry(row1, width=50)
        self.e_delay_min.insert(0, "60")
        self.e_delay_min.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="đến", text_color=T2).pack(side="left")
        self.e_delay_max = ctk.CTkEntry(row1, width=50)
        self.e_delay_max.insert(0, "150")
        self.e_delay_max.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="(Giây)", text_color=T2).pack(side="left")

        # Break
        row2 = ctk.CTkFrame(f_config, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        ctk.CTkLabel(row2, text="💤 Đăng liên tục", text_color=T2).pack(side="left")
        self.e_break_posts = ctk.CTkEntry(row2, width=40)
        self.e_break_posts.insert(0, "10")
        self.e_break_posts.pack(side="left", padx=5)
        
        ctk.CTkLabel(row2, text="bài, máy móc tự động Ngủ Đông:", text_color=T2).pack(side="left")
        self.e_break_mins = ctk.CTkEntry(row2, width=50)
        self.e_break_mins.insert(0, "60")
        self.e_break_mins.pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="(Phút)", text_color=T2).pack(side="left")

        # START ACTION BTNS
        f_actions = ctk.CTkFrame(self, fg_color="transparent")
        f_actions.pack(pady=15)
        
        self.btn_start = ctk.CTkButton(f_actions, text="🚀 CHẠY AUTO TIKTOK", font=F(16, "bold"), height=45, width=180, fg_color="#FE2C55", hover_color="#E0294D", command=self.start_posting)
        self.btn_start.pack(side="left", padx=5)
        
        self.btn_pause = ctk.CTkButton(f_actions, text="⏸ TẠM DỪNG", font=F(16, "bold"), height=45, width=120, fg_color=RED, hover_color="#CC0000", command=self.pause_posting, state="disabled")
        self.btn_pause.pack(side="left", padx=5)

        # Hẹn giờ
        self.sch_var = ctk.BooleanVar(value=False)
        self.chk_schedule = ctk.CTkCheckBox(f_actions, text="Đăng Lưu Nháp (Bản Thảo)", font=F(13,"bold"), variable=self.sch_var, text_color=T2, fg_color=SEL)
        self.chk_schedule.pack(side="left", padx=(15, 5))

        # LOGS
        self.logs = ctk.CTkTextbox(self, font=ctk.CTkFont("Consolas", 12), text_color="#A3E635", fg_color="#0D1117", corner_radius=10, border_width=1, border_color="#30363D", height=180)
        self.logs.pack(fill="both", expand=True, padx=40, pady=(0, 20))
        self.logs.configure(state="disabled")

    def open_login_browser(self):
        threading.Thread(target=lambda: login_and_save_cookie(logger=self.log), daemon=True).start()
        self.after(2000, self.check_cookie)

    def check_cookie(self):
        ud = get_user_data_dir()
        if os.path.exists(ud):
            self.lbl_cookie_status.configure(text="✅ Đã có File Phiên Đăng Nhập. (Sẵn sàng chiến)", text_color=GRN)
            self.btn_login.configure(fg_color=BORDER)
        else:
            self.lbl_cookie_status.configure(text="❌ Chưa có Phiên Đăng Nhập TikTok. Bấm nút mào đỏ bên trên!", text_color=RED)

    def log(self, msg):
        def _append():
            self.logs.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.logs.insert("end", f"[{ts}] {msg}\n")
            self.logs.see("end")
            self.logs.configure(state="disabled")
        self.after(0, _append)

    def load_directory(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Chứa Video TikTok")
        if not folder: return
        self.output_dir = folder
        
        # Load lịch sử đâm lén
        self.history_file = os.path.join(folder, "tiktok_posted.txt")
        posted_files = set()
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                posted_files = set(line.strip() for line in f if line.strip())
        
        files = os.listdir(folder)
        videos = [f for f in files if f.endswith(".mp4")]
        
        self.videos = []
        skipped = 0
        for v in videos:
            if v in posted_files:
                skipped += 1
                continue
            self.videos.append(os.path.join(folder, v))
                
        self.lbl_loaded.configure(text=f"Nạp: {len(self.videos)} Video chờ bắn. (Bỏ qua {skipped} Video đã Up)", text_color=GRN)
        self.log(f"🔎 Quét thư mục... Cầm cờ {len(self.videos)} Video Mới, loại trừ {skipped} Video Cũ.")

    def pause_posting(self):
        if self.is_running:
            self.log("🔥 Đã nhận lệnh ngự bài! Robot sẽ Tạm Dừng sau khi up xong video hiện tại...")
            self.btn_pause.configure(state="disabled", text="ĐANG HUỶ...")
            self.stop_event.set()

    def start_posting(self):
        if self.is_running: return
        if not self.videos:
            self.log("⚠️ Không có video nào để Up! Dùng Nút chọn Thư mục trước.")
            return
            
        ud = get_user_data_dir()
        if not os.path.exists(ud):
            self.log("⚠️ Bạn chưa Đăng nhập lấy Cookie TikTok! Bấm nút Màu đỏ bên trên.")
            return
            
        try:
            d_min = int(self.e_delay_min.get().strip())
            d_max = int(self.e_delay_max.get().strip())
            b_posts = int(self.e_break_posts.get().strip())
            b_mins = int(self.e_break_mins.get().strip())
        except:
            d_min, d_max, b_posts, b_mins = 60, 150, 10, 60
            
        if d_min > d_max: d_min, d_max = d_max, d_min
            
        self.log("🎲 Đang đảo lộn trật tự lên Video ngẫu nhiên...")
        random.shuffle(self.videos)
            
        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", fg_color=T3)
        self.btn_pause.configure(state="normal", text="⏸ TẠM DỪNG", text_color=T1)
        threading.Thread(target=self.post_worker, args=(d_min, d_max, b_posts, b_mins), daemon=True).start()

    def smart_sleep(self, seconds, message=""):
        if message: self.log(message)
        for _ in range(seconds):
            if self.stop_event.is_set():
                return False
            time.sleep(1)
        return True

    def post_worker(self, d_min, d_max, b_posts, b_mins):
        self.log("🚀 MỞ LỒNG THẢ CHÓ (TIKTOK ANTI-SPAM BẬT)...")
        
        hashtag = self.e_hashtag.get().strip()
        total = len(self.videos)
        success = 0
        fail = 0
        posts_since_break = 0
        from threads.gemini_caption import get_caption_from_video
        
        for idx, v_path in enumerate(self.videos):
            if self.stop_event.is_set():
                self.log("🛑 Robot đã Bị Vô Hiệu Hoá thành công.")
                break
                
            v_name = os.path.basename(v_path)
            self.log(f"\n--- Băng Chuyền TikTok {idx+1}/{total}: {v_name} ---")
            
            # Quét Caption tự động qua AI trước
            self.log("👁 Đang quét AI tự sáng tác Caption phù hợp với Video này...")
            caption, _, product_name = get_caption_from_video(v_path, logger=self.log)
            if not caption:
                caption = f"Lại là {product_name if product_name else 'siêu phẩm'} đây anh em ơi!!! Gét Gô!"
                
            self.log(f"📝 Caption Mẫu Của AI: '{caption}'")
            
            # Gửi lên TikTok Robot
            res = post_tiktok_video(v_path, caption=caption, hashtags=hashtag, logger=self.log)
            
            if res:
                success += 1
                posts_since_break += 1
                self.log(f"✅ ĐÃ ĐĂNG TIKTOK THÀNH CÔNG: {v_name}")
                with open(self.history_file, "a", encoding="utf-8") as f:
                    f.write(v_name + "\n")
            else:
                fail += 1
                self.log(f"❌ UP TIKTOK THẤT BẠI: {v_name}")
                
            # Nghỉ ngơi Tránh bão spam
            if idx < total - 1 and not self.stop_event.is_set():
                if b_posts > 0 and posts_since_break >= b_posts:
                    sleep_time = b_mins * 60
                    if not self.smart_sleep(sleep_time, f"🔔 Đã chạy đủ {posts_since_break} nháy. Máy móc đi NGỦ ĐÔNG {b_mins} phút..."):
                        continue
                    posts_since_break = 0
                else:
                    sleep_time = random.randint(d_min, d_max)
                    if not self.smart_sleep(sleep_time, f"💤 Tạm tắt trình duyệt thả lỏng AI {sleep_time} giây chờ Clip Tiếp Theo..."):
                        continue
                
        self.is_running = False
        self.after(0, self.reset_buttons)
        self.log(f"\n✅ DOOM! Xong Việc! Up thành công {success}/{total} Clip lên TikTok. Thất bại: {fail}.")

    def reset_buttons(self):
        self.btn_start.configure(state="normal", fg_color="#FE2C55")
        self.btn_pause.configure(state="disabled", text="⏸ TẠM DỪNG")