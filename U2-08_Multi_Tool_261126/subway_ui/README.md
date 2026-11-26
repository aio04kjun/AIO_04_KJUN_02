# 수도권 전철 관제도

기존 가상환경을 활성화한 뒤 부모 폴더에서 실행합니다.

```powershell
python subway_ui/server.py
```

브라우저에서 [관제도](http://127.0.0.1:8765)를 엽니다. 포트가 이미 사용 중이면 `python subway_ui/server.py --port 8766`으로 실행하고 주소의 포트도 바꿉니다. 서버를 종료하려면 터미널에서 Ctrl+C를 누릅니다.

- **열차 위치**는 선택한 노선의 서울시 API 응답을 30초마다 조회합니다. 아이콘은 API가 보고한 역에 놓이며, 같은 열차의 위치가 갱신되면 노선을 따라 이동합니다. 역 사이 화면 이동은 보고된 두 지점 사이의 보간입니다. 지도에 매칭할 수 있는 좌표가 없는 열차는 목록에 표시됩니다.
- **역별 도착**은 검색창이나 지도 위 역을 선택하면 기존 도착 조회 도구를 실행합니다. 부모 폴더의 .env에 SEOUL_SUBWAY_API_KEY가 필요합니다.
- **지하철 에이전트에게 질문하기**는 기존 run_agent를 호출합니다. 부모 폴더의 .env에 OPENAI_API_KEY도 필요합니다.
- **예시 모드**에서 API 연결 없이 위치 애니메이션과 역 검색을 볼 수 있습니다.

정적 노선도는 공개 역 좌표와 역 간 연결을 사용한 개략도입니다. 데이터 기준에 따라 일부 연장 구간이나 역이 빠질 수 있습니다. 실시간 위치 지원은 서울시 API의 운영 범위에 따릅니다.

[노선·역 좌표·연결 데이터](https://github.com/JoeYunHa/korea_seoul_subway_static_data) · [연장 구간 역 좌표](https://github.com/myyrakle/datasets/tree/master/stations-kr/20260429) · [서울시 열차 위치 API](https://data.seoul.go.kr/dataList/OA-12601/A/1/datasetView.do)
