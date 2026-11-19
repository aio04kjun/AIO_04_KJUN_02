"""질문 분석, LangChain ReAct, 날씨에 맞는 바다 여행 추천."""

import json
import re
from datetime import date, timedelta
from decimal import Decimal
from threading import Lock

from coast_data import CITIES, get_weather, search_stays, settings, today_korea

PROVIDERS = {"OpenAI": ("OPENAI", "gpt-5-mini"), "Gemini": ("GEMINI", "gemini-3.5-flash-lite")}
CONDITIONS = ("여유롭게", "활동적으로", "피곤해요")
TOOLS = {
    "일정": ("get_weather", "search_stays"), "날씨": ("get_weather",),
    "숙소": ("search_stays",), "두 정보": ("get_weather", "search_stays"),
}


class ProviderError(RuntimeError):
    pass


def mock_intent(question, city, condition, today):
    for name, region in CITIES.items():
        if name in question or region["sea"] in question:
            city = name
            break

    start = today
    explicit = re.search(r"\b\d{4}-\d{2}-\d{2}\b", question)
    korean = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", question)
    try:
        if explicit:
            start = date.fromisoformat(explicit[0])
        elif korean:
            month, day = map(int, korean.groups())
            year = today.year + (today.month == 12 and month == 1)
            start = date(year, month, day)
        elif "모레" in question or "내일" in question:
            start += timedelta(days=2 if "모레" in question else 1)
    except ValueError as exc:
        raise ValueError("여행 날짜를 다시 확인해 주세요.") from exc

    duration = re.search(r"\d+\s*박\s*(\d+)\s*일", question)
    if not duration:
        duration = re.search(r"(\d+)\s*일\s*(?:동안|일정|여행|코스)", question[korean.end():] if korean else question)
    price = re.search(r"1\s*박\s*(?:당|에)?\s*(?:예산(?:은|이)?\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(만\s*원|원)", question)
    budget = int(Decimal(price[1].replace(",", "")) * (10000 if "만" in price[2] else 1)) if price else None

    if re.search(r"피곤|지쳤|컨디션이 안", question):
        condition = "피곤해요"
    elif re.search(r"활동적|많이 걷", question):
        condition = "활동적으로"
    elif "여유롭게" in question:
        condition = "여유롭게"

    has_stays = bool(re.search(r"숙소|호텔|숙박|펜션", question))
    has_weather = bool(re.search(r"날씨|기온|미세먼지|예보|강수|바람", question))
    task = "일정"
    if not re.search(r"코스|일정|동선|여행\s*(?:계획|추천)", question):
        if has_stays and (has_weather or "추천" in question):
            task = "두 정보"
        elif has_stays:
            task = "숙소"
        elif has_weather:
            task = "날씨"
    return {"city": city, "task": task, "start": start, "days": int(duration[1]) if duration else 1,
            "budget": budget, "condition": condition}


def live_model(provider):
    prefix, default_model = PROVIDERS[provider]
    env = settings()
    key = env.get(f"{prefix}_API_KEY", "").strip()
    if provider == "Gemini" and not key:
        key = env.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise ValueError(f"{provider}를 사용하려면 .env에 {prefix}_API_KEY를 설정해 주세요.")

    try:
        options = dict(model=env.get(f"{prefix}_MODEL", "").strip() or default_model,
                       api_key=key, timeout=45, max_retries=0)
        if provider == "OpenAI":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(**options)
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(**options, vertexai=False)
    except ImportError as exc:
        raise ProviderError("OpenAI와 Gemini를 사용하려면 requirements.txt의 패키지를 설치해 주세요.") from exc


