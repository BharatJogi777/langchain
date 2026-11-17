# LangGraph workflow example

This is a deterministic, local-only example of parallel evidence collection and state reduction.

## Run

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest -v
~~~

No model, API key, MCP server, or cloud account is required. The collectors are mock functions; replace them with bounded async MCP calls in a real application.

The example uses an in-memory checkpointer for learning. It is not durable across process restarts.
