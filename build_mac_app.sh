#!/bin/bash

# Navigate to the script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/modules"

echo "[+] Kích hoạt môi trường ảo..."
source venv_main/bin/activate

echo "[+] Cài đặt PyInstaller..."
pip install pyinstaller

echo "[+] Đang đóng gói ứng dụng bằng PyInstaller..."
# --windowed: creates a Mac .app bundle and hides the terminal console
# --noconfirm: overwrites the output directory without asking
# --collect-all: ensures all data files and hidden imports for a library are included

pyinstaller --windowed --noconfirm \
    --name "Video AI Pro Studio" \
    --collect-all customtkinter \
    --collect-all playwright \
    --collect-all moviepy \
    --add-data "automation:automation" \
    --add-data "watermark:watermark" \
    --add-data "douyin:douyin" \
    --add-data "bot:bot" \
    --add-data "threads:threads" \
    --add-data "tiktok_upload:tiktok_upload" \
    --add-data "trimmer:trimmer" \
    --add-data "manual_editor:manual_editor" \
    --add-data "ratio_converter:ratio_converter" \
    main_gui.py

echo "[+] Hoàn tất! Ứng dụng đã được tạo tại: $DIR/modules/dist/Video AI Pro Studio.app"
echo "[+] Bạn có thể di chuyển file .app ra ngoài hoặc vào thư mục Applications để dùng."