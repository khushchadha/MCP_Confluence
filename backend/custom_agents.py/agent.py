import sys
import time
from pathlib import Path
from agents import Agent, OpenAIChatCompletionsModel, RunContextWrapper, Runner
from agents.mcp import MCPServerStdio
from utils.agent_client import get_agent_client
from utils.helpers import load_prompt
from custom_logger import logger, short

PROMPTS_DIR = Path(__file__).parent / "prompts"
MCP_SERVER = Path(__file__).parent.parent / "mcp_server" / "server.py"

_agent_client = None
_model_name = None


def _get_client():
    global _agent_client, _model_name
    if _agent_client is None:
        _agent_client, _model_name = get_agent_client()
    return _agent_client, _model_name


async def _list_tool_names(mcp_server, agent) -> str:
    """Tool names exposed by the MCP server, for the connection log line.

    `list_tools` gained required run_context/agent parameters in newer agents
    SDK versions, so try that first and fall back to the older no-arg form.
    This is logging only — never fail a run because of it.
    """
    try:
        try:
            tools = await mcp_server.list_tools(RunContextWrapper(context=None), agent)
        except TypeError:
            tools = await mcp_server.list_tools()
        return ", ".join(t.name for t in tools)
    except Exception:
        return ""


def _tool_call_fields(item):
    """Pull (name, arguments) off a tool_call_item, which the SDK hands back
    either as a dict or as a typed object depending on the model adapter."""
    raw = getattr(item, "raw_item", None)
    if raw is None:
        return "unknown", ""
    if isinstance(raw, dict):
        return raw.get("name", "unknown"), raw.get("arguments", "")
    return getattr(raw, "name", None) or "unknown", getattr(raw, "arguments", "") or ""


def _tool_output(item):
    """The tool's return value; `output` is set by the SDK, raw_item is the
    protocol-level fallback."""
    output = getattr(item, "output", None)
    if output is not None:
        return output
    raw = getattr(item, "raw_item", None)
    if isinstance(raw, dict):
        return raw.get("output", "")
    return getattr(raw, "output", "") or ""


async def stream_main_agent_output(user_input: str):
    logger.info(f"RUN_START | agent=Main Agent | query={short(user_input)}")
    started = time.perf_counter()

    streamed_any_text = False
    final_output = ""
    tool_calls = 0
    agent_client, model_name = _get_client()

    try:
        async with MCPServerStdio(
            params={"command": sys.executable, "args": [str(MCP_SERVER)]},
            cache_tools_list=True,
        ) as mcp_server:
            agent = Agent(
                name="Main Agent",
                instructions=load_prompt(PROMPTS_DIR / "main_agent_instruction.md"),
                model=OpenAIChatCompletionsModel(
                    model=model_name,
                    openai_client=agent_client,
                ),
                mcp_servers=[mcp_server],
            )

            tool_names = await _list_tool_names(mcp_server, agent)
            logger.info(f"MCP_CONNECTED | server={mcp_server.name} | tools={tool_names}")

            result = Runner.run_streamed(agent, input=user_input)

            async for event in result.stream_events():
                if event.type == "run_item_stream_event":
                    item = event.item
                    item_type = getattr(item, "type", "")

                    if item_type == "tool_call_item":
                        tool_name, tool_args = _tool_call_fields(item)
                        tool_calls += 1
                        logger.info(f"TOOL_CALL | tool={tool_name} | input={short(tool_args)}")
                        yield {"type": "tool_call", "name": tool_name, "args": tool_args}

                    elif item_type == "tool_call_output_item":
                        logger.info(f"TOOL_RESULT | output={short(_tool_output(item))}")

                elif event.type == "raw_response_event":
                    data = event.data
                    if getattr(data, "type", "") == "response.output_text.delta":
                        delta = getattr(data, "delta", "")
                        if delta:
                            streamed_any_text = True
                            yield {"type": "text", "delta": delta}

            final_output = str(getattr(result, "final_output", "") or "")
            if final_output and not streamed_any_text:
                yield {"type": "text", "delta": final_output}

        logger.info(
            f"RUN_END | agent=Main Agent | tool_calls={tool_calls} | "
            f"duration={time.perf_counter() - started:.2f}s | response={short(final_output)}"
        )

    except Exception as exc:
        logger.info(f"RUN_FAILED | agent=Main Agent | query={short(user_input)} | error={exc}")
        raise
