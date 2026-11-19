"""로컬 HTML과 여행 추천 JSON API를 제공한다."""

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from coast_data import ROOT
from planner import ProviderError, plan_trip


class TravelHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def reply(self, status, payload):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if self.path != "/api/plan":
            self.reply(404, {"error": "요청 주소를 확인해 주세요."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError
        except (UnicodeError, ValueError):
            self.reply(400, {"error": "여행 질문을 읽을 수 없습니다."})
            return

        try:
            result = plan_trip(payload)
        except ValueError as exc:
            self.reply(400, {"error": str(exc)})
        except ProviderError as exc:
            self.reply(502, {"error": str(exc)})
        else:
            self.reply(200, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8018)
    port = parser.parse_args().port
    with ThreadingHTTPServer(("127.0.0.1", port), TravelHandler) as server:
        print(f"물결여행 http://127.0.0.1:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
