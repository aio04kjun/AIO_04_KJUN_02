# 물결여행

서해 태안·동해 강릉·남해 여수의 바닷가 여행을 추천하는 한국어 웹 서비스입니다. 오늘부터 7일 중 1~3일 여행을 계획할 수 있습니다.

## 실행

Python 3.11 이상에서 아래 명령을 실행하고 [물결여행](http://127.0.0.1:8018)을 엽니다.

```powershell
cd .\20261118_mission_02
python server.py
```

**Mock**은 API 키와 패키지 설치 없이 실행됩니다. 처음 열면 강릉 1박 2일 예시가 표시됩니다. `실시간 예보`를 선택하면 Mock에서도 실제 Open-Meteo 데이터를 받을 수 있습니다. 예보가 제공되지 않은 수치는 `—`로 표시합니다. [날씨 API](https://open-meteo.com/en/docs) · [대기질 API와 CAMS](https://open-meteo.com/en/docs/air-quality-api)

### Gemini와 OpenAI

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe server.py
```

`.env`에 `GEMINI_API_KEY` 또는 `OPENAI_API_KEY`를 채우고 화면에서 모델을 고릅니다. 이미 `.env`가 있다면 복사 명령 대신 필요한 키만 추가합니다. `GOOGLE_API_KEY`도 Gemini 키로 지원합니다. 모델 이름은 `GEMINI_MODEL`과 `OPENAI_MODEL`에서 바꿀 수 있습니다.

## 수업에서 볼 흐름

1. 사용자 질문에서 도시, 시작일, 일수, 1박 예산, 컨디션과 요청 유형을 뽑습니다. 지원 여행지는 화면에 표시된 세 해안 도시입니다.
2. 일정 추천과 날씨에 맞는 숙소 추천에는 날씨·숙소 도구를 모두 사용합니다. 날씨만 물으면 `get_weather`, 숙소 목록만 물으면 `search_stays`를 호출합니다. OpenAI·Gemini는 LangChain ReAct로 도구를 호출하고 조회 결과를 바탕으로 요약합니다. Mock은 키워드로 의도를 해석하고 같은 조회 함수를 직접 호출합니다. [LangChain 에이전트 문서](https://docs.langchain.com/oss/python/langchain/agents)
3. 강수확률 60% 이상, 비·눈, 강풍 또는 낮은 기온에는 실내 관광과 바다 전망 휴식을 우선합니다. `피곤해요`를 고르면 앉아서 쉴 장소와 가벼운 식사를, 온화한 날 `활동적으로`를 고르면 해안 산책과 든든한 메뉴를 추천합니다. 화면 하단에서 추출한 조건과 `Action → Observation`을 확인할 수 있습니다.

예시 숙소는 SQLite에서 조회하며, 카드의 이미지와 1박 요금은 수업용입니다. `.env`에 `TOUR_API_KEY`를 넣고 실시간 예보를 선택하면 실제 숙박 목록과 제공된 대표 이미지를 조회합니다. TourAPI에서 요금이나 실내 시설 정보가 확인되지 않으면 확인 필요로 표시합니다. 식사 코스는 메뉴 중심이며 식당의 영업 상태나 예약 가능 여부는 제공하지 않습니다. [한국관광공사 국문 관광정보 서비스](https://www.data.go.kr/data/15101578/openapi.do)

## 디자인과 초기 설계 자료

`DESIGN.md`의 옅은 새벽 톤, 큰 제목, 짙은 알약형 버튼과 테라코타 강조 카드 하나를 적용했습니다. 중앙 정렬과 큰 한글 제목을 사용하고, 작은 화면에서는 숙소·코스 카드가 한 열로 바뀝니다. 날씨 아이콘은 입체 음영을 준 CSS 그래픽과 한글 상태를 함께 표시합니다.

ImageGen 내장 도구로 이미지 두 개를 만들었습니다. 생성 프롬프트는 다음과 같습니다.

- [해안 히어로](web/assets/coast-dawn.png) — “Create an ultra-wide landscape photograph for an elegant Korean coast travel website hero. Photorealistic aerial view, clear coastal water and white surf curving around a pale sand beach backed by a thin band of dark coastal pines and rocks, at dawn near Korea's east sea. Blue-grey, muted ocean teal and mist grey, mild warm dawn light. Calm luxury travel editorial, finely detailed waves, elegant and natural. Wide 3:1 intended crop, main coastline and foam visible in the middle third. No people, text, graphics, lettering, watermark or logos.”
- [예시 숙소 이미지](web/assets/coastal-stays.png) — “Create one edge-to-edge montage asset for a Korean coastal travel service. Exactly 3 columns, 2 rows of 6 distinct equal-sized photographic tiles, straight contiguous boundaries and absolutely no gutters or frame, each tile a complete different editorial photograph. Landscape aspect 3:2. Row 1 left to right: cozy light-oak oceanfront Gangneung guestroom with a wide bay window; pale modern waterfront pool hotel on the East Sea; coastal wooden cabin tucked in pines in Taean. Row 2 left to right: warm minimalist inn lounge and broad ocean window looking onto West Sea mudflats; Yeosu modern resort room and island-filled sea; Yeosu hillside white boutique guesthouse with window and muted sunset over harbor. Photoreal architectural travel photography, airy, calm, muted blue grey and warm whites. No text, signage, logos, people, labels, frames or type. Clearly distinct tile artwork without objects spilling across tiles.”

초기에 작성한 [요구사항과 검증 기준](01_요구사항_및_검증.md), [프로그램 설계](02_프로그램_설계.md), [활동 다이어그램](activity_diagram.png)에서 공통 설계 흐름을 볼 수 있습니다. 현재 구현의 지원 지역과 설정은 이 README를 기준으로 합니다.