def extract_live_intent(model, provider, question, city, condition, today):
    from typing import Literal
    from pydantic import BaseModel, Field

    class Intent(BaseModel):
        city: Literal["강릉", "태안", "여수"]
        task: Literal["일정", "날씨", "숙소", "두 정보"]
        start: date
        days: int = Field(ge=1)
        budget: int | None = Field(default=None, ge=0)
        condition: Literal["여유롭게", "활동적으로", "피곤해요"]

    method = "function_calling" if provider == "OpenAI" else "json_schema"
    try:
        intent = model.with_structured_output(Intent, method=method).invoke([
            ("system", f"한국시간 오늘은 {today}. 바다 여행 질문에서 조건만 추출한다. 지원 도시는 서해 태안, "
             f"동해 강릉, 남해 여수다. 질문에 도시가 없으면 {city}, 컨디션이 없으면 {condition}을 사용한다. "
             "일정·관광·힐링·식사 코스 요청은 '일정', 정보만 원하면 '날씨', '숙소', '두 정보'로 구분한다. "
             "날씨에 어울리는 숙소 추천은 '두 정보'다. 날짜·일수 생략 시 오늘·1일. 명시된 1박 예산만 원 단위로 추출한다."),
            ("human", question),
        ])
        if intent is not None:
            return intent.model_dump()
    except Exception as exc:
        raise ProviderError(f"{provider}에서 여행 조건을 받아오지 못했습니다. API 키, 모델, 사용 한도와 연결 상태를 확인해 주세요.") from exc
    raise ProviderError("여행 조건을 읽지 못했습니다. 날짜와 원하는 코스를 다시 적어 주세요.")


def weather_context(day):
    if day is None or day.get("rain") is None:
        return "unknown", "예보를 확인할 수 없어 실내 대안을 우선했어요."
    if day["rain"] >= 60 or day["icon"] in {"rain", "storm", "snow"}:
        return "wet", "비나 눈을 피할 수 있는 실내 코스를 우선했어요."
    if (day.get("wind") or 0) >= 35:
        return "wind", "바람이 강해 해안 산책 대신 실내를 우선했어요."
    if day.get("high") is not None and day["high"] <= 8:
        return "cold", "기온이 낮아 따뜻한 실내 코스를 우선했어요."
    return "mild", "강수 가능성이 낮아 바다 가까이에서 시간을 보내기 좋아요."


def build_routes(intent, forecast):
    region = CITIES[intent["city"]]
    days = {day["date"]: day for day in forecast.get("days", [])}
    plans = []
    visits = {True: 0, False: 0}
    for i in range(intent["days"]):
        day = (intent["start"] + timedelta(days=i)).isoformat()
        mode, note = weather_context(days.get(day))
        indoor = mode != "mild"
        tour, rest = region["indoor" if indoor else "outdoor"]
        if visits[indoor] % 2:
            tour = region["alternate"][int(indoor)]
        visits[indoor] += 1
        condition = intent["condition"]
        if condition == "피곤해요":
            rest = region["indoor"][1]
            meal = region["meals"][0]
            meal_note = "가볍게 먹고 쉴 수 있는 한 끼예요."
        elif indoor:
            meal = region["meals"][1]
            meal_note = "실내 코스 사이에 따뜻한 식사를 넣었어요."
        else:
            meal = region["meals"][2 if condition == "활동적으로" else 0]
            meal_note = "산책 뒤에 든든히 먹기 좋아요." if condition == "활동적으로" else "바다를 둘러본 뒤 여유롭게 식사해요."
        plans.append({"date": day, "note": note, "stops": [
            {"label": "관광", "title": tour, "description": "날씨에 맞춰 실내에서 둘러봐요." if indoor else "바닷가 풍경을 가까이에서 만나보세요."},
            {"label": "힐링", "title": rest, "description": "앉아서 쉬는 시간을 넉넉히 잡았어요." if indoor or condition == "피곤해요" else "물가에 잠시 머물며 천천히 걸어요."},
            {"label": "식사", "title": meal, "description": meal_note},
        ]})
    return plans


def rank_stays(stays, forecast, intent):
    dates = {(intent["start"] + timedelta(days=i)).isoformat() for i in range(intent["days"])}
    conditions = [weather_context(day)[0] for day in forecast.get("days", []) if day["date"] in dates]
    indoor = any(mode != "mild" for mode in conditions) or intent["condition"] == "피곤해요"
    items = stays["items"]
    if items and items[0]["sheltered"] is not None and conditions:
        items = sorted(items, key=lambda row: (bool(row["sheltered"]) != indoor, row["price"]))
    return {**stays, "items": [{**row, "match": bool(conditions) and row["sheltered"] is not None
                               and bool(row["sheltered"]) == indoor} for row in items]}


