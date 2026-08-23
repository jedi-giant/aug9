import asyncio

from dotenv import load_dotenv
from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from aug9.core.planner import create_plan
from aug9.skills import load_skills

load_dotenv()

skill_instructions = load_skills()

async def run_agent(user_input: str) -> str:
    plan = create_plan(user_input)
    async with MCPServerStdio(
        name="Aug9 MCP Server",
        params={
            "command": "uv",
            "args": [
                "run",
                "mcp",
                "run",
                "src/aug9/mcp_server.py",
            ],
        },
    ) as server:
        agent = Agent(
            name="Aug9 Assistant",
            instructions=f"""
        {skill_instructions}

        User request plan:

        Intent:
        {plan.intent}

        Required capabilities:
        {plan.required_capabilities}

        Use this plan to guide your response.
        """,
            mcp_servers=[server],
        )
        result = await Runner.run(
            agent,
            user_input,
        )

        return result.final_output


async def main() -> None:
    result = await run_agent(
        "What is the weather at  Maxwell Food Centre?"
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
