import http.server
import urllib.request
import urllib.error
import socketserver
import sys

PORT = 8081
TARGET_HOST = 'localhost'
TARGET_PORT = 8080
NGROK_HOST = 'unrueful-alix-binomially.ngrok-free.dev'

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, hdrs):
        return fp
    def http_error_302(self, req, fp, code, msg, hdrs):
        return fp
    def http_error_303(self, req, fp, code, msg, hdrs):
        return fp
    def http_error_307(self, req, fp, code, msg, hdrs):
        return fp

opener = urllib.request.build_opener(NoRedirectHandler)

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_request(self):
        # Read request body if present
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Build target path
        path = self.path
        if path.startswith('/senaite'):
            # Path starts with /senaite -> /VirtualHostBase/https/NGROK_HOST:443/VirtualHostRoot/senaite/...
            rewritten_path = f"/VirtualHostBase/https/{NGROK_HOST}:443/VirtualHostRoot{path}"
        elif path == '/':
            # Redirect root to /senaite
            self.send_response(302)
            self.send_header('Location', '/senaite')
            self.end_headers()
            return
        else:
            # For other paths, map directly
            rewritten_path = f"/VirtualHostBase/https/{NGROK_HOST}:443/VirtualHostRoot{path}"

        target_url = f"http://{TARGET_HOST}:{TARGET_PORT}{rewritten_path}"

        # Copy request headers
        headers = {}
        for key, val in self.headers.items():
            if key.lower() not in ('host', 'content-length'):
                headers[key] = val
        
        # Explicitly set the host header for the target Zope instance
        headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"

        req = urllib.request.Request(
            target_url,
            data=body,
            headers=headers,
            method=self.command
        )

        try:
            with opener.open(req) as res:
                status_code = getattr(res, 'status', getattr(res, 'code', 200))
                self.send_response(status_code)
                # Copy response headers
                for key, val in res.headers.items():
                    if key.lower() not in ('transfer-encoding', 'content-length', 'connection'):
                        self.send_header(key, val)
                
                res_content = res.read()
                self.send_header('Content-Length', len(res_content))
                self.end_headers()
                self.wfile.write(res_content)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for key, val in e.headers.items():
                if key.lower() not in ('transfer-encoding', 'content-length', 'connection'):
                    self.send_header(key, val)
            res_content = e.read()
            self.send_header('Content-Length', len(res_content))
            self.end_headers()
            self.wfile.write(res_content)
        except Exception as e:
            self.send_error(500, str(e))

    def do_GET(self):
        self.do_request()
    def do_POST(self):
        self.do_request()
    def do_HEAD(self):
        self.do_request()
    def do_PUT(self):
        self.do_request()
    def do_DELETE(self):
        self.do_request()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    server = ThreadingHTTPServer(('0.0.0.0', port), ProxyHandler)
    print(f"Proxying from http://localhost:{port} to http://{TARGET_HOST}:{TARGET_PORT} with VHM rewriting...")
    server.serve_forever()
