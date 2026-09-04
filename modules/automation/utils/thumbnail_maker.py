import os
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import sys

# Khai báo đường dẫn root để load Cấu hình
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config.config as cfg

def create_thumbnail(video_path, title_text, output_thumb_path):
    """
    Trích xuất Frame ở giây thứ 2 của video, phủ sương mù, 
    giảm sáng và dập text Tiêu Đề Clickbait lên giữa ảnh.
    Trả về True nếu thành công.
    """
    try:
        temp_frame = output_thumb_path + "_raw.jpg"
        
        # 1. Trích xuất frame giây thứ 2 bằng FFmpeg
        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:02", "-i", video_path, 
            "-frames:v", "1", "-q:v", "2", temp_frame
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if not os.path.exists(temp_frame):
            return False

        # 2. Xử lý ảnh bằng Pillow
        with Image.open(temp_frame) as raw_img:
            img = raw_img.convert("RGB")
            
            # Làm mờ sương (Blur)
            img = img.filter(ImageFilter.GaussianBlur(15))
            
            # Hạ độ sáng làm nền đen mờ
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(0.5)  # Tối đi 50%
            
            # 3. Chuẩn bị Vẽ Chữ Khổng Lồ
            draw = ImageDraw.Draw(img)
            width, height = img.size
            
            # Tìm kích thước Font phù hợp để chữ ko quá bé / quá to
            font_size = int(width * 0.08)  # Cỡ chữ tỷ lệ 8% chiều ngang
            font_path = os.path.join(cfg.ASSETS_DIR, cfg.FONT_NAME)
            
            try:
                font = ImageFont.truetype(font_path, font_size)
            except IOError:
                # Fallback nếu lỗi đường dẫn font
                try:
                    font = ImageFont.truetype(cfg.FONT_PATH, font_size)
                except IOError:
                    font = ImageFont.load_default()
                    
            text = str(title_text).upper()
            
            # Tính toán vị trí X Y Căn Giữa màn hình
            # PIL >= 8.0 sử dụng textbbox
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except Exception:
                text_w, text_h = draw.textsize(text, font=font)
                
            x = (width - text_w) / 2
            y = (height - text_h) / 2
            
            # Viết chữ (Có Stroke đen để nổi bật)
            stroke_width = max(2, int(font_size * 0.05))
            
            draw.text((x, y), text, font=font, fill="yellow", 
                      stroke_width=stroke_width, stroke_fill="black")
            
            img.save(output_thumb_path, "JPEG", quality=90)
            
        os.remove(temp_frame)
        return True
    except Exception as e:
        print(f"❌ Lỗi tạo Thumbnail Ảnh Bìa: {e}")
        return False

# Test độc lập
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 3:
        create_thumbnail(sys.argv[1], sys.argv[2], sys.argv[3])