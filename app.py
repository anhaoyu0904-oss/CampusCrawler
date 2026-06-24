from __future__ import annotations

import json
import sys
import threading
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from campus_crawler import collect, download_file, export_results


if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS")).resolve()
else:
    APP_ROOT = Path(__file__).resolve().parent
    RESOURCE_ROOT = APP_ROOT

WEB_DIR = RESOURCE_ROOT / "web"
DOWNLOAD_DIR = APP_ROOT / "downloads"
HOST = "127.0.0.1"
PORT = 8765


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_POST(self) -> None:
        if self.path == "/api/collect":
            self.handle_collect()
            return
        if self.path == "/api/download":
            self.handle_download()
            return
        if self.path == "/api/export":
            self.handle_export()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        if self.path.startswith("/downloads/"):
            self.serve_download()
            return
        super().do_GET()

    def handle_collect(self) -> None:
        try:
            payload = self.read_json()
            result = collect(
                str(payload.get("url", "")),
                str(payload.get("mode", "logo")),
                int(payload.get("max_pages", 12)),
            )
            self.send_json(result)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_download(self) -> None:
        try:
            payload = self.read_json()
            url = str(payload.get("url", ""))
            saved_to = download_file(url, DOWNLOAD_DIR / "files")
            relative = saved_to.relative_to(APP_ROOT).as_posix()
            self.send_json(
                {
                    "saved_path": str(saved_to),
                    "download_url": f"/{relative}",
                }
            )
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_export(self) -> None:
        try:
            payload = self.read_json()
            export_format = str(payload.get("format", "csv"))
            content, content_type, extension = export_results(list(payload.get("items", [])), export_format)
            export_dir = DOWNLOAD_DIR / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            path = export_dir / f"campus-crawler-{datetime.now():%Y%m%d-%H%M%S}.{extension}"
            path.write_bytes(content)
            relative = path.relative_to(APP_ROOT).as_posix()
            self.send_json({"saved_path": str(path), "download_url": f"/{relative}"})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def serve_download(self) -> None:
        requested = (APP_ROOT / self.path.lstrip("/")).resolve()
        if not requested.is_file() or APP_ROOT not in requested.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.directory = str(APP_ROOT)
        super().do_GET()

    def read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def send_json(self, data: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        print(f"[CampusCrawler] {self.address_string()} - {format % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"CampusCrawler is running: {url}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
