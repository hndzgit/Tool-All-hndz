import google.generativeai as genai
from config.config import GEMINI_API_KEY
import os
import threading
import random

# Ổ khóa luân phiên Google Gemini (Chống lỗi 429 Too Many Requests khi chạy Đa Luồng)
gemini_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH NGẪU NHIÊN DIỄN ĐẠT DỊCH PHÓNG TÁC (TRANSLATION LOCALIZATION POOL)
# ══════════════════════════════════════════════════════════════

TRANSLATION_STYLES = [
    "Dịch phóng tác, tự nhiên, sử dụng từ lóng trẻ trung (như: đỉnh chóp, xịn sò, uy tín luôn, hết nước chấm, sướng cái nách, bất ngờ chưa...).",
    "Dịch chân thực, mộc mạc, ngắn gọn, tập trung thẳng vào tác dụng chính và ưu điểm vượt trội của sản phẩm.",
    "Dịch hài hước, dí dỏm, pha chút lầy lội vui tươi để tạo tiếng cười cho người xem.",
    "Dịch chuyên nghiệp, dứt khoát, khoa học, phân tích ưu nhược điểm logic rõ ràng.",
    "Dịch kịch tính, giật gân, tạo cảm giác tò mò cao độ qua từng câu thoại lôi cuốn."
]

def check_gemini_key():
    import config.config as cfg
    live_cfg = cfg.load_settings()
    
    keys = [
        live_cfg.get("gemini_api_key", "").strip(),
        live_cfg.get("gemini_api_key_2", "").strip(),
        live_cfg.get("gemini_api_key_3", "").strip(),
        live_cfg.get("gemini_api_key_4", "").strip(),
        live_cfg.get("gemini_api_key_5", "").strip(),
    ]
    
    valid_keys = [k for k in keys if k and len(k) > 10]
    
    if not valid_keys:
        raise ValueError("Chưa thiết lập Google Gemini API Key. Vui lòng vào 'Cài Đặt API' để nhập.")
        
    return valid_keys

import re
import json

