# LangGraph dynamic fan-out with Send

This example demonstrates runtime map-reduce:
- dispatch one worker per validated service using Send;
- pass each worker a small custom input;
- aggregate worker updates using a list reducer;
- enforce a maximum fan-out size;
- handle an empty input list;
- sort results before generating a stable report.

## Run

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest -v
~~~

No model, API key, MCP server, or cloud account is required. Worker findings are deterministic mock data. Replace the worker with bounded, authorized service or MCP calls for a real system.
