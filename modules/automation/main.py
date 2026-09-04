import os
import sys
import shutil

# Import cấu hình để kiểm tra thư mục
from config.config import INPUT_DIR, OUTPUT_DIR, TEMP_DIR, PROCESSED_DIR, ASSETS_DIR, FONT_PATH

# Import giao diện chính
from gui import VideoAutomationApp

def setup_environment():
    """
    Hàm này chạy đầu tiên để đảm bảo mọi thứ sẵn sàng trước khi bật App.
    """
    print("🚀 Đang khởi động VIDEO AUTOMATION PRO...")
    
    # 1. Tạo các thư mục bắt buộc nếu chưa có
    directories = [INPUT_DIR, OUTPUT_DIR, TEMP_DIR, PROCESSED_DIR, ASSETS_DIR]
    for d in directories:
        if not os.path.exists(d):
            print(f"🛠️ Đang tạo thư mục: {d}")
            os.makedirs(d, exist_ok=True)

    # 2. Kiểm tra Font chữ (Rất quan trọng, tránh lỗi lúc đang chạy dở)
    if not os.path.exists(FONT_PATH):
        print(f"⚠️ CẢNH BÁO: Không tìm thấy file font tại: {FONT_PATH}")
        print("👉 Vui lòng kiểm tra lại thư mục assets/ hoặc config.py")
    else:
        print(f"✅ Đã tìm thấy Font: {os.path.basename(FONT_PATH)}")

    # 3. Dọn dẹp thư mục Temp cũ (nếu có rác từ lần chạy trước)
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
            os.makedirs(TEMP_DIR)
            print("🧹 Đã dọn dẹp file tạm (Temp files).")
        except Exception as e:
            print(f"⚠️ Không thể dọn dẹp thư mục Temp: {e}")

def main():
    # Bước 1: Setup môi trường
    setup_environment()
    
    print("✨ Mọi thứ đã sẵn sàng. Đang mở giao diện...")
    
    # Bước 2: Khởi chạy ứng dụng Giao diện (GUI)
    app = VideoAutomationApp()
    
    # Bước 3: Giữ app chạy liên tục
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\n🛑 Đã dừng chương trình bằng bàn phím.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Lỗi không mong muốn: {e}")

if __name__ == "__main__":
    main()