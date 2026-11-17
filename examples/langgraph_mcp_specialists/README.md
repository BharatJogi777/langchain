# LangGraph specialist agents with multiple MCP servers

Three specialist agents connect to separate MCP servers:

- Logs specialist → logs tools only.
- Metrics specialist → metrics tools only.
- Infrastructure specialist → infrastructure tools only.

The supervisor uses structured routing and LangGraph handoffs. The MCP servers return mock, read-only data; they do not access or modify real infrastructure.

## Setup

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_mcp_specialists/requirements.txt
ollama pull llama3.2:3b
```

Run the live integration example:

```bash
python examples/langgraph_mcp_specialists/main.py
```

The MCP client starts the three stdio server processes automatically.

Run deterministic tests (no Ollama/MCP processes required):

```bash
PYTHONPATH=examples/langgraph_mcp_specialists pytest -q examples/langgraph_mcp_specialists/tests
```

See [Lesson 30](../../docs/30-specialist-agents-multiple-mcp-servers.md) for the architecture, security model, troubleshooting, and exercises.
