"""만든 상황판을 로컬에서 열어 보는 임시 서버."""
import http.server
import socketserver
import webbrowser
from functools import partial
from pathlib import Path


def serve(path, port=8765, open_browser=True):
    p = Path(path).resolve()
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(p.parent))
    socketserver.TCPServer.allow_reuse_address = True
    url = f"http://localhost:{port}/{p.name}"
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"{url}  — 멈추려면 Ctrl+C")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n중지했습니다.")
