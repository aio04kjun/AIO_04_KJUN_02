import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(".env", override=True)


@tool
def lookup_user_quota(user_id: str) -> dict:
    """사용자 ID(user_id)의 일일 API 호출 한도와 현재 사용량을 조회합니다."""
    quotas = {
        "U-100": {"daily_limit": 1000, "used": 640},
        "U-200": {"daily_limit": 5000, "used": 4890},
    }
    q = quotas.get(user_id.upper(), {"daily_limit": 500, "used": 120})
    return {"user_id": user_id.upper(), **q, "remaining": q["daily_limit"] - q["used"]}


@tool
def calc_overage_cost(overage_calls: int, unit_cost_krw: int = 50) -> dict:
    """초과 호출 건수(overage_calls)와 건당 단가(unit_cost_krw)로 추가 과금을 계산합니다."""
    safe_calls = max(0, overage_calls)
    return {"overage_calls": safe_calls, "unit_cost_krw": unit_cost_krw, "overage_krw": safe_calls * unit_cost_krw}


def execute_dynamic_agent(prompt: str, tools_list: list) -> str:
    # if/elif 분기 대신 이름 -> BaseTool 매핑 레지스트리 사용
    tool_registry = {t.name: t for t in tools_list}
    llm_with_tools = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools_list)

    messages = [
        SystemMessage(content="쿼터 조회와 초과 과금 계산은 제공된 도구를 동적으로 호출해 처리하세요."),
        HumanMessage(content=prompt),
    ]

    # 나머지 코드를 완성
    # 1. llm이 호출할수 있는 tools를 확보하고 그결과를 message 저장
    # 2. tools를 순환 하면서 실제 tool을 호출해서 결과를 message 저장(ToolMessages)
    # 3. 최종 저장 된 message를 이용해서 최종 답변 출력

        # execute_dynamic_agent() 내부에서 messages 선언 바로 아래에 추가
    for _ in range(8):
        # 1. LLM 응답을 받고, 도구 호출 요청이 담긴 AIMessage를 저장
        ai_msg = llm_with_tools.invoke(messages)
        messages.append(ai_msg)

        # 3. 도구 호출이 없으면 최종 답변 반환
        if not ai_msg.tool_calls:
            return ai_msg.text

        # 2. 요청받은 도구를 실행하고 각 결과를 ToolMessage로 저장
        for call in ai_msg.tool_calls:
            selected_tool = tool_registry[call["name"]]
            tool_msg = selected_tool.invoke(call)
            messages.append(tool_msg)

    raise RuntimeError("LLM 호출 8회 안에 최종 답변을 생성하지 못했습니다.")


if __name__ == "__main__":
    answer = execute_dynamic_agent(
        "U-200 사용자의 남은 일일 API 호출 한도를 조회해줘. "
        "오늘 200건을 더 호출한다면 초과 건수와 추가 과금은 얼마야?",
        [lookup_user_quota, calc_overage_cost],
    )
    print("최종 답변:", answer)