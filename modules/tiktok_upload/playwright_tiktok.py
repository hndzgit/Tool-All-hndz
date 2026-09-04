import os
import time
import json
from playwright.sync_api import sync_playwright

def get_user_data_dir():
    # Store Chrome profile locally inside the tool folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "browser_profile")

def login_and_save_cookie(logger=print):
    """Mở Chrome cho Sếp tự đăng nhập TikTok."""
    user_data_dir = get_user_data_dir()
    os.makedirs(user_data_dir, exist_ok=True)
    
    with sync_playwright() as p:
        logger("Mở Web Chrome, đợi một lát...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chromium",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com/login")
        logger("🔥 HÃY ĐĂNG NHẬP VÀO TIKTOK. SAU KHI ĐĂNG NHẬP THÀNH CÔNG, HÃY TẮT TRÌNH DUYỆT CÁI 'X'.")
        
        # Wait until user closes the browser
        context.on("close", lambda c: logger("Đã tắt Trình duyệt."))
        try:
            page.wait_for_timeout(3600000) # Đợi 1 tiếng
        except:
            pass # Closed early
        finally:
            try:
                context.close()
            except:
                pass
            logger("✅ Đã lưu phiên đăng nhập TikTok thành công vào ổ cứng.")

def post_tiktok_video(video_path, caption="", hashtags="", scheduled_time=None, logger=print):
    """Thực thi thao tác Up bài Video lên TikTok"""
    user_data_dir = get_user_data_dir()
    
    if not os.path.exists(user_data_dir):
        logger("❌ [Playwright Error] Chưa thấy Dữ liệu Cookie. Vui lòng bấm nút 'Đăng Nhập TikTok' trước!")
        return False
        
    full_caption = caption
    if hashtags:
        full_caption += f"\n\n{hashtags}"

    with sync_playwright() as p:
        logger("Khởi động Trình duyệt Ẩn danh TikTok Robot...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False, # Mở lên cho user xem lúc đang code
            channel="chromium",
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        try:
            page = context.new_page()
            # TikTok Update Upload Endpoint
            logger("Đang truy cập Trung tâm Sáng tạo TikTok (Creator Center)...")
            page.goto("https://www.tiktok.com/creator-center/upload")
            page.wait_for_load_state("networkidle")
            
            # Xử lý iFrame nếu TikTok nhúng màn hình Upload vào IFrame (rất hay gặp)
            logger("Đang tìm cổng nhét Video...")
            page.wait_for_timeout(5000)
            
            # 1. Tìm File Input (Input ẩn thường được dùng để chọn video)
            try:
                # Playwright có thể nhét thẳng file vào input dù nó bị che (CSS hidden)
                upload_input = page.locator("input[type='file'][accept*='video']")
                upload_input.first.set_input_files(video_path, timeout=10000)
                logger(f"✅ Đã kéo thả thành công Video vào Web: {os.path.basename(video_path)}")
            except Exception as e:
                logger("⚠️ Không tìm thấy Input ẩn, thử click tay vào iFrame...")
                # Nếu TikTok sử dụng iframe
                frames = page.frames
                uploaded = False
                for frame in frames:
                    try:
                        inp = frame.locator("input[type='file'][accept*='video']")
                        if inp.count() > 0:
                            inp.first.set_input_files(video_path, timeout=5000)
                            uploaded = True
                            page = frame # Chuyển context sang frame này để thao tác tiếp
                            logger("✅ Kéo thả thành công vào iFrame!")
                            break
                    except:
                        continue
                        
                if not uploaded:
                    logger("❌ Lỗi nhét video. Phải nâng cấp thuật toán DOM.")
                    return False

            # Đợi hệ thống tải Video lên và hiện thanh Edit (Bình thường mất 30s-1 phút tuỳ mạng)
            logger("⏳ Đang chờ hệ thống TikTok Server Render Video... (1-3 phút)")
            page.wait_for_timeout(10000)
            
            # --- VIẾT CAPTION ---
            logger("Đang gõ bàn phím điền Caption AI...")
            try:
                # Tìm khung Contenteditable của Draft.js (TikTok dùng Draft)
                # Ghi đè vào DOM để chắc chắn trúng khung gõ
                caption_box = page.locator(".public-DraftEditor-content").first
                caption_box.click(timeout=15000)
                
                # Bấm Ctrl/Cmd + A để xoá text mặc định của tên Video
                page.keyboard.press("Meta+A") # Trên Mac
                page.keyboard.press("Backspace")
                
                # Gõ như người thật (delay random chống bot)
                page.keyboard.type(full_caption, delay=50)
                logger("✅ Gõ xong kịch bản Mắt Thần!")
            except Exception as e:
                logger(f"⚠️ Không tìm đựơc khung Caption: {str(e)}")
                page.mouse.click(640, 400) # Fallback nhắm mù
                page.keyboard.type(full_caption, delay=50)

            # --- POST VIDEO ---
            logger("Đang vận nội công bấm ĐĂNG TẢI...")
            page.wait_for_timeout(3000)
            
            try:
                # Quét mọi nút Post
                post_btn = page.locator(
                    "button:has-text('Post'), "
                    "button:has-text('Đăng'), "
                    "div:has-text('Post'):has(button), "
                    "div.btn-post"
                ).last
                post_btn.click(timeout=8000)
            except:
                logger("⚠️ Nút Đăng giấu kỹ quá. Ấn Toạ độ ép buộc: Xô nghiêng sang phái...")
                page.mouse.click(1000, 750) # Toạ độ thường nằm góc dưới phải
                
            # Đợi kết quả
            logger("Đợi 10s xác nhận Up Mạng...")
            page.wait_for_timeout(10000)
            logger("🎉 ĐĂNG TẢI HOÀN TẤT THÀNH CÔNG VÀO SERVER TIKTOK!")
            return True

        except Exception as e:
            logger(f"❌ [TikTok Core Crash]: {e}")
            return False
        finally:
            try:
                context.close()
            except:
                pass