import time
import os
import google.generativeai as genai
from config.config import GEMINI_API_KEY
import config.config as cfg
import threading
import random

# Khóa luân phiên Mắt Thần AI (Chống kẹt xe Google Server khi nhiều Video đồng loạt Load)
gemini_vision_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH NGẪU NHIÊN HÓA KỊCH BẢN (SCRIPT RANDOMIZATION ENGINE)
# ══════════════════════════════════════════════════════════════

REVIEW_STYLES = [
    "Bắt trend, giật gân, khơi gợi tò mò mạnh ở giây đầu tiên. Đi thẳng vào sự tò mò, tránh các câu chào sáo rỗng.",
    "Hài hước, dí dỏm, lầy lội, trêu đùa, sử dụng các phép so sánh độc lạ và vui nhộn.",
    "Đánh giá chân thực, thẳng thắn, tập trung trực diện vào ưu điểm nổi bật và lợi ích thực tế lớn nhất.",
    "Kể chuyện tâm sự (storytelling), chia sẻ trải nghiệm cá nhân tự nhiên, đời thường như đang nói chuyện với tri kỷ.",
    "Ngắn gọn, súc tích, nhịp điệu nhanh, dứt khoát, tập trung kích thích người nghe chốt đơn ngay lập tức.",
    "Tạo tình huống kịch tính, bất ngờ, đặt câu hỏi tranh cãi hoặc giả định hài hước ở đầu video."
]

PERSONAS = [
    "Chiến thần review TikTok thực chiến: giọng điệu vô cùng tự tin, cuốn hút, đi thẳng vào trải nghiệm đập hộp và sử dụng thực tế, không ngại khen chê thẳng thắn để tạo uy tín.",
    "Reviewer kiểm chứng quảng cáo (kiểu Kiên Review): giọng điệu điềm tĩnh nhưng sắc sảo, chuyên mua các món đồ hot trên mạng về test xem có đúng như quảng cáo không, tạo niềm tin tuyệt đối.",
    "Bá chủ unboxing/săn deal GenZ: giọng điệu trẻ trung, cực kỳ năng động, hài hước, sử dụng từ lóng tự nhiên, tạo cảm giác thân thiết như bạn bè khuyên nhủ nhau.",
    "Chuyên gia bóc tách công nghệ/tiện ích thông minh: tập trung nói về các mẹo sử dụng ẩn, tính năng đột phá của sản phẩm mà ít người biết, nói năng lưu loát, dứt khoát.",
    "Khách hàng khó tính trải nghiệm thực tế: bắt đầu bằng thái độ hơi nghi ngờ quảng cáo trên mạng, nhưng sau khi tự tay dùng thử thì bị thuyết phục hoàn toàn bởi hiệu quả thực tế."
]

HOOKS = [
    "Đặt một câu hỏi ngược cực kỳ sốc/gây tranh cãi đánh thẳng vào nỗi đau hoặc mong muốn thầm kín của người xem (Ví dụ: 'Đã tốn bao nhiêu tiền ngu cho cái này rồi?', 'Đừng bao giờ mua món này nếu không muốn hối hận...').",
    "Phát ngôn gây chấn động mạnh ngay từ 1.5 giây đầu tiên (Ví dụ: 'Chấn động thực sự!', 'U là trời, cái gì thế này?', 'Đừng lướt qua nếu bạn không muốn bỏ lỡ deal hời nhất...').",
    "So sánh độc lạ, khập khiễng, thu hút trí tò mò tuyệt đối (Ví dụ: 'Trông như đồ chơi con nít nhưng công dụng thì ngang ngửa máy tiền triệu!', 'Đừng mua món này nếu nhà bạn quá chật...').",
    "Lời cảnh báo/lời khuyên khơi gợi tò mò cực cao (Ví dụ: 'Nói thật, món này không dành cho người lười!', 'Đây là lý do tại sao người giàu giấu nhẹm món này...')."
]

