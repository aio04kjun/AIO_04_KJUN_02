import argparse
import json
import os
import sys
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from dotenv import load_dotenv
from langsmith import tracing_context

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT.parent)
sys.path.insert(0, str(ROOT.parent))
load_dotenv(ROOT.parent / ".env", override=True)

from seoul_subway_api_test import SUBWAY_API_URL
from seoul_subway_multi_tool_agent import run_agent, search_subway_arrivals

FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/network.json": ("network.json", "application/json; charset=utf-8"),
}
LINES = {line["name"] for line in json.loads((ROOT / "network.json").read_text(encoding="utf-8"))}


class PositionError(ValueError):
    pass


@lru_cache(maxsize=64)
def positions(line, interval):
    key = os.getenv("SEOUL_SUBWAY_API_KEY", "").strip()
    if not key:
        raise PositionError("상위 폴더 .env에 SEOUL_SUBWAY_API_KEY를 설정해 주세요.")
    name = quote(line, safe="")
    url = f"{SUBWAY_API_URL}/{quote(key, safe='')}/json/realtimePosition/0/300/{name}"
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("errorMessage") or payload
    if result.get("code") not in ("INFO-000", "INFO-200"):
        code = str(result.get("code", "응답 형식 오류"))
        if not code.isascii() or not code.replace("-", "").isalnum():
            code = "응답 형식 오류"
        raise PositionError(f"{line} 위치 데이터를 불러오지 못했습니다. ({code})")
    trains = payload.get("realtimePositionList") or []
    fields = ("trainNo", "statnNm", "statnId", "statnTnm", "statnTid", "updnLine", "trainSttus", "recptnDt", "directAt")
    return [{field: row.get(field) for field in fields} for row in trains]


class Handler(BaseHTTPRequestHandler):
    def send_data(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload, status=200):
        self.send_data(json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path in FILES:
            filename, content_type = FILES[url.path]
            self.send_data((ROOT / filename).read_bytes(), content_type)
            return
        query = parse_qs(url.query)
        try:
            if url.path == "/api/positions":
                line = query.get("line", [""])[0]
                if line not in LINES:
                    self.send_json({"error": "노선을 선택해 주세요."}, 400)
                    return
                self.send_json({"trains": positions(line, int(monotonic() // 20))})
            elif url.path == "/api/arrivals":
                station = query.get("station", [""])[0].strip()
                if station != "서울역":
                    station = station.removesuffix("역").strip()
                if not station or len(station) > 60:
                    self.send_json({"error": "역 이름을 입력해 주세요."}, 400)
                    return
                with tracing_context(enabled=False):
                    payload = search_subway_arrivals.invoke({"station_name": station})
                fields = ("subwayId", "trainLineNm", "arvlMsg2", "arvlMsg3", "barvlDt")
                rows = payload.get("realtimeArrivalList") or []
                self.send_json({"station": station, "arrivals": [{key: row.get(key) for key in fields} for row in rows]})
            else:
                self.send_json({"error": "경로를 찾을 수 없습니다."}, 404)
        except PositionError as exc:
            self.send_json({"error": str(exc)}, 502)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            self.send_json({"error": "서울시 API 응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요."}, 502)

    def do_POST(self):
        if self.path != "/api/agent":
            self.send_json({"error": "경로를 찾을 수 없습니다."}, 404)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json({"error": "JSON 요청이 필요합니다."}, 415)
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 2048:
                raise ValueError
            query = json.loads(self.rfile.read(size)).get("query", "")
            if not isinstance(query, str) or not 0 < len(query.strip()) <= 240:
                raise ValueError
        except (ValueError, AttributeError):
            self.send_json({"error": "240자 이내로 질문을 입력해 주세요."}, 400)
            return
        if not os.getenv("OPENAI_API_KEY", "").strip():
            self.send_json({"error": "상위 폴더 .env에 OPENAI_API_KEY를 설정해 주세요."}, 503)
            return
        try:
            with tracing_context(enabled=False):
                answer = run_agent(query.strip())
            self.send_json({"answer": answer or "답변을 받지 못했습니다. 역 이름을 포함해 다시 질문해 주세요."})
        except Exception:
            self.send_json({"error": "에이전트 실행에 실패했습니다. API 키와 연결 상태를 확인해 주세요."}, 502)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    options = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", options.port), Handler) as server:
        print(f"수도권 전철 관제도  http://127.0.0.1:{options.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
