"""어린이집정보공개포털의 전국 검색 및 시설 상세조회 MCP 서버."""

import asyncio
import csv
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

DIRECTORY = Path(__file__).resolve().parent
SOURCE = "https://www.data.go.kr/data/3065251/openapi.do"
API_BASE = "https://api.childcare.go.kr/mediate/rest"
PORTAL = "https://info.childcare.go.kr/info_html5/pnis/search"

load_dotenv(DIRECTORY / ".env", override=False)
# httpx의 요청 로그에는 쿼리 문자열의 인증키가 포함될 수 있다.
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp = MCPServer("DaycareInfoMCP")

PROVINCE_ALIASES = {
    "경기": "경기도", "충북": "충청북도", "충남": "충청남도",
    "경북": "경상북도", "경남": "경상남도", "강원도": "강원특별자치도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도",
    "제주도": "제주특별자치도", "광주광역시": "전남광주통합특별시",
    "광주": "전남광주통합특별시", "전남": "전남광주통합특별시",
    "전라남도": "전남광주통합특별시",
}
GWANGJU_CODES = {"12210", "12240", "12270", "12300", "12330"}


def compact(value: str) -> str:
    return "".join(value.split()).casefold()


def find_regions(region: str) -> list[dict[str, str]]:
    with (DIRECTORY / "daycare_regions.csv").open(encoding="utf-8-sig", newline="") as file:
        regions = list(csv.DictReader(file))

    query = compact(region)
    if re.fullmatch(r"[0-9]{5}", query):
        return [row for row in regions if row["code"] == query]

    aliases = PROVINCE_ALIASES.copy()
    for row in regions:
        province = row["province"]
        aliases[province] = province
        short = re.sub(r"(통합특별시|특별자치도|특별자치시|특별시|광역시|도)$", "", province)
        aliases.setdefault(short, province)

    for alias in sorted(aliases, key=len, reverse=True):
        if not query.startswith(alias):
            continue
        district = query[len(alias):]
        matches = [row for row in regions if row["province"] == aliases[alias]]
        if alias in {"광주", "광주광역시"}:
            matches = [row for row in matches if row["code"] in GWANGJU_CODES]
        if alias in {"전남", "전라남도"}:
            matches = [row for row in matches if row["code"] not in GWANGJU_CODES]
        matches = [
            row for row in matches
            if not district or row["district"].startswith(district) or row["district"].endswith(district)
        ]
        if matches:
            return matches

    return [
        row for row in regions
        if query and (row["district"].startswith(query) or row["district"].endswith(query))
    ]


class DaycareAPIError(Exception):
    """도구에 반환해도 되는 오류 메시지."""


def api_key(operation: str) -> str:
    return os.getenv(f"CHILDCARE_{operation}_API_KEY", "").strip() or os.getenv("CHILDCARE_API_KEY", "").strip()


async def portal_page(client: httpx.AsyncClient, url: str, **params: str | int) -> BeautifulSoup:
    try:
        response = await client.get(url, params=params or None)
        response.raise_for_status()
    except httpx.HTTPError:
        raise DaycareAPIError("공개 포털에 연결하지 못했습니다. 잠시 후 다시 시도하세요.") from None
    return BeautifulSoup(response.text, "html.parser")


