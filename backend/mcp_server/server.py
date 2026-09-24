import functools
import sys
from pathlib import Path

# Ensure backend/ is on path so confluence_client can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from mcp_server.confluence_client import ConfluenceClient
from custom_logger import logger
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

mcp = FastMCP("Confluence MCP")
client = ConfluenceClient()


def logged(fn):
    """Log every tool run inside the MCP server with its input and output.

    The agent-side log records what the model asked for; this records what the
    server actually did, which is where a Confluence failure shows up.
    functools.wraps keeps the signature and annotations FastMCP needs to build
    the tool schema.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        logger.info(f"MCP_TOOL_RUN | tool={fn.__name__} | input={kwargs or args}")
        try:
            output = fn(*args, **kwargs)
        except Exception as exc:
            logger.info(f"MCP_TOOL_FAILED | tool={fn.__name__} | error={exc}")
            raise
        logger.info(f"MCP_TOOL_OUTPUT | tool={fn.__name__} | output={output}")
        return output

    return wrapper


@mcp.tool()
@logged
def search_pages(query: str, limit: int = 10) -> str:
    """Search Confluence pages by keyword or phrase."""
    data = client.search_pages(query, limit)
    results = data.get("results", [])
    if not results:
        return "No pages found."
    return "\n".join(
        f"ID: {r['id']} | Title: {r['title']} | Space: {r.get('space', {}).get('name', 'N/A')}"
        for r in results
    )


@mcp.tool()
@logged
def get_page(page_id: str) -> str:
    """Get the full content of a Confluence page by its ID."""
    data = client.get_page(page_id)
    title = data.get("title", "")
    body = data.get("body", {}).get("storage", {}).get("value", "")
    return f"Title: {title}\n\n{body}"


@mcp.tool()
@logged
def list_spaces(limit: int = 25) -> str:
    """List all available Confluence spaces."""
    data = client.list_spaces(limit)
    results = data.get("results", [])
    if not results:
        return "No spaces found."
    return "\n".join(f"Key: {s['key']} | Name: {s['name']}" for s in results)


@mcp.tool()
@logged
def list_pages(space_key: str, limit: int = 25) -> str:
    """List the pages in a Confluence space, with each page's ID."""
    data = client.list_pages(space_key, limit)
    results = data.get("results", [])
    if not results:
        return f"No pages found in space {space_key}."
    return "\n".join(f"ID: {p['id']} | Title: {p['title']}" for p in results)


@mcp.tool()
@logged
def create_page(space_key: str, title: str, content: str, parent_id: str = "") -> str:
    """Create a new Confluence page in the given space."""
    data = client.create_page(space_key, title, content, parent_id or None)
    url = data.get("_links", {}).get("webui", "")
    return f"Page created — ID: {data['id']} | URL: {url}"


@mcp.tool()
@logged
def update_page(page_id: str, title: str, content: str) -> str:
    """Update an existing Confluence page by its ID."""
    existing = client.get_page(page_id)
    version = existing.get("version", {}).get("number", 1)
    data = client.update_page(page_id, title, content, version)
    new_version = data.get("version", {}).get("number", "")
    return f"Page updated — ID: {data['id']} | Version: {new_version}"


if __name__ == "__main__":
    logger.info("MCP_SERVER_START | server=Confluence MCP | transport=stdio")
    mcp.run()
