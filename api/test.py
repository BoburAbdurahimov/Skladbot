from http.server import BaseHTTPRequestHandler
import sys
import traceback

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        
        try:
            import libsql_experimental
            self.wfile.write("libsql_experimental imported successfully!\n".encode())
            
            import os
            url = os.environ.get("TURSO_DATABASE_URL", "missing")
            token = os.environ.get("TURSO_AUTH_TOKEN", "missing")
            
            self.wfile.write(f"URL loaded: {'Yes' if url != 'missing' else 'No'}\n".encode())
            self.wfile.write(f"Token loaded: {'Yes' if token != 'missing' else 'No'}\n".encode())
            
            conn = libsql_experimental.connect("test.db", sync_url=url, auth_token=token)
            conn.sync()
            self.wfile.write("Connection synced!\n".encode())
            
        except Exception as e:
            self.wfile.write(f"Error: {e}\n\n".encode())
            self.wfile.write(traceback.format_exc().encode())
            
