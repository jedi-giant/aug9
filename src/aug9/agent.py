import asyncio
from pathlib import Path

from dotenv import load_dotenv
from agents import Agent, Runner
from agents.mcp import MCPServerStdio


load_dotenv()

skill_paths = [
    Path("skills/sg-place-finder/SKILL.md"),
    Path("skills/sg-weather/SKILL.md"),
]

skill_instructions = "\n\n".join(
    path.read_text()
    for path in skill_paths
)

async def run_agent(user_input: str) -> str:
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
            instructions=skill_instructions,
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
