# LangGraph state and checkpointing example

This example demonstrates:
- a typed state schema;
- a custom reducer that merges evidence by stable ID;
- three parallel evidence collectors;
- a join before synthesis;
- an in-memory checkpointer;
- checkpoint inspection through get_state and get_state_history.

## Run

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest -v
~~~

No model, credentials, MCP server, or cloud service is required. InMemorySaver is for learning and tests; it does not persist across process restarts.
