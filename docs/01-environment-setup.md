# Environment setup

## Local learning setup
For an Apple Silicon laptop with limited RAM, start with Ollama and a small model such as llama3.2:3b. A small model is useful for learning but may be unreliable at complex tool calling. Do not run unnecessarily large models and databases together.

```bash
mkdir langchain-lab && cd langchain-lab
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install langchain langchain-core langchain-ollama
```

Install only what a module needs. Later modules may require langchain-text-splitters, langchain-community, langchain-postgres, psycopg, FastAPI, pytest, mcp[cli], and langchain-mcp-adapters. Verify current compatibility before pinning.

Record exact tested versions with python -m pip freeze > requirements-lock.txt and run python -m pip check. Use uv, Poetry, or pip-tools for a reproducible application lockfile.

## Ollama
1. Install and start Ollama.
2. Run ollama pull llama3.2:3b.
3. Verify with ollama list and ollama run llama3.2:3b.
4. Keep the Ollama service running.
5. Optional API check: curl http://localhost:11434/api/tags.

```python
from langchain_ollama import ChatOllama
model = ChatOllama(model="llama3.2:3b", temperature=0)
response = model.invoke("Explain idempotency in two sentences.")
print(response.content)
```

Use an explicit integration object such as ChatOllama rather than assuming a bare model name can be provider-inferred.

## Project layout
app/{config.py,api/,schemas/,services/,llm/,tools/,agents/,retrieval/,repositories/,observability/}; tests/{unit/,integration/,evals/}; .env.example; .gitignore; pyproject.toml.

## Secrets
Never commit .env, credentials, production logs, private documents, or model caches. Commit only placeholder values in .env.example. Use runtime environment variables or a secret manager.

## Troubleshooting
- Wrong interpreter: check which python and python --version.
- Import mismatch: use python -m pip and confirm package is installed in the active venv.
- Ollama refused: start the service and check port 11434.
- Model missing: pull it first.
- Tool schema errors: simplify schema, use explicit typed parameters, validate inputs, and test the function independently.