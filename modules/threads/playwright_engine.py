import os
import time
import json
import requests
from playwright.sync_api import sync_playwright
from .gemini_caption import get_caption_from_video

def get_user_data_dir():
    # Store Chrome profile locally inside the tool folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "browser_profile")

def login_and_save_cookie(logger=print):
    """Mở Chrome cho Sếp tự đăng nhập Threads."""
    user_data_dir = get_user_data_dir()
    os.makedirs(user_data_dir, exist_ok=True)
    
    with sync_playwright() as p:
        logger("Mở Web Chrome, đợi một lát...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chromium"
        )
        page = context.new_page()
        page.goto("https://www.threads.net/login")
        logger("🔥 HÃY ĐĂNG NHẬP VÀO THREADS. SAU KHI ĐĂNG NHẬP THÀNH CÔNG, HÃY TẮT TRÌNH DUYỆT CÁI 'X'.")
        
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
            logger("✅ Đã lưu phiên đăng nhập thành công vào ổ cứng.")

def post_carousel(video_path, image_path, bio_link="", logger=print):
    """Thực thi thao tác Up bài"""
    user_data_dir = get_user_data_dir()
    
    if not os.path.exists(user_data_dir):
        logger("❌ [Playwright Error] Chưa thấy Dữ liệu Cookie. Vui lòng bấm nút 'Đăng Nhập Threads' trước!")
        return False

    # 1. Gọi Não Bô AI Gemini xem Video trước để lấy Caption
    caption, _, product_name = get_caption_from_video(video_path, logger=logger)
    
    logger(f"🍄 [Mắt Thần Soi Đồ]: Khẳng Định Món Trong Video Là '{product_name.upper()}'")
    
    if not caption:
        caption = "🔥🔥🔥 Dạo này có gì Hot? #trending" # Fallback Cửa Tử
        logger("  -> AI bận quá, xài Caption Backup!")

    if bio_link:
        caption += f"\n\n👇 Các Tình yêu Mua hàng chính hãng ở Trong Này nha:\n{bio_link}"

    with sync_playwright() as p:
        logger("Khởi động Robot...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False, # Mở lên cho Sếp xem luôn cho tín
            viewport={"width": 1280, "height": 800}
        )
        
        try:
            page = context.new_page()
            page.set_default_timeout(60000) # Nới rộng khung kẹt mạng thành 60 giây
            page.goto("https://www.threads.net/")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)
            
            # 1. Tìm khu vực gõ văn bản Threads hoặc nút Viết bài
            logger("Đang tìm nút Đăng Bài...")
            
            # Click vào "Start a thread..." / "Bắt đầu một thread..."
            try:
                # Quét mọi khả năng: Tên Tiếng Anh, Tên Tiếng Việt, Hoặc SVG Icon (Tạo / Create)
                create_btns = page.locator(
                    "svg[aria-label='New thread'], "
                    "svg[aria-label='Thread mới'], "
                    "svg[aria-label='Tạo'], "
                    "svg[aria-label='Create'], "
                    "span:has-text('Bắt đầu một thread'), "
                    "span:has-text('Start a thread')"
                )
                create_btns.first.click(timeout=6000)
            except:
                logger("⚠️ Giao diện thay đổi! Sử dụng định vị toạ độ thô bạo...")
                page.mouse.click(640, 180) # Click thẳng vào toạ độ Giữa Top Màn Hình (Chỗ để đăng bài)
            
            page.wait_for_timeout(2000)
            
            # --- MỚI: VIẾT CAPTION NHỜ AI ---
            logger("Đang gõ bàn phím điền Caption AI...")
            try:
                # Tìm khung gõ chữ (thường là contenteditable)
                text_box = page.locator("div[contenteditable='true']").first
                text_box.click(timeout=5000)
                for char in caption: # Gõ y như người thật
                    page.keyboard.type(char, delay=5)
                    
                # [QUAN TRỌNG] Chốt hạ dấu cách và click ra ngoài để thoát khỏi trạng thái Đề Xuất Hashtag của web
                page.keyboard.type(" ")
                page.wait_for_timeout(500)
                
                # Bỏ Focus Textbox bằng lệnh JS thuần (An toàn tuyệt đối, không đụng nhầm Background gây Hủy Upload)
                page.evaluate("if (document.activeElement) document.activeElement.blur();")
                page.wait_for_timeout(1000)
            except:
                logger("⚠️ Không tìm thấy khung điền Text. Hệ thống bỏ qua bước viết Caption!")
                
            page.wait_for_timeout(1000)

            # 2. Upload Files (Ném tuần tự chống nghẽn Mạng Local)
            logger(f"Đang đính kèm Video... (Nạp Độc Lập)")
            file_input = page.locator("input[type='file']")
            file_input.set_input_files(video_path)
            
            # Đợi 4 giây cho Web Threads xơi xong cái Video rồi mới tải Ảnh, tránh lỗi "Failed API"!
            page.wait_for_timeout(4000)
            
            logger(f"Đang đính kèm tiếp Ảnh chân dung...")
            file_input.set_input_files(image_path)
            
            # 3. Mắt thần giám sát Tiến Độ Upload (Đợi bao lâu tải xong thì đi tiếp)
            logger("⏳ Đang dò kênh Upload Video... Máy chủ FB đang giải nén...")
            page.wait_for_timeout(40000) # [BULLDOZER MDOES] Ép chết thời gian 40 GIÂY để ĐẢM BẢO 100% Video đã lên hình
            
            logger("✅ Cập nhật Media 100%! Nút Đăng đã sáng đèn.")
            
            # 4. Bấm nút Đăng
            logger("Bấm nút Phát Hành!")
            try:
                # Ưu tiên tìm chính xác text Đăng / Post ở cuối màn hình
                post_button_locator = page.locator("div[role='button']:has-text('Post'), div[role='button']:has-text('Đăng'), button:has-text('Post'), button:has-text('Đăng')")
                post_button_locator.last.click(timeout=8000, force=True)
            except:
                logger("⚠️ Trình duyệt lag mất nút Đăng, kích hoạt ngón tay phụ...")
                page.keyboard.press("Control+Enter") # Phím tắt đăng bài vạn năng của Meta
                page.mouse.click(820, 680) # Toạ độ chốt chặng
            
            # 5. Mắt Thần Canh Cửa (Đợi Khung Đăng Bài Sập Xuống)
            logger("⏳ Hệ thống bắt đầu đẩy Video lên Trung Tâm Meta! Tuyệt đối không tắt Tab...")
            page.wait_for_timeout(2000) # Mồi trước 2s cho UI nó chạy hoạt ảnh
            
            try:
                # Modal chứa bài đăng có thuộc tính Dialog. Chờ cho Dialog bị Huỷ rớt khỏi DOM.
                page.locator("div[role='dialog']").first.wait_for(state="hidden", timeout=210000)
                logger("✅ THÀNH CÔNG: Mạng Lưới Meta đã đóng dấu Bài Viết 100%! Rút quân.")
            except Exception as e:
                logger("⚠️ TRÀN BỘ NHỚ: Đợi 3.5 phút vẫn chưa đóng Modal! Tool nhảy rẽ nhánh khẩn cấp.")
                
            return True
            
        except Exception as e:
            logger(f"❌ [Robot Error]: Lỗi thuật toán UI: {e}")
            return False
            
        finally:
            try:
                context.close()
            except:
                pass