# Confluence MCP Agent

A Confluence assistant with two ways to drive the same set of tools:

- **Chat** — ask a question in plain English; an Azure OpenAI agent decides which
  Confluence tools to call, and the answer streams back token by token.
- **MCP Tools** — a form for each tool, so you can call it directly and see the
  raw result. Useful for showing what the agent is actually doing underneath.

Both go through the same **MCP server**, which wraps the Confluence REST API.

## Architecture

```
frontend/index.html  ──POST /ask────────┐
  (chat, SSE stream)                    │
                                        ▼
frontend/mcp.html    ──POST /tools/call──►  backend/server.py  (Flask)
  (tool forms)                            │           │
                                          │           └──────────────┐
                                          ▼                          ▼
                             custom_agents.py/agent.py     mcp_server/confluence_client.py
                               (Azure OpenAI agent)                  │
                                          │                          │
                                          ▼                          │
                             mcp_server/server.py  ─────────────────►┘
                               (MCP tool definitions)                │
                                                                     ▼
                                                        Confluence Cloud REST API
```

The chat path reaches Confluence through the MCP protocol (the agent spawns
`mcp_server/server.py` over stdio). The tool-form path calls the same
`ConfluenceClient` directly, so both surfaces always behave identically.

## The tools

| Tool | Arguments | What it returns |
|------|-----------|-----------------|
| `list_spaces` | `limit` | Every space with its key |
| `list_pages` | `space_key`, `limit` | Pages in one space, with page IDs |
| `search_pages` | `query`, `limit` | Pages matching a keyword, across spaces |
| `get_page` | `page_id` | Full page title and body |
| `create_page` | `space_key`, `title`, `content`, `parent_id?` | New page ID and URL |
| `update_page` | `page_id`, `title`, `content` | New version number |

Most tools need an ID you don't have yet, so they chain:

```
list_spaces → space key → list_pages → page ID → get_page / update_page
```

> Personal space keys start with `~` (e.g. `~71202028abd…`). Pass the key exactly
> as `list_spaces` returned it — dropping the `~` gives a 404.

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # then fill in your credentials
```

`.env` needs Azure OpenAI credentials (for chat) and Confluence credentials
(for the tools). A Confluence API token comes from
<https://id.atlassian.com/manage-profile/security/api-tokens>.
`CONFLUENCE_URL` is the site root without `/wiki` — e.g. `https://your-site.atlassian.net`.

## Running it

**Terminal 1 — backend:**

```bash
cd backend
python server.py
# Confluence Agent backend running on http://127.0.0.1:5000
```

**Then open the frontend** (plain HTML, no build step):

```bash
start frontend/index.html      # chat
start frontend/mcp.html        # tool forms
```

The two pages link to each other in the top-right corner.

You don't start the MCP server yourself — the agent launches it as a subprocess
when a chat request comes in.

## Project layout

```
backend/
  server.py                        Flask API: /ask (chat, SSE) and /tools/call (direct tools)
  custom_agents.py/
    agent.py                       Agent setup + streaming loop
    prompts/
      main_agent_instruction.md    System prompt: role, tool list, chaining rules
  mcp_server/
    server.py                      MCP tool definitions (the agent's interface)
    confluence_client.py           Confluence REST calls (the only place HTTP happens)
  utils/
    agent_client.py                Azure OpenAI client factory + env validation
    helpers.py                     Prompt loading
  custom_logger/__init__.py        File + console logging, third-party noise muted
  logs/                            Daily rotating logs (gitignored)
frontend/
  index.html                       Chat UI, renders streamed text and tool calls
  mcp.html                         One form per tool
  style.css                        Shared styles
```

## Notes

- Logging writes to `backend/logs/app_<date>.log` and the console. Per-request
  HTTP lines from `httpx`, `openai`, and `werkzeug` are muted to WARNING, and the
  Flask auto-reloader is off, so the console shows only application events.
- `create_page` and `update_page` write to real Confluence. `update_page`
  replaces the entire page body — read the page first if you want to keep it.
- Secrets live only in `backend/.env`, which is gitignored. `.env.example` is the
  committed template.