async def search_portal(name: str, regions: list[dict[str, str]], limit: int) -> dict[str, Any]:
    scopes = []
    for province in dict.fromkeys(row["province"] for row in regions):
        selected = [row for row in regions if row["province"] == province]
        if len(selected) > 1 and selected == find_regions(province):
            scopes.append((selected[0]["code"][:2], "", selected))
        else:
            scopes.extend((row["code"][:2], row["code"], [row]) for row in selected)

    matches = {}
    failed = []
    truncated = False
    async with httpx.AsyncClient(timeout=12) as client:
        for province_code, district_code, selected in scopes:
            offset = 0
            for _ in range(5):
                try:
                    page = await portal_page(
                        client, f"{PORTAL}/NurseryNameContentsSlL.jsp",
                        flag="NM", ctprvn=province_code, signgu=district_code,
                        crname=name.strip(), offset=offset, searchOpt="Y",
                    )
                    table = page.select_one("table:has(#unitySearchCaption)")
                    if table is None:
                        raise DaycareAPIError("공개 포털의 검색 결과 형식이 예상과 다릅니다.")
                except DaycareAPIError as exc:
                    failed.append({"region_code": district_code or province_code, "error": str(exc)})
                    break

                for link in table.select("a[onclick^='fnPreviewPopOpen']"):
                    code_match = re.search(r"'([0-9]{11})'", link["onclick"])
                    cells = link.find_parent("tr").find_all("td", recursive=False)
                    if code_match is None or len(cells) < 8:
                        continue
                    code = code_match[1]
                    label = cells[2].get_text(" ", strip=True)
                    district_name = compact(label.split("/")[-1])
                    district = next(
                        (row["code"] for row in selected if row["code"] == code[:5]
                         or compact(row["district"]) == district_name),
                        district_code or code[:5],
                    )
                    matches[code] = {
                        "facility_code": code, "region_code": district,
                        "name": link.get_text(" ", strip=True), "region": label,
                        "capacity": cells[6].get_text(" ", strip=True),
                        "enrolled": cells[7].get_text(" ", strip=True),
                        "source": f"{PORTAL}/preview/SummaryInfoSlPu.jsp?flag=YJ&STCODE_POP={code}",
                    }

                next_link = page.select_one('a[href="#page_next"][onclick]')
                next_offset = re.search(r"'([0-9]+)'", next_link["onclick"]) if next_link else None
                if next_offset is None or int(next_offset[1]) <= offset:
                    break
                if len(matches) >= limit:
                    truncated = True
                    break
                offset = int(next_offset[1])
            else:
                truncated = True

        ordered = sorted(matches.values(), key=lambda row: (
            compact(row["name"]) != compact(name), row["name"], row["region"], row["facility_code"],
        ))
        results = ordered[:limit]
        # 동명이거나 단일 후보일 때만 요약 페이지에서 주소를 확인한다.
        for row in results[:5]:
            if len(results) == 1 or sum(compact(other["name"]) == compact(row["name"]) for other in results) > 1:
                try:
                    summary = await portal_page(client, row["source"])
                    address = summary_fields(summary).get("주소")
                    if address:
                        row["address"] = address
                except DaycareAPIError:
                    pass

    result = {
        "total": len(ordered), "results": results, "truncated": truncated or len(ordered) > limit,
        "source": f"{PORTAL}/NurseryNameSlL.jsp",
    }
    if failed:
        result["failed_regions"] = failed
        if not results and len(failed) == len(scopes):
            result["error"] = failed[0]["error"]
    return result


def summary_fields(page: BeautifulSoup) -> dict[str, str]:
    table = next((caption.parent for caption in page.find_all("caption")
                  if caption.get_text(strip=True) == "요약 정보"), None)
    if table is None:
        return {}
    fields = {}
    for header in table.select('th[scope="row"]'):
        cell = header.find_next_sibling()
        if cell and cell.name == "td" and len(header.parent.find_all("td", recursive=False)) <= 2:
            label = header.get_text(" ", strip=True)
            if label == "제공서비스":
                value = ", ".join(item.get_text(" ", strip=True) for item in cell.select("li:has(input[checked])"))
            else:
                value = " ".join(cell.get_text(" ", strip=True).split())
            if value:
                fields[label] = value
    return fields


