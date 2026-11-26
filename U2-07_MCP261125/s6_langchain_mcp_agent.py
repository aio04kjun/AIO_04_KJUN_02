# mcp 세션 + LLM API + 외부 API연동 결합된 AGENT

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage,SystemMessage,ToolMessage
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv('.env',override=True)

async def run_mcp_llm_agent(user_query:str)->str:
    server_params =  StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("s5_order_mcpserver.py"))],
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream,write_stream) as session:
            await session.initialize()
            listed_tools = await session.list_tools()
            mcp_tools = [{"name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                }
                for tool in listed_tools.tools
            ]

            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(mcp_tools)
            messages = [
                SystemMessage(content="주문 및 환불 업무는 MCP 서버에서 제공된 도구를 사용해 처리하세요."),
                HumanMessage(content=user_query),
            ]

            for _ in range(5):
                ai_msg = await llm.ainvoke(messages)
                messages.append(ai_msg)
                if not ai_msg.tool_calls:
                    return ai_msg.content

                for call in ai_msg.tool_calls:
                    result = await session.call_tool(call["name"], call["args"])
                    tool_out = result.model_dump_json(by_alias=True, exclude_none=True)
                    print(f"  [MCP Tool 실행] {call['name']}({call['args']}) -> {tool_out}")
                    messages.append(ToolMessage(content=str(tool_out), tool_call_id=call["id"]))

            return "최대 반복 횟수 초과"
if __name__ == "__main__":
    q = "ORD_1001 상태를 확인하고, ORD_1002는 '배송 지연 우려'로 환불 접수해줘."
    print(asyncio.run(run_mcp_llm_agent(q)))
