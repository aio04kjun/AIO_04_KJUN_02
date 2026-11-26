from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from seoul_subway_api_tool_test import search_subway_arrivals
import os
load_dotenv(".env", override=True)

def run_agent(query: str):
    # Initialize the agent with the OpenAI API key
    tools = [search_subway_arrivals]
    agent = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                       model_name="gpt-4o-mini",
                       ).bind_tools(tools)
    messages = [
        SystemMessage(content="너는 서울 지하철 실시간 도착 정보를 조회하는 전문가야." \
                        "사용자가 역 이름을 입력하면 해당 역의 도착 정보를 반환해줘."),
        HumanMessage(content=query)
    ]    
    registered_tool_names = {tool.name:tool for tool in tools}
    for i in range(1, 6):
        llm = agent.invoke(messages)
        messages.append(llm)
        if not llm.tool_calls:
            return llm.content
        for call in llm.tool_calls:
            fn = registered_tool_names[call["name"]]
            res = fn.invoke(call["args"])
            messages.append(ToolMessage(content=str(res), tool_call_id=call["id"]))
if __name__ == "__main__":
    query = input("지하철 역 이름을 입력하세요: ")
    result = run_agent(query)
    print(result)