def translate_srt_with_gemini(srt_path, output_path):
    """
    Sử dụng Gemini để dịch toàn bộ file SRT sang ngôn ngữ đích thông qua hệ thống Array Proxy (JSON).
    Không cho phép AI nhìn thấy Timecode để tránh lỗi chèn Timecode vào Text.
    """
    valid_keys = check_gemini_key()
    
    import config.config as cfg
    target_language = getattr(cfg, "TARGET_LANGUAGE", "Tiếng Việt")
    src_lang = getattr(cfg, "SOURCE_LANGUAGE", "Tự Động (AI)")
    src_instruction = f" từ {src_lang}" if src_lang != "Tự Động (AI)" else ""
    
    if target_language == "Không Dịch (Giữ Nguyên Bản)":
        target_language = "giữ NGỮ NGHĨA GỐC, sửa các lỗi chính tả, KHÔNG DỊCH sang ngôn ngữ khác"
    
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"Không tìm thấy file SRT: {srt_path}")

    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    # 1. PARSE SRT gốc thành cấu trúc
    pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n*$)', re.DOTALL)
    matches = pattern.findall(srt_content)
    
    if not matches:
        print("⚠️ File SRT trống hoặc định dạng lỗi.")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        return output_path

    # 2. XÂY DỰNG JSON PROXY: Chỉ gửi Text
    blocks = []
    proxy_payload = []
    
    for idx, (stt, timecode, text) in enumerate(matches):
        clean_text = text.strip().replace('\n', ' ')
        blocks.append({
            "stt": stt,
            "timecode": timecode,
            "original_text": clean_text,
            "translated_text": clean_text
        })
        proxy_payload.append({
            "id": stt,
            "text": clean_text
        })
    
    prod_name = getattr(cfg, "SPECIFIED_PRODUCT_NAME", "").strip()
    extra_instruction = ""
    if prod_name:
        extra_instruction = f"\n    8. [ĐỊNH HƯỚNG TÊN SẢN PHẨM CHỈ ĐỊNH]: Sản phẩm trong video được xác định cụ thể là: '{prod_name}'. Bạn hãy chủ động sửa tất cả các từ khóa tên sản phẩm dịch hoặc từ viết sai chính tả sang đúng tên sản phẩm '{prod_name}' này để kịch bản đồng bộ và chuẩn xác."

    import random
    selected_tr_style = random.choice(TRANSLATION_STYLES)
    print(f"🎲 [Gemini Translator] Đã chọn ngẫu nhiên phong cách dịch thuật: {selected_tr_style}")

    prompt = f"""
    Dưới đây là một mảng JSON chứa các câu phụ đề gốc của một video.
    Bạn là một biên kịch TikTok tối ưu hóa tỷ lệ giữ chân người xem bậc thầy (High Retention Scriptwriter). Nhiệm vụ của bạn là:
    
    1. [Bộ Lọc Rác/Âm Nhạc]: Hãy tự động phân tích ngữ nghĩa. Nếu toàn bộ nội dung chỉ là Lời Bài Hát (Âm nhạc thuần túy không có lời thoại nói chuyện), những tiếng kêu vô nghĩa (a a a, ồ ồ), hoặc rác hoàn toàn vô nghĩa, hãy đặt `is_valid_review` thành `false` và trả về mảng `subtitles` rỗng `[]`. Còn nếu là vlogs, tin tức, chia sẻ cuộc sống, review, trò chuyện,... thì vẫn coi là hợp lệ (`is_valid_review` là `true`).
    2. Dịch thuật & Cải tiến kịch bản chống lướt (nếu `is_valid_review`: `true`): 
       - Dịch mảng `subtitles`{src_instruction} sang {target_language}.
       - [PHONG CÁCH BIỂU ĐẠT BẮT BUỘC]: {selected_tr_style}
       - 🔥 [BẮT BUỘC - CHỐNG SKIP GIÂY ĐẦU]: Hãy chỉnh sửa hoặc viết lại câu đầu tiên (id: 1 hoặc câu đầu tiên có nội dung) để biến nó thành một HOOK chống lướt cực mạnh (Ví dụ: đặt câu hỏi tranh cãi, phát ngôn bất ngờ, cảnh báo sốc về sản phẩm), cấm tuyệt đối các câu chào hỏi kiểu 'chào mọi người', 'review', 'hôm nay mình sẽ'.
       - 🔥 [NHỊP ĐIỆU CỰC CƠN LỐC]: Tuyệt đối không dịch dài dòng máy móc. Hãy cắt ngắn, tinh giản và viết lại câu chữ bằng tiếng Việt ngắn gọn, từ 3 đến 6 từ mỗi câu. Nhịp điệu kịch bản phải dồn dập, gãy gọn, có tính động từ mạnh để kích thích người nghe cuốn theo từ đầu đến cuối mà không muốn lướt đi.
       - Nếu ngôn ngữ đích là Không Dịch, vẫn phải áp dụng luật cắt ngắn câu và sửa lỗi chính tả để tối ưu giữ chân người xem.
    3. CẮT NGẮN CÂU DÀI: Tự động xuống dòng (\\n) nếu câu quá dài, để phụ đề không tràn màn hình.
    4. [BẢO VỆ THƯƠNG HIỆU]: Giữ nguyên/phiên âm đúng tên hãng, mã model (VD: Attack Shark, iPhone). KHÔNG DỊCH tên hãng sang ngôn ngữ khác.
    5. [TẠO ẢNH BÌA CLICKBAIT]: Dựa trên toàn bộ nội dung video này, sáng tác 1 câu Tiêu Đề cực Giật gân/Tò mò ({target_language}) để làm Text Ảnh Bìa. TỐI ĐA 4-5 TỪ MÀ THÔI! Đặt vào trường `thumbnail_title`. (VD: "SECRET REVEALED", "DONT BUY THIS").
    6. [LUẬT AN TOÀN TIKTOK SHOP - TUYỆT ĐỐI CẤM NHẮC GIÁ CẢ]: Để tuân thủ chính sách mới của TikTok, bạn TUYỆT ĐỐI KHÔNG được đưa bất kỳ thông tin nào liên quan đến giá tiền, giá bán, số tiền cụ thể hoặc mệnh giá tiền tệ (kể cả Nhân dân tệ ¥/元, USD $, hay VND cành, k, nghìn, đồng, tiền...) vào phụ đề dịch. Không sử dụng các con số chỉ số tiền (ví dụ: cấm viết '99k', 'vài chục cành', 'chỉ 100k',...). Hãy loại bỏ hoặc tự động viết giảm viết tránh (ví dụ: thay vì dịch con số cụ thể, hãy dùng các từ như "giá hạt dẻ", "giá ưu đãi", "phù hợp túi tiền", "tiết kiệm", "giá cực tốt", "giá học sinh sinh viên",...). Tuyệt đối không bao giờ để giá tiền xuất hiện trên phụ đề/video để tránh bị đánh vi phạm chính sách. Điều này áp dụng ngay cả khi ngôn ngữ đích là Không Dịch.
    7. [SỬA LỖI CHÍNH TẢ & TỪ NGỮ SAI]: Hãy chủ động rà soát kỹ mảng subtitles đầu vào. Nếu phát hiện từ nào viết sai chính tả, sai nghĩa, từ bị nhận diện lỗi do OCR (nhầm chữ), hoặc câu văn diễn đạt lủng củng không logic, bạn hãy tự động sửa và tối ưu hóa lại câu phụ đề đó để bản dịch đầu ra hoàn hảo, chính xác và có nghĩa rõ ràng nhất.{extra_instruction}
    
    BẠN BẮT BUỘC PHẢI TRẢ VỀ CHÍNH XÁC ĐỊNG DẠNG JSON SAU (Không kèm markdown):
    {{
       "is_valid_review": boolean,
       "thumbnail_title": "TÍT GIẬT GÂN NGHĨA THEO TỪ NGỮ ĐÍCH",
       "subtitles": [
          {{ "id": "...", "text": "bản dịch tương ứng" }}
       ]
     }}
       
     Payload:
     {json.dumps(proxy_payload, ensure_ascii=False, indent=2)}
     """

    print("🤖 Đang gửi yêu cầu dịch thuật siêu việt và Lọc Rác (JSON Mode) đến Google Gemini...")
    max_retries = max(3, len(valid_keys) * 2) # Mỗi key thử 2 lần
    import time
    
    for attempt in range(max_retries):
        # Trích xuất Chìa Khoá xoay vòng tương ứng với lượt thử hiện tại
        current_key_idx = attempt % len(valid_keys)
        current_key = valid_keys[current_key_idx]
        
        if attempt > 0:
            print(f"🔄 Đang Thử Nạp Đạn Key API Số {current_key_idx + 1}... (Lần {attempt+1}/{max_retries})")
            
        try:
            with gemini_lock:
                genai.configure(api_key=current_key)
                # Khởi tạo model bằng key mới
                model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
                response = model.generate_content(prompt, request_options={"timeout": 120})
            
            # Xóa sạch các thẻ markdown rác từ LLM (như ```json và ```) để có JSON tinh khiết
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            result_obj = json.loads(raw_text.strip())
            
            # --- CƠ CHẾ CHỐNG RÁC, CHỐNG ÂM NHẠC ---
            if not result_obj.get("is_valid_review", True):
                print("🚫 Gemini phát hiện audio là BÀI HÁT / RÁC vô nghĩa. Hủy bộ phụ đề!")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("") # Trả về file RỖNG => Các bước sau (TTS, Vẽ Sub) sẽ TỰ ĐỘNG BỎ QUA!
                return output_path
                
            tr_array = result_obj.get("subtitles", [])
            tr_dict = {str(item["id"]): item["text"] for item in tr_array}
            
            # Ghi đè lại SRT với cấu trúc timecode nguyên phân của bản gốc
            final_srt_str = ""
            for blk in blocks:
                # Fallback nếu AI lỡ rớt ID (cực hiếm)
                trans_text = tr_dict.get(str(blk["stt"]), blk["original_text"]) 
                final_srt_str += f"{blk['stt']}\n{blk['timecode']}\n{trans_text}\n\n"
                
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_srt_str)
                
            # Trích xuất Title lưu thành file riêng (.title.txt) cho Khâu Overlay Ảnh Bìa
            thumbnail_title = result_obj.get("thumbnail_title", "SIÊU PHẨM MỚI")
            if not thumbnail_title or thumbnail_title.strip() == "":
                thumbnail_title = "SIÊU PHẨM MỚI"
            title_log_path = output_path + ".title.txt"
            with open(title_log_path, "w", encoding="utf-8") as f:
                f.write(thumbnail_title)
            
            print(f"✅ Đã dịch xong phụ đề lưu tại: {output_path} (Bằng Key API số {current_key_idx + 1})")
            print(f"🌟 Sáng tác Ảnh bìa Clickbait: '{thumbnail_title}'")
            return output_path
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Gemini Key Số {current_key_idx + 1} trả về JSON lỗi: {e}")
            if attempt < max_retries - 1:
                print("⏳ Đang đợi 3 giây để thử lại (Key này vẫn nguyên đạn)...")
                time.sleep(3)
            else:
                raise Exception(f"❌ Gemini thất bại sau {max_retries} lần thử do lỗi JSON: {e}")
                
        except Exception as e:
            err_str = str(e).lower()
            err_reason = f"Lỗi không xác định: {e}"
            if "429" in err_str or "quota" in err_str or "exhausted" in err_str:
                err_reason = "Đã Hết Tín Chỉ (Quota Exceeded/429 Too Many Requests)"
            elif "api_key_invalid" in err_str or "400" in err_str:
                err_reason = "Key Không Hợp Lệ hoặc Bị Khóa"
                
            print(f"⚠️ Thất bại tại Key API số {current_key_idx + 1} - Lý do: {err_reason}")
            
            if attempt < max_retries - 1:
                print("♻️ Tự Động Bỏ Qua Chìa Khóa Này... Chuyển Sang Nạp Chìa Khóa Tiếp Theo!")
                time.sleep(1.5)
            else:
                raise Exception(f"❌ Toàn bộ {len(valid_keys)} Chìa Khoá Gemini Trong Băng đều đã Thất Bại Đoạt Mạng: {e}")
                
    return output_path