async def portal_details(facility_code: str, region_code: str) -> dict[str, Any]:
    summary_url = f"{PORTAL}/preview/SummaryInfoSlPu.jsp?flag=YJ&STCODE_POP={facility_code}"
    async with httpx.AsyncClient(timeout=12) as client:
        summary = await portal_page(client, summary_url)
        fields = summary_fields(summary)
        if not fields.get("기관명"):
            raise DaycareAPIError("공개 포털에서 해당 시설의 요약 정보를 확인하지 못했습니다.")

        sources = {"요약": summary_url}
        for label, endpoint, flag in (
            ("기본 현황", "BasisPresentConditionSlPu.jsp", "GH"),
            ("영유아 및 교직원", "ChildStaffSlPu.jsp", "BG"),
        ):
            sources[label] = f"{PORTAL}/preview/{endpoint}?flag={flag}&STCODE_POP={facility_code}"
        tabs = await asyncio.gather(
            *(portal_page(client, url) for label, url in sources.items() if label != "요약"),
            return_exceptions=True,
        )

    missing = []
    for label, page in zip(("기본 현황", "영유아 및 교직원"), tabs):
        if isinstance(page, DaycareAPIError):
            missing.append(label)
            continue
        if isinstance(page, BaseException):
            raise page
        caption_name = "CCTV 시설현황" if label == "기본 현황" else "연령별 반 현황"
        caption = next((tag for tag in page.find_all("caption") if tag.get_text(strip=True) == caption_name), None)
        if caption is None:
            missing.append(label)
            continue
        # 첫 데이터 행의 첫 셀은 CCTV 총설치대수 또는 총정원이다.
        for row in caption.parent.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            expected_count = 11 if label == "기본 현황" else 4
            if len(cells) < expected_count or not cells[0].get_text(strip=True).isdigit():
                continue
            keys = ("CCTV 설치수",) if label == "기본 현황" else ("정원", "현원")
            if label != "기본 현황" and not all(cell.has_attr("rowspan") for cell in cells[:2]):
                continue
            fields.update({key: cell.get_text(strip=True) for key, cell in zip(keys, cells)})
            break
        else:
            missing.append(label)

    result = {
        "found": True, "facility_code": facility_code, "region_code": region_code,
        "details": fields, "source": summary_url, "sources": sources,
    }
    if missing:
        result["unavailable_sections"] = missing
    return result


async def fetch_rows(
    client: httpx.AsyncClient, operation: str, region_code: str, facility_code: str | None = None
) -> list[dict[str, str]]:
    key = api_key(operation)
    if not key:
        raise DaycareAPIError("CHILDCARE_API_KEY 환경 변수에 포털에서 발급받은 인증키를 설정하세요.")
    params = {"key": key, "arcode": region_code}
    if facility_code:
        params["stcode"] = facility_code
    service = f"cpmsapi{operation}"
    try:
        response = await client.get(f"{API_BASE}/{service}/{service}/request", params=params)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except httpx.HTTPStatusError as exc:
        raise DaycareAPIError(f"어린이집 API HTTP 오류 ({exc.response.status_code}).") from None
    except httpx.RequestError:
        raise DaycareAPIError("어린이집 API 연결에 실패했습니다. 잠시 후 다시 시도하세요.") from None
    except ElementTree.ParseError:
        raise DaycareAPIError("어린이집 API가 올바른 XML을 반환하지 않았습니다.") from None

    if root.tag != "response":
        raise DaycareAPIError("어린이집 API 응답 형식이 예상과 다릅니다.")
    code = (root.findtext("errcode") or "").strip()
    if code == "INFO-200":
        return []
    if code == "INFO-100":
        raise DaycareAPIError(f"어린이집 API {operation}의 인증키와 활용 승인 상태를 확인하세요.")
    if code and code != "INFO-000":
        raise DaycareAPIError("어린이집 API가 요청 처리 오류를 반환했습니다.")

    return [
        {field.tag.lower(): (field.text or "").strip() for field in item}
        for item in root.iter("item")
    ]