TRENDY_SLANGS = [
    "đỉnh chóp", "keo lỳ", "mướt mườn mượt", "chấn động", "sướng cái nách", "cứu cả cụ cuộc đời", "ét ô ét",
    "10 điểm không có nhưng", "hết nước chấm", "quá là sướng", "bất ngờ chưa bà già", "đẹp xỉu up xỉu down",
    "chất phát ngất", "uy tín luôn", "xịn sò", "đỉnh của chóp", "khét lẹt"
]

CLICHES_TO_AVOID = [
    "Hôm nay mình sẽ review", "Chào các bạn", "Xin chào mọi người", "Siêu phẩm", "Món này", "Đây là",
    "Chào mừng các bạn", "Hôm nay", "Mình xin giới thiệu", "Các bạn ơi", "Cực kỳ", "Rất là", "Xin chào cả nhà",
    "Hôm nay mình sẽ", "Mình xin phép"
]

ANGLES = [
    "Bóc phốt ngược: Tỏ ra nghi ngờ chất lượng lúc đầu, định chê bai sản phẩm nhưng sau đó bị bất ngờ hoàn toàn vì dùng quá sướng và quay sang khen hết lời.",
    "Giải cứu nỗi đau: Nêu bật một vấn đề cực kỳ phiền toái, đau đầu mà người xem đang gặp phải hàng ngày, sau đó giới thiệu món đồ này như một vị cứu tinh giải quyết triệt để vấn đề.",
    "Tâm sự trải nghiệm cá nhân: Chia sẻ chân thành câu chuyện dở khóc dở cười của bản thân hoặc người thân khi chưa biết đến món đồ này, tạo sự đồng cảm sâu sắc.",
    "Thợ săn deal/Góc nhìn thực tế: Chia sẻ mẹo tối ưu, các tính năng ẩn thú vị của sản phẩm mà ít người biết, nhấn mạnh sự tiện dụng và hời như thế nào.",
    "Kịch tính giật gân: Bắt đầu bằng một lời cảnh báo gây sốc (Ví dụ: 'Đừng dại gì mua...', 'Sự thật tàn nhẫn về...') để thu hút người xem rồi giải thích lý do thực sự đằng sau.",
    "So sánh hài hước: So sánh công dụng của sản phẩm với những tình huống lầy lội, hài hước trong cuộc sống hàng ngày."
]

