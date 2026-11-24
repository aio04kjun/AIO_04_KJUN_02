"""Serve the local Wine Pairing Lab and connect it to the existing agent."""

import argparse
import base64
import binascii
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory


DESIGN = Path(__file__).resolve().parent
PROJECT = DESIGN.parent
MAX_IMAGE = 5 * 1024 * 1024
MAX_REQUEST = 7 * 1024 * 1024
ASSETS = {
    "/": (DESIGN / "index.html", "text/html; charset=utf-8"),
    "/index.html": (DESIGN / "index.html", "text/html; charset=utf-8"),
    "/lab.css": (DESIGN / "lab.css", "text/css; charset=utf-8"),
    "/lab.js": (DESIGN / "lab.js", "text/javascript; charset=utf-8"),
    "/dish.jpg": (PROJECT / "dish.jpg", "image/jpeg"),
}


class InputError(ValueError):
    pass


def run_test(route, data):
    if not isinstance(data, dict):
        raise InputError("요청 형식이 올바르지 않습니다.")
    query = data.get("query")
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 2000:
        raise InputError("요리 설명을 1~2,000자로 입력해 주세요.")
    if route == "/api/search":
        style, count = data.get("style"), data.get("count")
        if style not in ("all", "red", "white", "sparkling") or type(count) is not int or not 1 <= count <= 5:
            raise InputError("와인 스타일과 검색 건수를 확인해 주세요.")
        from step2_wine_pairing_agent import search_wine_reviews

        return search_wine_reviews.invoke({"dish_flavor": query.strip(), "wine_style": style, "k": count})

    image = data.get("image")
    if image == "sample":
        image_bytes = (PROJECT / "dish.jpg").read_bytes()
    elif image is None:
        image_bytes = None
    elif isinstance(image, str):
        try:
            image_bytes = base64.b64decode(image, validate=True)
        except (binascii.Error, ValueError):
            raise InputError("JPG 파일을 다시 선택해 주세요.") from None
        if len(image_bytes) > MAX_IMAGE or not image_bytes.startswith(b"\xff\xd8\xff"):
            raise InputError("5MB 이하의 JPG 파일을 선택해 주세요.")
    else:
        raise InputError("이미지 형식이 올바르지 않습니다.")

    from step2_wine_pairing_agent import run_wine_pairing_pipeline

    if image_bytes is None:
        return {"report": run_wine_pairing_pipeline(user_query=query.strip())}
    with TemporaryDirectory(prefix="wine-lab-") as temp:
        path = Path(temp) / "dish.jpg"
        path.write_bytes(image_bytes)
        return {"report": run_wine_pairing_pipeline(user_query=query.strip(), image_path=str(path))}


class LabHandler(BaseHTTPRequestHandler):
    def send_content(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status, payload):
        self.send_content(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/api/status":
            self.send_json(200, {"server": True})
            return
        asset = ASSETS.get(self.path)
        if asset is None or not asset[0].is_file():
            self.send_error(404)
            return
        self.send_content(200, asset[0].read_bytes(), asset[1])

    def do_POST(self):
        if self.path not in ("/api/pairing", "/api/search"):
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "JSON 요청만 처리할 수 있습니다."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST:
                raise ValueError("요청 크기를 확인해 주세요.")
            request = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError):
            self.send_json(400, {"error": "요청 형식 또는 파일 크기를 확인해 주세요."})
            return
        try:
            result = run_test(self.path, request)
        except InputError as error:
            self.send_json(400, {"error": str(error)})
        except ModuleNotFoundError:
            self.send_json(503, {"error": "프로젝트 의존성을 설치해 주세요. 실행 안내의 pip 명령을 확인하세요."})
        except Exception as error:
            self.report_provider_error(error)
        else:
            self.send_json(200, result)

    def report_provider_error(self, error):
        print(f"실제 연동 실패 ({type(error).__name__})", file=sys.stderr)
        self.send_json(502, {"error": "실제 연동 요청에 실패했습니다. .env 설정, Pinecone 인덱스 및 네트워크 연결을 확인해 주세요."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8612)
    args = parser.parse_args()
    os.chdir(PROJECT)  # The original agent loads .env relative to its working directory.
    sys.path.insert(0, str(PROJECT))
    with ThreadingHTTPServer(("127.0.0.1", args.port), LabHandler) as server:
        print(f"Wine Pairing Lab · http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