@mcp.tool(structured_output=True)
async def search_daycares(name: str, region: str, limit: int = 10) -> dict[str, Any]:
    """어린이집 이름(부분 일치)과 지역으로 검색합니다. 예: 서울 강서구, 경기 성남시, 11500.

    같은 이름의 후보는 지역과 공개 주소로 구분하세요. 상세조회에는 결과의
    facility_code와 region_code를 함께 사용하세요. limit은 1~50입니다.
    """
    term = compact(name)
    if not term or not region.strip():
        return {"error": "어린이집 이름과 지역을 입력하세요."}
    if not 1 <= limit <= 50:
        return {"error": "limit은 1~50 사이여야 합니다."}
    regions = find_regions(region)
    if not regions:
        return {"error": "지역을 찾지 못했습니다. 시·도와 시·군·구 또는 5자리 시군구 코드를 입력하세요."}

    if not api_key("021"):
        return await search_portal(name, regions, limit)

    matches = {}
    failed_regions = []
    async with httpx.AsyncClient(timeout=12) as client:
        for start in range(0, len(regions), 6):
            batch = regions[start:start + 6]
            responses = await asyncio.gather(
                *(fetch_rows(client, "021", area["code"]) for area in batch),
                return_exceptions=True,
            )
            for area, rows in zip(batch, responses):
                if isinstance(rows, DaycareAPIError):
                    failed_regions.append({"region_code": area["code"], "error": str(rows)})
                    continue
                if isinstance(rows, BaseException):
                    raise rows
                for row in rows:
                    code = row.get("stcode")
                    if code and term in compact(row.get("crname", "")):
                        matches[code] = {
                            "facility_code": code, "region_code": area["code"],
                            "name": row["crname"], "address": row.get("craddr", ""),
                            "phone": row.get("crtelno", ""),
                            "region": f"{area['province']} {area['district']}",
                        }
            if len(failed_regions) == len(batch) and start == 0:
                first_error = failed_regions[0]["error"]
                if len(batch) == len(regions) or "인증키" in first_error:
                    return {"error": first_error, "failed_regions": failed_regions}

    ordered = sorted(matches.values(), key=lambda item: (
        compact(item["name"]) != term, item["name"], item["address"], item["facility_code"],
    ))
    if len(failed_regions) == len(regions):
        return {"error": failed_regions[0]["error"], "failed_regions": failed_regions}
    result = {"total": len(ordered), "results": ordered[:limit], "source": SOURCE}
    if failed_regions:
        result["failed_regions"] = failed_regions
    return result


DETAIL_FIELDS = {
    "crname": "어린이집명", "sidoname": "시도", "sigunguname": "시군구",
    "crtypename": "유형", "crstatusname": "운영현황", "craddr": "주소",
    "crtelno": "전화번호", "crhome": "홈페이지", "crcapat": "정원",
    "crchcnt": "현원", "chcrtescnt": "보육교직원수",
    "cctvinstlcnt": "CCTV 설치수", "crcargbname": "통학차량 운영여부",
    "crspec": "제공서비스", "datastdrdt": "데이터 기준일",
    **{f"ew_cnt_{age:02d}": f"입소대기 {age}세" for age in range(6)},
    "ew_cnt_m6": "입소대기 6세 이상", "ew_cnt_tot": "입소대기 총계",
}


@mcp.tool(structured_output=True)
async def get_daycare_details(facility_code: str, region_code: str) -> dict[str, Any]:
    """시설 코드(11자리)와 지역 코드(5자리)로 공개 상세정보를 조회합니다.

    인증키가 없으면 포털 공시 화면에 표시된 요약과 기본 현황을 조회합니다.
    누락된 항목은 추정하지 마세요.
    """
    if not re.fullmatch(r"[0-9]{11}", facility_code) or not re.fullmatch(r"[0-9]{5}", region_code):
        return {"error": "시설 코드 11자리와 지역 코드 5자리를 입력하세요."}
    try:
        if not api_key("030"):
            return await portal_details(facility_code, region_code)
        async with httpx.AsyncClient(timeout=12) as client:
            rows = await fetch_rows(client, "030", region_code, facility_code)
    except DaycareAPIError as exc:
        return {"error": str(exc)}
    facility = next((row for row in rows if row.get("stcode") == facility_code), None)
    if facility is None:
        return {"found": False, "message": "해당 지역과 시설 코드에 맞는 어린이집을 찾지 못했습니다."}
    return {
        "found": True, "facility_code": facility_code, "region_code": region_code,
        "details": {label: facility[field] for field, label in DETAIL_FIELDS.items() if facility.get(field)},
        "fields": facility, "source": "https://www.data.go.kr/data/15101154/openapi.do",
    }


if __name__ == "__main__":
    if sys.stdin.isatty():
        print(
            "어린이집 MCP 서버가 클라이언트 연결을 기다리는 중입니다. "
            "검색하려면 MCP 클라이언트에 서버를 등록하세요. 종료는 Ctrl+C입니다.",
            file=sys.stderr,
        )
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