def run_agent(model, provider, question, intent, allowed, lookup, results):
    from langchain.agents import create_agent
    from langchain_core.tools import tool

    @tool
    def get_weather() -> str:
        """선택한 해안 지역의 7일 기온, 강수, 미세먼지와 조회 상태를 읽는다."""
        return json.dumps(lookup("get_weather"), ensure_ascii=False)

    @tool
    def search_stays() -> str:
        """선택한 지역의 숙소와 확인 가능한 1박 가격, 조회 상태를 읽는다."""
        return json.dumps(lookup("search_stays"), ensure_ascii=False)

    system = ("등록된 도구를 각각 한 번 호출하고 도구 결과를 근거로 한국어 두 문장 이내의 요약을 작성한다. "
              "확인되지 않은 가격, 예보, 영업 상태를 만들지 않는다. 예시 숙소는 예시라고 명시한다. "
              "관광·힐링·식사 세부 목록은 화면에서 별도로 제공한다. "
              f"여행 조건은 {intent}이다.")
    try:
        agent = create_agent(model, tools=[t for t in (get_weather, search_stays) if t.name in allowed], system_prompt=system)
        result = agent.invoke({"messages": [("human", question)]}, config={"recursion_limit": 9})
        return result["messages"][-1].text.strip()
    except Exception as exc:
        if not results:
            raise ProviderError(f"{provider} 응답을 완료하지 못했습니다. 사용 한도와 연결 상태를 확인해 주세요.") from exc
        return "모델 요약이 중단되어 조회가 완료된 정보로 코스를 구성했어요."


def plan_trip(payload):
    question = payload.get("question", "")
    provider = payload.get("provider", "Mock")
    city = payload.get("city", "강릉")
    condition = payload.get("condition", "여유롭게")
    weather_mode = payload.get("weather", "sample")
    sample = weather_mode == "sample"
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError("여행 질문을 1~500자 사이로 입력해 주세요.")
    if provider not in ("Mock", *PROVIDERS) or city not in tuple(CITIES) or condition not in CONDITIONS or weather_mode not in ("sample", "live"):
        raise ValueError("여행지, 컨디션, 추천 모델을 다시 선택해 주세요.")
    today = today_korea()
    model = live_model(provider) if provider != "Mock" else None
    intent = (extract_live_intent(model, provider, question, city, condition, today) if model is not None
              else mock_intent(question, city, condition, today))
    if not 1 <= intent["days"] <= 3 or not 0 <= (intent["start"] - today).days <= 7 - intent["days"]:
        raise ValueError("오늘부터 7일 안에 들어오는 1~3일 여행을 입력해 주세요.")

    city = intent["city"]
    callbacks = {
        "get_weather": lambda: get_weather(city, today, sample),
        "search_stays": lambda: search_stays(city, intent["budget"], sample),
    }
    allowed = TOOLS[intent["task"]]
    results = {}
    events = []
    locks = {name: Lock() for name in allowed}

    def lookup(name):
        with locks[name]:
            if name not in results:
                events.append({"stage": "Action", "tool": name})
                results[name] = callbacks[name]()
                events.append({"stage": "Observation", "tool": name})
            return results[name]

    if model is None:
        for name in allowed:
            lookup(name)
        summary = ""
    else:
        summary = run_agent(model, provider, question, intent, allowed, lookup, results)
        if any(name not in results for name in allowed):
            summary = "모델이 요청한 도구에서 받은 정보만 표시해요. 일부 조회가 완료되지 않았어요."

    forecast = results.get("get_weather")
    stays = results.get("search_stays")
    routes = build_routes(intent, forecast or {}) if intent["task"] == "일정" else []
    return {"city": city, "sea": CITIES[city]["sea"], "provider": provider,
            "intent": {**intent, "start": intent["start"].isoformat()}, "summary": summary,
            "routes": routes, "weather": forecast, "stays": rank_stays(stays, forecast or {}, intent) if stays else None,
            "events": events}
