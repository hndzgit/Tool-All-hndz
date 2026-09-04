from pyngrok import ngrok
import time

_current_tunnel = None

def start_tunnel(port=8000):
    global _current_tunnel
    if _current_tunnel:
        return _current_tunnel.public_url

    try:
        _current_tunnel = ngrok.connect(port)
        public_url = _current_tunnel.public_url
        print(f"🔗 [Ngrok Tunnel] Connected: {public_url} -> localhost:{port}")
        return public_url
    except Exception as e:
        print(f"❌ [Ngrok Tunnel] Error: {e}")
        return None

def stop_tunnel():
    global _current_tunnel
    if _current_tunnel:
        ngrok.disconnect(_current_tunnel.public_url)
        _current_tunnel = None
        print("🔗 [Ngrok Tunnel] Disconnected.")

def get_public_url(filename):
    """Lấy trực tiếp link download Public cho File trên Local Server"""
    global _current_tunnel
    if not _current_tunnel:
        start_tunnel()
    
    if _current_tunnel:
        return f"{_current_tunnel.public_url}/{filename}"
    return None