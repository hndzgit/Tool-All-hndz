import threading
import asyncio
import customtkinter as ctk

# Thêm path
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from bot.bot_main import app as bot_app

class BotApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)

        self.bot_thread = None
        self.bot_loop = None
        self.is_running = False

        self.setup_ui()

    def setup_ui(self):
        title_label = ctk.CTkLabel(self, text="TELEGRAM BOT MANAGER", font=("Arial", 24, "bold"))
        title_label.pack(pady=20)

        info_label = ctk.CTkLabel(self, text="Bot hỗ trợ tải video TikTok/Douyin/YouTube từ Telegram.\nBot Token được cấu hình trực tiếp trong mã nguồn.", justify="center")
        info_label.pack(pady=10)

        self.btn_toggle = ctk.CTkButton(self, text="▶ START BOT", font=("Arial", 16, "bold"), height=50, fg_color="#107C41", hover_color="#0b5c30", command=self.toggle_bot)
        self.btn_toggle.pack(pady=20)

        self.lbl_status = ctk.CTkLabel(self, text="Bot đang tắt", text_color="gray")
        self.lbl_status.pack()

    def toggle_bot(self):
        if not self.is_running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self):
        self.btn_toggle.configure(text="⏳ Đang khởi động...", state="disabled")
        self.lbl_status.configure(text="Đang kết nối...", text_color="orange")
        
        # Bắt đầu bot trên luồng riêng
        self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
        self.bot_thread.start()

    def run_bot_thread(self):
        self.bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_loop)
        
        self.btn_toggle.configure(text="⏹ STOP BOT", fg_color="#D32F2F", hover_color="#B71C1C", state="normal")
        self.lbl_status.configure(text="✅ Bot đang chạy", text_color="green")
        self.is_running = True

        try:
            bot_app.run_polling(stop_signals=[]) # Vô hiệu hóa signal handlers để tránh lỗi không chạy ở luồng chính
        except Exception as e:
            print(f"Bot error: {e}")
        finally:
            self.is_running = False
            self.btn_toggle.configure(text="▶ START BOT", fg_color="#107C41", hover_color="#0b5c30", state="normal")
            self.lbl_status.configure(text="Bot đã dừng", text_color="gray")

    def stop_bot(self):
        if self.is_running and self.bot_loop:
            self.btn_toggle.configure(text="⏳ Đang dừng...", state="disabled")
            self.lbl_status.configure(text="Đang ngắt kết nối...", text_color="orange")
            
            # Đẩy task dừng bot vào event loop
            if bot_app.updater:
                asyncio.run_coroutine_threadsafe(bot_app.updater.stop(), self.bot_loop)
                asyncio.run_coroutine_threadsafe(bot_app.stop(), self.bot_loop)

if __name__ == "__main__":
    app = ctk.CTk()
    app.geometry("600x400")
    frame = BotApp(app)
    frame.pack(fill="both", expand=True)
    app.mainloop()
