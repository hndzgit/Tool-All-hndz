import time
import google.generativeai as genai
from automation.config import config as cfg

def get_caption_from_video(video_path, logger=print):
    # Lấy API Key từ Config chung (của Tool Automation)
    api_key = getattr(cfg, "GEMINI_API_KEY", "")
    if not api_key:
        logger("❌ [Gemini AI] Thiếu API KEY! Vui lòng vào Cài Đặt Chung của Tool cấu hình KEY Gemini trước.")
        return "", "", ""
        
    genai.configure(api_key=api_key)
    
    prompt = (
        "Bạn là một chuyên gia marketing Affiliate và chém gió MXH siêu đỉnh (Sống tại Việt Nam). "
        "Hãy xem kỹ toàn bộ video clip này. Dựa vào nội dung/âm thanh của nó, "
        "hãy viết 1 đoạn Caption/STT ngắn thu hút để đăng bài (Khoảng 2-4 câu). "
        "Cố gắng giật tít, tò mò, thả thính hoặc tạo sự chú ý. "
        "Thêm 2 - 3 hashtag trend mạng xã hội ở cuối. "
        "Nghiêm cấm viết chữ in đậm hoặc chèn emoji kì cục. Chỉ xuất ra nội dung text để đăng. Không lải nhải giải thích."
        "\nTUYỆT ĐỐI NGHIÊM CẤM nhắc đến giá tiền, số tiền cụ thể hoặc mệnh giá tiền tệ (VND, $, cành, k, đồng, tệ,...) để tránh bị đánh vi phạm chính sách."
        "\n\n[LỆNH ĐẶC BIỆT BẮT BUỘC]: BẠN PHẢI NÊU RÕ TÊN MÓN HÀNG/SẢN PHẨM TRONG VIDEO SAU CÙNG CỦA ĐOẠN CAPTION BẰNG THẺ XML SAU: <PRODUCT>Tên Ngắn Gọn Tiếng Việt</PRODUCT>."
    )

    try:
        logger(f"🧠 [Gemini AI] Đang đẩy Video lên não bộ Google (Xin chờ xíu, tốc độ tùy mạng)...")
        # Upload using the new GenAI Files API
        video_file = genai.upload_file(path=video_path)
        logger(f"  -> Uploaded as: {video_file.uri}. Đang xử lý Video phân giải cao...")
        
        # Chờ video được xử lý thành trạng thái ACTIVE
        while video_file.state.name == "PROCESSING":
            logger("  -> AI Đang coi Video... (Tốn tầm 10s-30s).")
            time.sleep(5)
            # Fetch latest state
            video_file = genai.get_file(video_file.name)
            
        if video_file.state.name == "FAILED":
            logger("❌ [Gemini AI] Đọc video bị lỗi từ máy chủ. Bỏ qua STT!")
            return ""
            
        logger("✅ [Gemini AI] Xác nhận đã thấu hiểu Video. Chuẩn bị viết Caption...")
        
        # Mẫu đời mới nhất theo lệnh Sếp nổ: gemini-3.1-flash-lite-preview
        # Sẽ fallback sang "gemini-3.1-flash-lite-preview" nếu API cũ.
        model_name = getattr(cfg, "AI_MODEL_NAME", "gemini-3.1-flash-lite-preview") # Fallback Default
        if "3.1" in model_name or hasattr(cfg, "AI_MODEL_NAME") == False:
             model_name = "gemini-3.1-flash-lite-preview"
             
        logger(f"  -> Model Sử dụng: {model_name}")
        model = genai.GenerativeModel(model_name=model_name)
        
        response = model.generate_content([video_file, prompt])
        raw_text = response.text.strip()
        
        caption = raw_text
        product_name = "Chưa xá định được"
        import re
        
        # Bóc Tên Món Hàng Nguyên Bản Ra Khỏi Status
        match_prod = re.search(r"<PRODUCT>(.*?)</PRODUCT>", raw_text, re.IGNORECASE)
        if match_prod:
            product_name = match_prod.group(1).strip()
            caption = caption.replace(match_prod.group(0), "").strip()

        logger(f"🔥 [Gemini AI STT XONG]:\n{caption}\n")
        
        genai.delete_file(video_file.name)
        return caption, "", product_name
        
    except Exception as e:
        logger(f"❌ [Gemini AI Error] Lỗi Hệ Toán Não: {str(e)}")
        try:
            if 'video_file' in locals():
                genai.delete_file(video_file.name)
        except:
            pass
        return "", "", ""

def scan_product_name_from_video(video_path, logger=print):
    """Hàm chỉ quét Video để nặn ra Tên Món Hàng in lên Log, không sinh file rác"""
    api_key = getattr(cfg, "GEMINI_API_KEY", "")
    if not api_key:
        logger("❌ [Gemini AI] Thiếu API KEY! Không thể quét sản phẩm.")
        return ""
        
    genai.configure(api_key=api_key)
    
    prompt = (
        "Nhiệm vụ của bạn là xem Video này và Cho Tôi Biết món đồ vật/Sản phẩm chính "
        "đang được quảng cáo hoặc sử dụng trong Video là Món Gì? (Nhớ dùng Tiếng Việt). "
        "Chỉ Nêu ĐÚNG cái tên cụ thể của Sản phẩm, CÀNG NGẮN GỌN CÀNG TỐT (Từ 3 đến 8 chữ). "
        "Ví dụ: Máy sấy tóc, Bình giữ nhiệt, Chổi lau nhà, Bàn chải điện. "
        "TUYỆT ĐỐI KHÔNG DÀI DÒNG. Cấu trúc TRẢ VỀ DUY NHẤT: <PRODUCT>Tên Món Hàng</PRODUCT>"
    )
    
    try:
        video_file = genai.upload_file(path=video_path)
        while video_file.state.name == "PROCESSING":
            time.sleep(3)
            video_file = genai.get_file(video_file.name)
            
        if video_file.state.name == "FAILED": return "Không Rõ Lỗi Tải"
        
        model_name = getattr(cfg, "AI_MODEL_NAME", "gemini-2.5-flash")
        if "3.1" in model_name or hasattr(cfg, "AI_MODEL_NAME") == False:
             model_name = "gemini-3-flash-preview"
             
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content([video_file, prompt])
        raw_text = response.text.strip()
        
        genai.delete_file(video_file.name)
        
        # Bóc thẻ sạch tưng
        import re
        match = re.search(r"<PRODUCT>(.*?)</PRODUCT>", raw_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return raw_text.replace("<PRODUCT>", "").replace("</PRODUCT>", "").strip()
        
    except Exception as e:
        try:
            if 'video_file' in locals(): genai.delete_file(video_file.name)
        except: pass
        return "Không Nhận Diện Được"