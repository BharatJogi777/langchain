# LangGraph subgraphs and specialist workflows

This example builds three independent child graphs (logs, metrics, infrastructure) and composes them into a parent incident-investigation graph.

It demonstrates:
- private child state schemas;
- wrapper nodes that map parent input to child input and child output to parent output;
- parallel specialist execution;
- reducer-based aggregation in parent state;
- deterministic final report ordering.

The specialist workflows use mock evidence. They are graph components, not LLM-powered agents yet.

## Run

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest -v
~~~

No API key, LLM, MCP server, or cloud credentials are required.