def build_randomized_prompt(script_duration, extra_instruction="", is_image=False):
    style = random.choice(REVIEW_STYLES)
    persona = random.choice(PERSONAS)
    hook = random.choice(HOOKS)
    angle = random.choice(ANGLES)
    
    # Pick 3 random slang words
    slangs = random.sample(TRENDY_SLANGS, 3)
    slang_str = ", ".join([f"'{s}'" for s in slangs])
    
    # Format clichés to avoid backslash inside f-string curly braces
    cliches_str = ", ".join([f'"{c}"' for c in CLICHES_TO_AVOID])
    
    source_type = "bức ảnh đơn hàng / hóa đơn / sản phẩm" if is_image else "đoạn Video không lời/không phụ đề"
    role_description = (
        "Đọc thông tin sản phẩm/đơn hàng từ bức ảnh này, nhưng TUYỆT ĐỐI không đọc liệt kê khô khan như robot. Hãy đóng vai một TikTok Reviewer đang hào hứng 'đập hộp/khoe' đơn hàng này cho người xem. Hãy tự sáng tạo một kịch bản review sản phẩm tự nhiên, cuốn hút dựa trên các từ khóa đọc được từ ảnh đó." 
        if is_image else 
        "Khám phá nội dung video. Đóng vai một TikTok Reviewer đang thuyết minh, lồng tiếng cho sản phẩm/nội dung xuất hiện trong video theo cách chân thực và lôi cuốn nhất."
    )
    
    prompt = (
        f"Bạn là một biên kịch TikTok/Shorts/Reels bậc thầy, chuyên sáng tạo những kịch bản giữ chân người xem cực tốt (High Retention) có tỷ lệ xem hết trên 80%.\n"
        f"Hãy xem xét kỹ {source_type} này. {role_description}\n\n"
        f"🔥 QUY TẮC VÀNG ĐỂ CHỐNG NGƯỜI DÙNG LƯỚT VIDEO (MANDATORY RETENTION RULES):\n"
        f"1. [CHỐNG SKIP GIÂY ĐẦU]: Người nghe sẽ lướt đi trong 2 giây đầu nếu câu mở đầu nhàm chán. Do đó, câu đầu tiên BẮT BUỘC phải đi thẳng vào hook chống lướt sau:\n"
        f"   -> HOOK: {hook}\n"
        f"   Nghiêm cấm tuyệt đối các câu chào hỏi, tự giới thiệu bản thân hoặc giới thiệu sản phẩm kiểu mòn cũ.\n"
        f"2. [NHỊP ĐIỆU DỒN DẬP - PUNCHY]: Mỗi câu phụ đề cực kỳ ngắn gọn (TỪ 3 ĐẾN 6 TỪ). Nhịp điệu kịch bản phải dồn dập, gãy gọn, kích thích người nghe cuốn theo. Cấm viết các câu dài lê thê làm giảm sự tập trung.\n"
        f"3. [CỐT TRUYỆN / GÓC TIẾP CẬN KỊCH TÍNH]: {angle}\n"
        f"4. [VAI DIỄN & TÔNG GIỌNG]: Hóa thân cực sâu vào nhân vật: {persona} (Phong cách biểu đạt: {style}).\n"
        f"5. [TỪ LÓNG & TỪ ĐỜI THƯỜNG]: Sử dụng các từ ngữ nói chuyện đời thường tự nhiên, lồng ghép khéo léo các từ lóng: {slang_str}.\n"
        f"6. [ĐỘ DÀI PHÙ HỢP]: Tổng thời lượng kịch bản lồng tiếng phải nằm gọn từ 00:00:00,000 đến tối đa {script_duration:.1f} giây (tức là chỉ bằng 83% chiều dài video, chừa lại 3-4 giây cuối làm outro không đọc để video có khoảng nghỉ tự nhiên).\n\n"
        f"🔥 PHONG CÁCH REVIEW TIKTOK THỰC CHIẾN:\n"
        f"- Không liệt kê thông số khô khan như máy móc. Hãy dùng từ ngữ đời thường, gần gũi, biểu cảm mạnh, có khen chê chân thực.\n"
        f"- Xưng hô thân mật tự nhiên như đang nói chuyện trực tiếp với người xem: 'mình', 'cả nhà', 'anh em', 'mấy bà', 'mấy ông'.\n"
        f"- Thay vì nói 'Sản phẩm này có kích thước...', hãy nói 'Cầm cái này trên tay siêu nhỏ gọn luôn...', 'Dùng thử mà sướng cái nách...'.\n\n"
        f"{extra_instruction}\n\n"
        f"CÁC LUẬT BẮT BUỘC:\n"
        f"1. Chỉ xuất ra CHUẨN ĐỊNH DẠNG FILE `.SRT`. Không nói thêm bất kỳ từ ngữ dư thừa nào khác ngoài cấu trúc file SRT. "
        f"Cấu trúc SRT ví dụ:\n"
        f"   1\n"
        f"   00:00:00,000 --> 00:00:02,000\n"
        f"   [Nội dung câu 1]\n\n"
        f"   2\n"
        f"   00:00:02,300 --> 00:00:05,000\n"
        f"   [Nội dung câu 2]\n\n"
        f"2. TUYỆT ĐỐI KHÔNG ĐƯỢC nhắc đến bất kỳ giá cả, số tiền, giá bán, hay mệnh giá tiền tệ nào (cấm các từ như VND, đồng, k, cành, tệ, $, tiền,...). Không được giá tiền xuất hiện trên phụ đề/giọng đọc. Hãy dùng các từ nói giảm nói tránh như 'giá hạt dẻ', 'phù hợp túi tiền', 'tiết kiệm', 'siêu hời',... để tránh bị TikTok quét bóp tương tác hoặc vi phạm chính sách.\n"
        f"3. Không in đậm, không dùng emoji, thuần Text Tiếng Việt.\n"
        f"4. ĐỪNG giải thích gì cả. CHỈ ĐƯA RA NỘI DUNG CODE FILE SRT!\n"
        f"5. NGHIÊM CẤM sử dụng lại các cụm từ mở đầu sáo rỗng sau: {cliches_str}. Hãy bắt đầu bằng một hook bất ngờ hoặc đi thẳng luôn vào vấn đề chính.\n"
        f"6. Kịch bản của mỗi video phải khác biệt hoàn toàn về cấu trúc câu, từ ngữ, không dùng chung các lối nói mòn cũ."
    )
    return prompt

