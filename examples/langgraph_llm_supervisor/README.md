# LLM-powered LangGraph supervisor

This example uses a local Ollama chat model to propose specialist routes. Pydantic validates the decision, and Python enforces an allow-list, delegation budget, task-length limit, and no-repeat rule before LangGraph follows a handoff.

## Requirements

- Python 3.12 recommended
- Ollama running locally
- `llama3.2:3b` pulled locally (or set `OLLAMA_MODEL`)

## Setup

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_llm_supervisor/requirements.txt
ollama pull llama3.2:3b
python examples/langgraph_llm_supervisor/main.py
```

## Tests

The tests use a fake structured model; they do not need Ollama:

```bash
PYTHONPATH=examples/langgraph_llm_supervisor pytest -q examples/langgraph_llm_supervisor/test_supervisor.py
```

The specialists are mock evidence collectors. They do not call real monitoring systems or execute infrastructure changes. Read the full lesson at [Lesson 29](../../docs/29-llm-powered-supervisor-structured-routing.md) before adapting this pattern.
