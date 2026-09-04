import os
import threading
import time
import random
import customtkinter as ctk
from customtkinter import filedialog

from .styles import F, T1, T2, T3, BG2, BORDER, SEL, GRN, RED, ORG
from .playwright_engine import login_and_save_cookie, post_carousel, get_user_data_dir

class PosterApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.output_dir = ""
        self.excel_path = ""
        self.pairs = [] # List of {"mp4": path, "jpg": path}
        self.history_file = ""
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        # --- CẤU HÌNH ROBOT ---
        f_api = ctk.CTkFrame(self, fg_color="transparent")
        f_api.pack(fill="x", padx=40, pady=(20, 10))
        
        info = "Chế độ: Trâu Cày (Robot Web).\nTool sẽ mở Trình duyệt, Sếp đăng nhập Threads xong TẮT đi để nó ghi nhớ Mãi Mãi."
        ctk.CTkLabel(f_api, text=info, font=F(12), text_color=T2, justify="center").pack(pady=5)
        
        self.btn_login = ctk.CTkButton(f_api, text="🔑 BẤM MỞ TRÌNH DUYỆT ĐỂ ĐĂNG NHẬP", height=40, width=300,
                                       command=self.open_login_browser, fg_color=SEL, hover_color="#006BB3")
        self.btn_login.pack(pady=10)
        
        self.lbl_cookie_status = ctk.CTkLabel(f_api, text="Đang kiểm tra...", text_color=T3)
        self.lbl_cookie_status.pack()
        self.check_cookie()

        # --- CHƯƠNG TRÌNH ĐĂNG ---
        f_load = ctk.CTkFrame(self, fg_color="transparent")
        f_load.pack(fill="x", padx=40, pady=10)
        
        self.btn_load = ctk.CTkButton(f_load, text="📂 Chọn Thư Mục Chứa Video", font=F(12, "bold"), fg_color=BORDER, command=self.load_directory)
        self.btn_load.pack(side="left")
        
        self.lbl_loaded = ctk.CTkLabel(f_load, text="Chưa nạp", text_color=T3, font=F(12))
        self.lbl_loaded.pack(side="left", padx=10)
        
        # --- CẤU HÌNH BIO LINK BAO TRỌN GÓI VÀ TELEGRAM ---
        f_config = ctk.CTkFrame(self, fg_color="transparent")
        f_config.pack(fill="x", padx=40, pady=5)
        
        row_bio = ctk.CTkFrame(f_config, fg_color="transparent")
        row_bio.pack(fill="x", pady=(5, 5))
        ctk.CTkLabel(row_bio, text="🔗 ĐƯỜNG LINK BIO CHUNG (Áp dụng Kẹp vào Mọi Bài Đăng):", text_color="#F43F5E", font=F(12, "bold")).pack(side="left")
        self.e_bio_link = ctk.CTkEntry(row_bio, width=350, placeholder_text="Gắn Link Bio Shopee của Sếp Vào Đây...")
        self.e_bio_link.pack(side="left", padx=10)

        row_tele = ctk.CTkFrame(f_config, fg_color="transparent")
        row_tele.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row_tele, text="🔔 MÃ TOKEN CỦA BOT BÁO CÁO (TELEGRAM):", text_color="#3B82F6", font=F(12, "bold")).pack(side="left")
        self.e_tele_token_b = ctk.CTkEntry(row_tele, width=320, placeholder_text="Mã lấy ở BotFather")
        self.e_tele_token_b.insert(0, "8750842741:AAFeEwZPzjpPOYfhVr4B0aMYiV7S6jQsLbA") # Token Sếp vừa duyệt
        self.e_tele_token_b.pack(side="left", padx=10)

        # Anti Spam Config Row
        row1 = ctk.CTkFrame(f_config, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkLabel(row1, text="⏳ Thời gian nghỉ Ngẫu Nhiên: Từ", text_color=T2).pack(side="left")
        self.e_delay_min = ctk.CTkEntry(row1, width=50)
        self.e_delay_min.insert(0, "300")
        self.e_delay_min.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="đến", text_color=T2).pack(side="left")
        self.e_delay_max = ctk.CTkEntry(row1, width=50)
        self.e_delay_max.insert(0, "600")
        self.e_delay_max.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="(Giây)", text_color=T2).pack(side="left")

        # Break
        row2 = ctk.CTkFrame(f_config, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        ctk.CTkLabel(row2, text="💤 Đăng liên tục", text_color=T2).pack(side="left")
        self.e_break_posts = ctk.CTkEntry(row2, width=40)
        self.e_break_posts.insert(0, "5")
        self.e_break_posts.pack(side="left", padx=5)
        
        ctk.CTkLabel(row2, text="bài, máy móc tự động Ngủ Đông:", text_color=T2).pack(side="left")
        self.e_break_mins = ctk.CTkEntry(row2, width=50)
        self.e_break_mins.insert(0, "60")
        self.e_break_mins.pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="(Phút)", text_color=T2).pack(side="left")

        # START ACTION BTNS
        f_actions = ctk.CTkFrame(self, fg_color="transparent")
        f_actions.pack(pady=15)
        
        self.btn_start = ctk.CTkButton(f_actions, text="🚀 CHẠY AUTO POST", font=F(16, "bold"), height=45, width=150, fg_color=ORG, hover_color="#D97706", command=self.start_posting)
        self.btn_start.pack(side="left", padx=5)
        
        self.btn_prescan = ctk.CTkButton(f_actions, text="👁 QUÉT MẮT AI", font=F(16, "bold"), height=45, width=140, fg_color="#3B82F6", hover_color="#2563EB", command=self.start_prescan)
        self.btn_prescan.pack(side="left", padx=5)
        
        self.btn_pause = ctk.CTkButton(f_actions, text="⏸ TẠM DỪNG", font=F(16, "bold"), height=45, width=120, fg_color=RED, hover_color="#CC0000", command=self.pause_posting, state="disabled")
        self.btn_pause.pack(side="left", padx=5)

        # LOGS
        self.logs = ctk.CTkTextbox(self, font=ctk.CTkFont("Consolas", 12), text_color="#A3E635", fg_color="#0D1117", corner_radius=10, border_width=1, border_color="#30363D", height=160)
        self.logs.pack(fill="both", expand=True, padx=40, pady=(0, 20))
        self.logs.configure(state="disabled")

    def open_login_browser(self):
        threading.Thread(target=lambda: login_and_save_cookie(logger=self.log), daemon=True).start()
        self.after(2000, self.check_cookie)

    def check_cookie(self):
        ud = get_user_data_dir()
        if os.path.exists(ud):
            self.lbl_cookie_status.configure(text="✅ Đã có File Phiên Đăng Nhập. (Sẵn sàng đăng)", text_color=GRN)
            self.btn_login.configure(fg_color=BORDER)
        else:
            self.lbl_cookie_status.configure(text="❌ Chưa có Phiên Đăng Nhập. Bấm nút Tanh bên trên!", text_color=RED)

    def log(self, msg):
        def _append():
            self.logs.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.logs.insert("end", f"[{ts}] {msg}\n")
            self.logs.see("end")
            self.logs.configure(state="disabled")
        self.after(0, _append)

    def start_prescan(self):
        if self.is_running: return
        if not self.pairs:
            self.log("⚠️ Không có Video để quét! Xài nút [Load Thư Mục] trước đê Sếp.")
            return
        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_prescan.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        threading.Thread(target=self.prescan_worker, daemon=True).start()

    def prescan_worker(self):
        self.log("\n==================================")
        self.log("👁 MẮT THẦN GIÁM ĐỊNH SẢN PHẨM TRƯỚC VẠCH XUẤT PHÁT")
        self.log("==================================")
        from .gemini_caption import scan_product_name_from_video
        
        total = len(self.pairs)
        scanned = 0
        
        for idx, pair in enumerate(self.pairs):
            if self.stop_event.is_set():
                self.log("🛑 Dừng quét Mắt Thần.")
                break
                
            v_name = os.path.basename(pair["mp4"])
            self.log(f"[{idx+1}/{total}] Đang ngắm nghía Video: {v_name}")
            
            sp_name = scan_product_name_from_video(pair["mp4"], logger=self.log)
            self.log(f"   => Khẳng định Món Hàng: {sp_name.upper()}")
            
            scanned += 1
            
        self.log("\n✅ ĐÃ QUÉT DỌN PHÂN TÍCH XONG HẾT. CHUẨN BỊ BAY TỐC ĐỘ BÀN THỜ NÀO!!")
        
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_prescan.configure(state="normal")
        self.btn_pause.configure(state="disabled")

    def load_directory(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Đầu Ra chứa Video & Ảnh")
        if not folder: return
        self.output_dir = folder
        
        # Load lịch sử đâm lén
        self.history_file = os.path.join(folder, "threads_posted.txt")
        posted_files = set()
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                posted_files = set(line.strip() for line in f if line.strip())
        
        # Scanner
        files = os.listdir(folder)
        videos = [f for f in files if f.endswith(".mp4")]
        
        self.pairs = []
        skipped = 0
        for v in videos:
            if v in posted_files:
                skipped += 1
                continue
                
            basename = os.path.splitext(v)[0]
            img_name = f"{basename}.jpg"
            if img_name in files:
                self.pairs.append({"mp4": os.path.join(folder, v), "jpg": os.path.join(folder, img_name)})
                
        self.lbl_loaded.configure(text=f"Nạp: {len(self.pairs)} Bài chờ bắn. (Bỏ qua {skipped} cặp đã Up)", text_color=GRN)
        self.log(f"🔎 Quét thư mục... Tìm thấy {len(self.pairs)} bài mới toanh, loại trừ {skipped} bài cũ.")

    def save_history(self, filename):
        if self.history_file:
            try:
                with open(self.history_file, 'a', encoding='utf-8') as f:
                    f.write(f"{filename}\n")
            except:
                pass

    def pause_posting(self):
        if self.is_running:
            self.log("🔥 Đã nhận lệnh ngự bài! Robot sẽ Tạm Dừng sau khi kết thúc chặng hoặc thoát khỏi giấc ngủ ngay lập tức...")
            self.btn_pause.configure(state="disabled", text="ĐANG HUỶ...")
            self.stop_event.set()

    def start_posting(self):
        if self.is_running: return
        if not self.pairs:
            self.log("⚠️ Không có bài viết nào để đăng! Hãy Load Thư mục trước.")
            return
            
        ud = get_user_data_dir()
        if not os.path.exists(ud):
            self.log("⚠️ Bạn chưa Đăng nhập lấy Cookie! Bấm nút Màu xanh trước.")
            return
            
        try:
            d_min = int(self.e_delay_min.get().strip())
            d_max = int(self.e_delay_max.get().strip())
            b_posts = int(self.e_break_posts.get().strip())
            b_mins = int(self.e_break_mins.get().strip())
        except:
            d_min, d_max, b_posts, b_mins = 300, 600, 5, 60
            
        if d_min > d_max: d_min, d_max = d_max, d_min
            
        self.log("🎲 Đang xáo trộn ngẫu nhiên thứ tự bài đăng...")
        random.shuffle(self.pairs)
            
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
        self.log("🚀 MỞ LỒNG THẢ TRÂU CÀY (CHẾ ĐỘ ANTI-SPAM BẬT)...")
        
        bio_link = self.e_bio_link.get().strip()
        total = len(self.pairs)
        success = 0
        posts_since_break = 0
        
        for idx, pair in enumerate(self.pairs):
            if self.stop_event.is_set():
                self.log("🛑 Robot đã Bị Vô Hiệu Hoá Chặn Đứng Hoàn Toàn theo Lệnh Vua.")
                break
                
            v_name = os.path.basename(pair["mp4"])
            
            self.log(f"\n--- Bài Cày {idx+1}/{total}: {v_name} ---")
            
            try:
                from .playwright_engine import post_carousel
            except Exception as e:
                self.log(f"Module Engine Khởi Động Lỗi To: {e}")
                break
            
            # Cắm thẳng Link Bio Chung vào cho Trình duyệt Chèn vào Sau Caption
            res = post_carousel(pair["mp4"], pair["jpg"], bio_link=bio_link, logger=self.log)
            if res:
                success += 1
                posts_since_break += 1
                self.log(f"✅ ĐÃ ĐĂNG: {v_name}")
                with open(self.history_file, "a", encoding="utf-8") as f:
                    f.write(v_name + "\n")
                    
                # [LÍNH LIÊN LẠC TELEGRAM MỘT CHIỀU CO ĐỊNH]
                tele_token = self.e_tele_token_b.get().strip()
                if tele_token:
                    import requests
                    try:
                        t_chat = getattr(self, "cached_chat_id", None)
                        if not t_chat:
                            # Fetch Chat ID tự động bằng API
                            resp = requests.get(f"https://api.telegram.org/bot{tele_token}/getUpdates").json()
                            if resp.get("ok") and resp.get("result"):
                                t_chat = resp["result"][-1]["message"]["chat"]["id"]
                                self.cached_chat_id = t_chat
                        
                        if t_chat:
                            msg = f"✅ BÁO CÁO NHIỆM VỤ THÀNH CÔNG\n📌 Món Hàng Vừa Lên Tường: {v_name}\n🚀 Tốc độ Máy Bay Không Người Lái!"
                            requests.post(f"https://api.telegram.org/bot{tele_token}/sendMessage", json={"chat_id": t_chat, "text": msg})
                    except Exception as e:
                        self.log(f"⚠️ Không bắn được thông báo Tele: {e}")
            else:
                fail += 1
                self.log(f"❌ THẤT BẠI: {v_name}")
                tele_token = self.e_tele_token_b.get().strip()
                if tele_token:
                    import requests
                    try:
                        t_chat = getattr(self, "cached_chat_id", None)
                        if t_chat:
                            msg = f"❌ BÁO ĐỘNG ĐỎ: Lỗi đứt xích bài {v_name} rồi Sếp ơi!"
                            requests.post(f"https://api.telegram.org/bot{tele_token}/sendMessage", json={"chat_id": t_chat, "text": msg})
                    except: pass
                
            # Nghỉ ngơi Tránh bão
            if idx < total - 1 and not self.stop_event.is_set():
                if b_posts > 0 and posts_since_break >= b_posts:
                    sleep_time = b_mins * 60
                    if not self.smart_sleep(sleep_time, f"🔔 Đã Quota {posts_since_break} bài. Bật mode NGỦ ĐÔNG {b_mins} phút..."):
                        continue
                    posts_since_break = 0
                else:
                    sleep_time = random.randint(d_min, d_max)
                    if not self.smart_sleep(sleep_time, f"💤 Tạm tắt trình duyệt, trâu xả hơi ngẫu nhiên {sleep_time} giây..."):
                        continue
                
        self.is_running = False
        self.after(0, self.reset_buttons)
        self.log(f"\n✅ TỔNG KẾT: Cày bừa được {success}/{total} Mẫu. Rút quân!")

    def reset_buttons(self):
        self.btn_start.configure(state="normal", fg_color=ORG)
        self.btn_pause.configure(state="disabled", text="⏸ TẠM DỪNG")