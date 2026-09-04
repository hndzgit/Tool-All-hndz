import time
import requests

class ThreadsAPI:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.base_url = "https://graph.threads.net/v1.0"
        
    def _post(self, endpoint, data):
        url = f"{self.base_url}/{endpoint}"
        params = {"access_token": self.access_token}
        response = requests.post(url, params=params, data=data)
        
        try:
            return response.json()
        except Exception:
            return {"error": {"message": response.text}}

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        if params is None:
            params = {}
        params["access_token"] = self.access_token
        response = requests.get(url, params=params)
        
        try:
            return response.json()
        except:
            return {"error": {"message": response.text}}

    def upload_image_container(self, image_public_url, is_carousel_item=True):
        """Bước 1: Bắn hình ảnh lên Media Container (Hỗ trợ Carousel)"""
        data = {
            "media_type": "IMAGE",
            "image_url": image_public_url,
            "is_carousel_item": str(is_carousel_item).lower()
        }
        res = self._post(f"{self.user_id}/threads", data)
        return res.get("id")

    def upload_video_container(self, video_public_url, is_carousel_item=True):
        """Bước 2: Bắn Video lên Media Container (Hỗ trợ Carousel)"""
        data = {
            "media_type": "VIDEO",
            "video_url": video_public_url,
            "is_carousel_item": str(is_carousel_item).lower()
        }
        res = self._post(f"{self.user_id}/threads", data)
        return res.get("id")
        
    def check_status(self, container_id, max_retries=15):
        """Dò liên tục trạng thái Container Video. Phải FINISHED mới được Publish"""
        for i in range(max_retries):
            res = self._get(f"{container_id}", params={"fields": "status,error_message"})
            status = res.get("status")
            if status == "FINISHED":
                return True
            elif status == "ERROR":
                raise Exception(f"Lỗi Render Video trên máy chủ Meta: {res.get('error_message')}")
            
            # Đang IN_PROGRESS -> Chờ 5s rồi hỏi lại
            time.sleep(5)
        return False

    def create_carousel_container(self, children_ids, caption=""):
        """Bước 3: Ghép Image ID và Video ID vào chung 1 hộp Carousel"""
        data = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
        }
        if caption:
            data["text"] = caption
            
        res = self._post(f"{self.user_id}/threads", data)
        return res.get("id")

    def publish(self, creation_id):
        """Bước Cuối: Phát Hành (Publish) bài viết công khai"""
        data = {
            "creation_id": creation_id
        }
        res = self._post(f"{self.user_id}/threads_publish", data)
        return res.get("id")
        
    def check_token_info(self):
        """Kiểm tra token có đúng không bằng cách lấy Tên User / ID"""
        res = self._get("me", params={"fields": "id,username"})
        return res