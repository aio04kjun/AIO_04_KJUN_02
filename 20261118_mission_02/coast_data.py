"""바다 여행지 자료와 숙소·예보 조회 도구."""

import json
import os
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent

# 기상 좌표, TourAPI 법정동 코드, 실외/실내 관광·힐링 코스, 식사 후보.
CITIES = {
    "강릉": {
        "sea": "동해", "coords": (37.805, 128.911), "codes": (51, 150),
        "outdoor": ("경포해변 산책", "경포호 호숫가 휴식"),
        "indoor": ("아르떼뮤지엄 강릉", "경포 바다 전망 카페"),
        "alternate": ("경포대 둘러보기", "경포아쿠아리움"),
        "meals": ("초당순두부 정식", "따뜻한 감자옹심이", "장칼국수와 감자전"),
    },
    "태안": {
        "sea": "서해", "coords": (36.500, 126.338), "codes": (44, 825),
        "outdoor": ("꽃지해변 노을 산책", "안면도 자연휴양림 숲길"),
        "indoor": ("국립태안해양유물전시관", "신진도 항구 전망 카페"),
        "alternate": ("방포해변 산책", "태안 로컬 카페에서 쉬어가기"),
        "meals": ("바지락죽과 곁들임 반찬", "따뜻한 바지락칼국수", "태안 꽃게탕 정식"),
    },
    "여수": {
        "sea": "남해", "coords": (34.743, 127.754), "codes": (46, 130),
        "outdoor": ("오동도 입구 바다 산책", "엑스포 해안 데크 휴식"),
        "indoor": ("아쿠아플라넷 여수", "엑스포 바다 전망 카페"),
        "alternate": ("자산공원 전망 산책", "여수세계박람회장 인근 실내 카페"),
        "meals": ("맑은 생선국과 밥", "따뜻한 서대국", "여수 생선구이 정식"),
    },
}
DAILY = {
    "weather_code": "code", "temperature_2m_min": "low", "temperature_2m_max": "high",
    "precipitation_probability_max": "rain", "wind_speed_10m_max": "wind",
}
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TOUR_URL = "https://apis.data.go.kr/B551011/KorService2/searchStay2"


def today_korea():
    return datetime.now(timezone(timedelta(hours=9))).date()


def settings():
    """간단한 KEY=VALUE 형식의 .env와 실행 환경을 읽는다."""
    path = ROOT / ".env"
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                values[key.strip()] = value.strip().strip("\"'")
    return values | dict(os.environ)


def fetch_json(url, **query):
    with urlopen(f"{url}?{urlencode(query)}", timeout=6) as response:
        return json.load(response)


def weather_icon(code):
    if code is None:
        return "unknown", "예보 없음"
    if code in (0, 1):
        return "sun", "맑음"
    if code == 2:
        return "partly", "구름 조금"
    if code == 3:
        return "cloud", "흐림"
    if code in (45, 48):
        return "cloud", "안개"
    if code >= 95:
        return "storm", "뇌우"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow", "눈"
    return "rain", "비"


def get_weather(city, today, sample):
    """두 API의 결과를 한국시간 날짜로 병합하고 빠진 값은 null로 둔다."""
    days = {(today + timedelta(days=i)).isoformat(): {} for i in range(7)}
    warnings = []
    if sample:
        offset = {"강릉": 0, "태안": -1, "여수": 2}[city]
        for i, day in enumerate(days.values()):
            day.update(code=[2, 0, 61, 3, 2, 80, 0][i], low=9 + offset + i % 3,
                       high=18 + offset + i % 4, rain=[15, 10, 85, 35, 20, 70, 5][i],
                       wind=[14, 12, 30, 21, 15, 28, 13][i],
                       pm10=24 + i * 3 if i < 5 else None, pm2_5=11 + i * 2 if i < 5 else None)
    else:
        lat, lon = CITIES[city]["coords"]
        common = dict(latitude=lat, longitude=lon, timezone="Asia/Seoul", forecast_days=7)
        try:
            daily = fetch_json(WEATHER_URL, **common, daily=",".join(DAILY))["daily"]
            for i, key in enumerate(daily["time"]):
                if key in days:
                    days[key].update({name: daily[field][i] for field, name in DAILY.items()})
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            warnings.append("기온·강수 예보를 가져오지 못했습니다.")
        try:
            air = fetch_json(AIR_URL, **common, hourly="pm10,pm2_5", domains="cams_global")["hourly"]
            for field in ("pm10", "pm2_5"):
                readings = defaultdict(list)
                for stamp, value in zip(air["time"], air[field], strict=True):
                    if stamp[:10] in days and value is not None:
                        readings[stamp[:10]].append(value)
                for key, values in readings.items():
                    days[key][field] = round(mean(values), 1)
        except (OSError, ValueError, TypeError, KeyError):
            warnings.append("미세먼지·초미세먼지 예보를 가져오지 못했습니다.")

    rows = []
    for key, item in days.items():
        icon, label = weather_icon(item.get("code"))
        rows.append({"date": key, "icon": icon, "label": label,
                     **{field: item.get(field) for field in ("low", "high", "rain", "wind", "pm10", "pm2_5")}})
    return {"source": "예시 예보" if sample else "Open-Meteo / CAMS", "days": rows, "warnings": warnings}


def stay_photo(item):
    photo = urlsplit(item.get("firstimage") or item.get("firstimage2") or "")
    if photo.scheme in ("http", "https") and photo.hostname in {"tong.visitkorea.or.kr", "cdn.visitkorea.or.kr"}:
        return urlunsplit(("https", photo.hostname, photo.path, photo.query, ""))
    return None


def search_stays(city, budget, sample):
    """SQLite 숙소 예시 또는 키 설정 시 공공 숙박 목록을 읽는다."""
    key = settings().get("TOUR_API_KEY", "").strip() if not sample else ""
    if key:
        region, district = CITIES[city]["codes"]
        try:
            payload = fetch_json(TOUR_URL, serviceKey=unquote(key), lDongRegnCd=region, lDongSignguCd=district,
                                 MobileOS="ETC", MobileApp="CoastTrip", _type="json", numOfRows=8)
            answer = payload["response"]
            if answer["header"]["resultCode"] != "0000":
                raise ValueError("TourAPI lookup failed")
            items = (answer["body"].get("items") or {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            rows = [{"name": item["title"], "area": item.get("addr1") or city, "price": None,
                     "sheltered": None, "image_url": stay_photo(item),
                     "description": "숙소의 가격과 실내 편의시설을 직접 확인해 주세요."} for item in items]
            rows.sort(key=lambda row: row["image_url"] is None)
            warning = "TourAPI에 1박 요금이 없어 예산 충족 여부를 확인할 수 없습니다." if budget is not None and rows else ""
            return {"source": "한국관광공사 TourAPI", "items": rows[:2], "warning": warning}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return {"source": "한국관광공사 TourAPI", "items": [], "warning": "숙박 목록을 가져오지 못했습니다."}

    with closing(sqlite3.connect(":memory:")) as db:
        db.row_factory = sqlite3.Row
        db.executescript((ROOT / "stays.sql").read_text(encoding="utf-8"))
        rows = db.execute("SELECT * FROM stays WHERE city = ? AND (? IS NULL OR price <= ?) ORDER BY price",
                          (city, budget, budget))
        return {"source": "예시 숙소 · 생성 이미지와 예시 요금", "items": [dict(row) for row in rows], "warning": ""}
