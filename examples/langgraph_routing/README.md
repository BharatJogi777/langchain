# LangGraph conditional routing and loops

A deterministic DevOps incident workflow showing:
- severity-based conditional routing;
- an evidence collection loop;
- a confidence threshold and maximum-attempt exit;
- a graph-level recursion limit;
- unit and graph tests.

## Run

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest -v
~~~

The confidence progression and evidence are mock fixtures for teaching control flow, not a production incident scoring system.
