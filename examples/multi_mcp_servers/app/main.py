import asyncio
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "logs": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(PROJECT_ROOT / "servers" / "logs_server.py")],
            },
            "infrastructure": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [
                    str(PROJECT_ROOT / "servers" / "infrastructure_server.py")
                ],
            },
        }
    )

    tools = await client.get_tools()

    print("Discovered tools:")
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    agent = create_agent(
        model=ChatOllama(model="llama3.2:3b", temperature=0),
        tools=tools,
        system_prompt=(
            "You are a cautious DevOps investigation assistant. "
            "Use tools to gather evidence before drawing conclusions. "
            "Distinguish evidence from hypotheses. Never claim mock data is real."
        ),
    )

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Investigate payment-service. Search timeout logs, "
                        "count errors, check health, and inspect CPU usage. "
                        "Summarize the evidence."
                    ),
                }
            ]
        }
    )

    print("\nAgent response:")
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
