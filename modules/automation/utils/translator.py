from deep_translator import GoogleTranslator
from config.config import TRANSLATE_TARGET
import time

# Khởi tạo cỗ máy dịch thuật
# source='auto' đôi khi gây lỗi, ta nên handle kỹ
translator = GoogleTranslator(source='auto', target=TRANSLATE_TARGET)

translation_cache = {}

def translate_text(text):
    """
    Phiên bản an toàn: Không bao giờ trả về None.
    Nếu lỗi -> Trả về text gốc.
    """
    # 1. Kiểm tra đầu vào
    if text is None:
        return ""
    
    # Chuyển về dạng chuỗi và cắt khoảng trắng thừa
    text = str(text).strip()
    
    # Nếu chuỗi rỗng hoặc quá ngắn (VD: chỉ là dấu chấm, dấu phẩy), bỏ qua không dịch
    if len(text) < 2:
        return text
        
    # 2. Kiểm tra Cache (Nếu dịch rồi thì lấy luôn cho nhanh)
    if text in translation_cache:
        return translation_cache[text]
        
    # 3. Thử dịch
    try:
        # Gọi Google API
        translated = translator.translate(text)
        
        # QUAN TRỌNG: Kiểm tra xem Google có trả về None không
        if translated is None:
            return text # Dịch lỗi thì dùng tạm text gốc
            
        # Lưu vào cache
        translation_cache[text] = translated
        return translated

    except Exception as e:
        # Nếu mất mạng hoặc lỗi API, in ra lỗi nhẹ nhàng và trả về text gốc
        # print(f"⚠️ Warning dịch thuật: {e}") 
        return text