def get_valid_gemini_keys():
    live_cfg = cfg.load_settings()
    keys = [
        live_cfg.get("gemini_api_key", "").strip(),
        live_cfg.get("gemini_api_key_2", "").strip(),
        live_cfg.get("gemini_api_key_3", "").strip(),
        live_cfg.get("gemini_api_key_4", "").strip(),
        live_cfg.get("gemini_api_key_5", "").strip(),
    ]
    return [k for k in keys if k and len(k) > 10]

def generate_ai_srt_from_video(video_path, output_srt, max_retries=3, video_duration=None):
    keys = get_valid_gemini_keys()
    if not keys:
        raise ValueError("Chưa thiết lập Google Gemini API Key. Vui lòng vào 'Cài Đặt API' để nhập.")
        
    print(f"👁️ [Mắt Thần AI] Đang đẩy Video gốc lên Trung tâm thần kinh Google (Xin chờ xíu)...")
    
    try:
        # Lấy thời lượng video để tính toán giới hạn kịch bản nếu chưa có
        if video_duration is None:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 100
            video_duration = total_frames / fps
            cap.release()
        
        script_duration = video_duration * 0.83

        with gemini_vision_lock:
            current_key = keys[0]
            genai.configure(api_key=current_key)
            
            video_file = genai.upload_file(path=video_path)
            print(f"  -> Uplink thành công: {video_file.uri}. Đang xử lý AI...")
            
            while video_file.state.name == "PROCESSING":
                time.sleep(5)
                video_file = genai.get_file(video_file.name)
                
            if video_file.state.name == "FAILED":
                print("❌ [Mắt Thần AI] Phân tích video thất bại từ phía Máy Chủ Google.")
                return ""
                
            print("✅ [Mắt Thần AI] Mắt Thần đã phân rã toàn bộ Video. Tiến hành viết kịch bản Lồng tiếng SRT...")
            
            model_name = getattr(cfg, "AI_MODEL_NAME", "gemini-3.1-flash-lite-preview")
            if "3.1" in model_name or not hasattr(cfg, "AI_MODEL_NAME"):
                 model_name = "gemini-3.1-flash-lite-preview"
                 
            model = genai.GenerativeModel(model_name=model_name)
        
        prod_name = getattr(cfg, "SPECIFIED_PRODUCT_NAME", "").strip()
        extra_instruction = ""
        if prod_name:
            extra_instruction = f"\nCHÚ Ý: Sản phẩm chính xuất hiện trong video được xác định cụ thể là: '{prod_name}'. Bạn BẮT BUỘC phải viết kịch bản review xoay quanh đúng sản phẩm '{prod_name}' này, sử dụng chính xác tên thương hiệu/sản phẩm này trong kịch bản."

        prompt = build_randomized_prompt(script_duration, extra_instruction, is_image=False)
        print(f"🎲 [Mắt Thần AI] Đã xây dựng Prompt ngẫu nhiên độc quyền.")

        response = model.generate_content([prompt, video_file], request_options={"timeout": 120})
        
        raw_text = response.text.strip()
        if raw_text.startswith("```srt"):
            raw_text = raw_text[6:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        srt_content = raw_text.strip()
        
        if srt_content:
            with open(output_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)
            print(f"🎉 [Mắt Thần AI] Đã tự sáng tác Kịch bản Tiếng Việt Độc Quyền! Lưu tại: {output_srt}")
            
            # Lưu log Ảnh Bìa Title để tương thích Pipeline cũ
            title_log_path = output_srt + ".title.txt"
            with open(title_log_path, "w", encoding="utf-8") as f:
                f.write("SIÊU PHẨM BÍ ẨN") # Title Default
                
            return output_srt
        else:
            print("⚠️ [Mắt Thần AI] Gemini không nhả ra script nào.")
            return ""
            
    except Exception as e:
        print(f"⚠️ [Mắt Thần AI] Đặc Vụ Lỗi Khi Scan Kịch Bản: {e}")
        return ""

def generate_ai_srt_from_image(image_path, video_duration, output_srt, max_retries=3):
    keys = get_valid_gemini_keys()
    if not keys:
        raise ValueError("Chưa thiết lập Google Gemini API Key. Vui lòng vào 'Cài Đặt API' để nhập.")
        
    if not image_path or not os.path.exists(image_path):
        raise ValueError("Chưa chọn ảnh sản phẩm/đơn hàng hợp lệ hoặc file ảnh không tồn tại.")

    # Giới hạn thời lượng đọc kịch bản bằng 83% tổng video để có khoảng trống outro
    script_duration = video_duration * 0.83
        
    print(f"📸 [Gemini Image] Đang phân tích ảnh: {os.path.basename(image_path)}...")
    
    try:
        from PIL import Image
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        img = Image.open(image_path)
        
        with gemini_vision_lock:
            current_key = keys[0]
            genai.configure(api_key=current_key)
            
            model_name = getattr(cfg, "AI_MODEL_NAME", "gemini-3.1-flash-lite-preview")
            if "3.1" in model_name or not hasattr(cfg, "AI_MODEL_NAME"):
                 model_name = "gemini-3.1-flash-lite-preview"
                 
            model = genai.GenerativeModel(model_name=model_name)
            
        prod_name = getattr(cfg, "SPECIFIED_PRODUCT_NAME", "").strip()
        extra_instruction = ""
        if prod_name:
            extra_instruction = f"\nCHÚ Ý: Sản phẩm chính xuất hiện trong ảnh được xác định cụ thể là: '{prod_name}'. Bạn BẮT BUỘC phải viết kịch bản review xoay quanh đúng sản phẩm '{prod_name}' này, sử dụng chính xác tên thương hiệu/sản phẩm này trong kịch bản."

        prompt = build_randomized_prompt(script_duration, extra_instruction, is_image=True)
        print(f"🎲 [Gemini Image] Đã xây dựng Prompt ngẫu nhiên từ ảnh.")

        response = model.generate_content([prompt, img], request_options={"timeout": 90})
        
        raw_text = response.text.strip()
        if raw_text.startswith("```srt"):
            raw_text = raw_text[6:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        srt_content = raw_text.strip()
        
        if srt_content:
            with open(output_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)
            print(f"🎉 [Gemini Image] Đã tạo kịch bản từ ảnh thành công! Lưu tại: {output_srt}")
            return output_srt
        else:
            print("⚠️ [Gemini Image] Gemini không nhả ra script nào.")
            return ""
            
    except Exception as e:
        print(f"⚠️ [Gemini Image] Lỗi khi tạo kịch bản từ ảnh: {e}")
        return ""
