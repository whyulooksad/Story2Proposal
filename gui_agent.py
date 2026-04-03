from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent, SkillLoader, settings


async def main() -> None:
    settings.mcp_servers = {}

    skill_loader = SkillLoader(ROOT / "skills")

    desktop_agent = Agent(
        name="desktop_agent",
        description="负责桌面环境相关任务，包括应用发现、启动、窗口操作与后续桌面自动化。",
        model="qwen-plus",
        instructions=(
            "You are the desktop operations agent.\n"
            "You are responsible for desktop-environment tasks only.\n"
            "MCP servers may already be connected, but their tools are hidden until you activate a skill.\n"
            "You must first choose the correct skill from your skill catalog.\n"
            "After a skill is activated, you may only use the tools visible under that skill.\n"
            "If a required desktop-control tool is unavailable, say clearly which next tool is missing.\n"
            "Output in Chinese. Keep the answer concise, factual, and action-oriented."
        ),
        mcpServers={
            "windows_env": {
                "command": sys.executable,
                "args": [str(ROOT / "tools" / "windows_env_tools.py"), "--mcp"],
            }
        },
    ).with_skill_loader(skill_loader, agent_name="desktop_agent")

    router_agent = Agent(
        name="router_agent",
        description="入口智能体，负责识别任务类型并转发给合适的领域智能体。",
        model="qwen-plus",
        instructions=(
            "You are the entry agent for a multi-agent desktop assistant.\n"
            "Route the task to the correct subagent.\n"
            "If the task is about desktop operations, desktop applications, GUI control, "
            "music playback, or future desktop automation, you must call desktop_agent.\n"
            "Do not answer such tasks yourself.\n"
            "After handing off, let the delegated agent finish the task."
        ),
        nodes={desktop_agent},
    )

    try:
        result = await router_agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "帮我打开QQ音乐放《见字如面》。",
                    }
                ],
                "temperature": 0.1,
            }
        )
        for index, message in enumerate(result["messages"], start=1):
            print(f"[{index}] {message}")
    finally:
        await router_agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
