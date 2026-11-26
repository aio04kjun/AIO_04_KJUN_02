# 어린이집 검색·상세조회 MCP

`s7_daycare_mcpserver.py`는 표준 입출력(stdio)을 사용하는 Python MCP 서버입니다.

**인증키 없이도 검색과 상세조회가 됩니다.** 인증키가 설정되지 않은 도구는 어린이집정보공개포털의 공개 검색·공시 화면을 조회합니다. 검색 결과에는 시설 코드, 지역, 정원·현원과 공시 링크가 표시됩니다. 상세조회에서 주소, 전화번호, 운영시간, 통학차량 여부 등 화면에 공개된 값을 받을 수 있습니다. 포털 검색에서 `truncated`가 참이면 일부 결과만 반환된 것이므로 시설 이름이나 시군구를 더 구체적으로 입력하세요. [공개 검색 화면](https://info.childcare.go.kr/info_html5/pnis/search/UnitySearchSlL.jsp)

| 도구 | 입력과 반환값 |
| --- | --- |
| `search_daycares` | `name`과 `region`으로 검색합니다. 이름은 부분 일치하고 이름이 같은 시설은 주소와 시설 코드로 구분할 수 있습니다. 지역은 `서울 강서구`, `경기 성남시`, `11500`처럼 입력합니다. |
| `get_daycare_details` | 검색 결과의 `facility_code`와 `region_code`로 상세정보를 조회합니다. 연령별 입소대기는 공식 API 응답에 값이 있을 때 표시됩니다. |

## 공식 API를 사용하는 경우

1. 어린이집정보공개포털에 회원가입하고 로그인합니다. **보육정보공개 API → OPEN API**에서 아래 두 서비스를 각각 엽니다.
2. 각 서비스 상세 화면의 **기술문서**에서 Word 명세서를 내려받을 수 있습니다.
   - 전국 어린이집 정보 조회(`cpmsapi021`) [서비스 상세](https://info.childcare.go.kr/info_html5/oais/openapi/OpenApiInfoSl.jsp?flag=VIEW&svcseq=79) · [OpenAPI서비스명세서 021 v1.0 다운로드](https://info.childcare.go.kr/info/oais/common/FileDownload.jsp?flag=OPENAPIFILE&svcseq=79)
   - 어린이집별 기본정보 조회(`cpmsapi030`) [서비스 상세](https://info.childcare.go.kr/info_html5/oais/openapi/OpenApiInfoSl.jsp?flag=VIEW&svcseq=82) · [OpenAPI서비스명세서 030 v1.7 다운로드](https://info.childcare.go.kr/info/oais/common/FileDownload.jsp?flag=OPENAPIFILE&svcseq=82)
3. 각 상세 화면의 **활용신청**으로 개발계정 이용을 신청하고 승인 후 발급된 인증키를 확인합니다. [포털 개발가이드](https://info.childcare.go.kr/info_html5/oais/guide/Development.jsp)

## Windows PowerShell에서 실행

저장소 루트의 기존 `.venv`를 사용하는 예시입니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\U2-07_MCP261125\requirements.txt
.\.venv\Scripts\python.exe .\U2-07_MCP261125\s7_daycare_mcpserver.py
```

공식 API를 사용하려면 선택적으로 PowerShell에서 `$env:CHILDCARE_API_KEY = '발급받은_인증키'`를 실행하세요. 현재 PowerShell과 자식 프로세스에 적용됩니다. GUI MCP 클라이언트에서는 스크립트 옆의 기존 `U2-07_MCP261125/.env` 파일에 아래 한 줄을 추가할 수 있습니다. 이미 설정된 환경 변수가 같은 이름의 `.env` 항목보다 우선합니다.

```dotenv
CHILDCARE_API_KEY=발급받은_인증키
```

서비스별 키가 다르면 `CHILDCARE_021_API_KEY`와 `CHILDCARE_030_API_KEY`를 각각 설정하세요. 서비스별 키가 있으면 공통 키보다 우선합니다. 인증키는 로컬에 보관하세요.

Windows 명령 프롬프트(cmd.exe)에서는 `set "CHILDCARE_API_KEY=발급받은_인증키"`로 현재 세션에 설정합니다.

## MCP 클라이언트에서 연결

클라이언트의 stdio 서버 설정에 아래 실행 파일과 스크립트 경로를 등록하세요. 검색어는 MCP 클라이언트에 입력합니다. 클라이언트가 서버를 자동으로 실행하고 도구를 호출합니다. 터미널에서 직접 실행하면 연결 대기 메시지가 표시되며, `Ctrl+C`로 종료할 수 있습니다.

```json
{
  "mcpServers": {
    "daycare": {
      "command": "C:/AIO_04_kjun_02/.venv/Scripts/python.exe",
      "args": ["C:/AIO_04_kjun_02/U2-07_MCP261125/s7_daycare_mcpserver.py"]
    }
  }
}
```

검색 예시 입력은 `{"name":"햇살어린이집","region":"서울 강서구"}`입니다. 검색 결과에서 주소를 확인한 다음 반환된 시설 코드와 지역 코드로 상세조회를 호출하세요.

지역 코드는 어린이집정보공개포털의 지역 선택 목록을 2026년 11월 25일에 저장한 것입니다. 시·도 전체를 지정하면 해당 시군구를 순회하므로 시군구를 함께 입력하면 응답이 더 빠릅니다. 일부 시군구에 오류가 나면 검색 결과의 `failed_regions`에 표시됩니다. [공식 지역 선택 화면](https://info.childcare.go.kr/info_html5/oais/openapi/OpenApiInfoSl.jsp?flag=VIEW&svcseq=84)
