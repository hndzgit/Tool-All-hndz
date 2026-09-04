import http.server
import socketserver
import threading
import os

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

class LocalFileServer:
    def __init__(self, directory, port=8000):
        self.directory = directory
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        if self.httpd is not None:
            return # Already running
            
        os.chdir(self.directory)
        handler = CORSRequestHandler
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        print(f"🌐 [Web Server] Started at port {self.port} serving {self.directory}")

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            if self.thread:
                self.thread.join()
            print("🛑 [Web Server] Stopped.")

# Singleton instance
_server_instance = None

def start_server(directory, port=8000):
    global _server_instance
    if _server_instance:
        _server_instance.stop()
    _server_instance = LocalFileServer(directory, port)
    _server_instance.start()

def stop_server():
    global _server_instance
    if _server_instance:
        _server_instance.stop()
        _server_instance = None