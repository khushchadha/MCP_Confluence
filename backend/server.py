import asyncio
import importlib.util
import json
import sys
from pathlib import Path


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



if __name__ == "__main__":
    # debug/use_reloader are off: the reloader starts the app twice and floods
    # the console with restart logs, which is noise during a demo.
    logger.info("SERVER_START | url=http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)
