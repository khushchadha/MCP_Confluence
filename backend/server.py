import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)
AGENT_PATH = BASE_DIR / "custom_agents.py" / "agent.py"

# Ensure backend/ is on sys.path so agent.py can import utils and custom_logger
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from custom_logger import logger  # noqa: E402  (needs sys.path set above)

spec = importlib.util.spec_from_file_location("main_agent_module", AGENT_PATH)
main_agent_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_agent_module)

app = Flask(__name__)
CORS(app)

# Lazy singleton for the Confluence client (used by /tools/call)
_confluence_client = None

def _get_confluence_client():
    global _confluence_client
    if _confluence_client is None:
        from mcp_server.confluence_client import ConfluenceClient
        _confluence_client = ConfluenceClient()
    return _confluence_client


@app.post("/ask")
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        logger.info("ASK_REJECTED | reason=empty question")
        return jsonify({"error": "Question is required"}), 400

    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stream = main_agent_module.stream_main_agent_output(question)

        try:
            while True:
                try:
                    event = loop.run_until_complete(stream.__anext__())
                    yield f"data: {json.dumps(event)}\n\n"
                except StopAsyncIteration:
                    break
        except Exception as exc:
            logger.info(f"ASK_FAILED | question={question} | error={exc}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.post("/tools/call")
def call_tool():
    req = request.get_json(silent=True) or {}
    tool = (req.get("tool") or "").strip()
    args = req.get("args") or {}

    if not tool:
        return jsonify({"error": "tool is required"}), 400

    logger.info(f"TOOL_CALL | source=http | tool={tool} | input={args}")

    c = _get_confluence_client()
    try:
        if tool == "search_pages":
            data = c.search_pages(args.get("query", ""), int(args.get("limit", 10)))
            results = data.get("results", [])
            output = "No pages found." if not results else "\n".join(
                f"ID: {r['id']} | Title: {r['title']} | Space: {r.get('space', {}).get('name', 'N/A')}"
                for r in results
            )
        elif tool == "get_page":
            data = c.get_page(args.get("page_id", ""))
            page_body = data.get("body", {}).get("storage", {}).get("value", "")
            output = f"Title: {data.get('title', '')}\n\n{page_body}"
        elif tool == "list_spaces":
            data = c.list_spaces(int(args.get("limit", 25)))
            results = data.get("results", [])
            output = "No spaces found." if not results else "\n".join(
                f"Key: {s['key']} | Name: {s['name']}" for s in results
            )
        elif tool == "list_pages":
            space_key = args.get("space_key", "")
            data = c.list_pages(space_key, int(args.get("limit", 25)))
            results = data.get("results", [])
            if not results:
                output = f"No pages found in space {space_key}."
            else:
                output = "\n".join(
                    f"ID: {p['id']} | Title: {p['title']}" for p in results
                )
        elif tool == "create_page":
            data = c.create_page(
                args.get("space_key", ""), args.get("title", ""),
                args.get("content", ""), args.get("parent_id") or None,
            )
            url = data.get("_links", {}).get("webui", "")
            output = f"Page created — ID: {data['id']} | URL: {url}"
        elif tool == "update_page":
            existing = c.get_page(args.get("page_id", ""))
            version = existing.get("version", {}).get("number", 1)
            data = c.update_page(
                args.get("page_id", ""), args.get("title", ""),
                args.get("content", ""), version,
            )
            output = f"Page updated — ID: {data['id']} | Version: {data.get('version', {}).get('number', '')}"
        else:
            return jsonify({"error": f"Unknown tool: {tool}"}), 400

        logger.info(f"TOOL_RESULT | source=http | tool={tool} | output={output}")
        return jsonify({"result": output})
    except httpx.HTTPStatusError as exc:
        logger.info(f"TOOL_FAILED | source=http | tool={tool} | "
                    f"status={exc.response.status_code} | input={args}")
        # Turn Confluence's raw HTTP errors into something readable in the UI.
        if exc.response.status_code == 404:
            return jsonify({"error": "Not found in Confluence. Check the space key "
                                     "or page ID (personal space keys start with '~')."}), 404
        if exc.response.status_code == 401:
            return jsonify({"error": "Confluence rejected the credentials. "
                                     "Check CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN in backend/.env."}), 401
        if exc.response.status_code == 403:
            return jsonify({"error": "Confluence accepted the credentials but denied access. "
                                     "Make sure this account can access the requested Confluence space or page."}), 403
        return jsonify({"error": f"Confluence returned {exc.response.status_code}."}), 502
    except Exception as exc:
        logger.info(f"TOOL_FAILED | source=http | tool={tool} | input={args} | error={exc}")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    # debug/use_reloader are off: the reloader starts the app twice and floods
    # the console with restart logs, which is noise during a demo.
    logger.info("SERVER_START | url=http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)
