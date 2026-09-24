"""Application-wide logger.

Writes to backend/logs/app_<date>.log and to stderr. The log is meant to read
as a trace of what the agent actually did: which tool was called, with what
input, and what came back. Library chatter (HTTP calls, Flask request lines,
MCP framing) is silenced so nothing competes with those events.

stderr is used deliberately: the MCP server runs as a stdio subprocess and its
stdout carries the protocol, so log records must never go there.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(message)s"
DATE_FORMAT = "%H:%M:%S"

current_date = datetime.now().strftime("%Y-%m-%d")
file_handler = TimedRotatingFileHandler(
    LOG_DIR / f"app_{current_date}.log", when="midnight", interval=1, encoding="utf-8"
)
file_handler.suffix = "%Y-%m-%d"
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
logger = logging.getLogger("confluence-agent")

# Libraries that log every request/response. Without this the log is flooded
# with "HTTP Request: GET ..." and one line per Flask request.
NOISY_LOGGERS = (
    "azure",
    "azure.core.pipeline",
    "azure.openai",
    "httpx",             # Confluence + Azure OpenAI HTTP calls
    "httpcore",
    "openai",
    "werkzeug",          # Flask request log and the auto-reloader
    "mcp",
    "mcp.server",
    "mcp.server.lowlevel.server",
    "FastMCP",
    "asyncio",
    "urllib3",
)
for name in NOISY_LOGGERS:
    logging.getLogger(name).setLevel(logging.WARNING)

# The MCP stdio client logs a harmless "Attempted to exit cancel scope in a
# different task" ERROR each time an agent run finishes and the subprocess is
# torn down. It is a shutdown race inside the library, not an app failure.
logging.getLogger("agents.mcp").setLevel(logging.CRITICAL)

