# Agents, agent loops, middleware, human approval

## Chain vs agent
A chain follows developer-defined steps. An agent uses model output to choose the next action, such as calling a tool or answering. Agents are less predictable and require stronger controls.

## Agent loop
Read state and tool inventory → ask model for next action → validate and execute requested tool → append result → continue → stop on final answer or budget. Enforce maximum steps, wall-clock deadline, token budget, and tool-call budget.

```python
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain.tools import tool
@tool
def get_word_length(word: str) -> int:
    """Return the number of characters in a word."""
    return len(word)
model = ChatOllama(model="llama3.2:3b", temperature=0)
agent = create_agent(model=model, tools=[get_word_length], system_prompt="Use the tool when asked for a word's length.")
result = agent.invoke({"messages": [{"role": "user", "content": "How many letters are in extraordinary?"}]})
for message in result["messages"]:
    print(type(message).__name__, message.content)
```

Exact create_agent options and middleware APIs evolve. Inspect the installed version and official reference; do not assume remembered signatures apply to every release.

## Middleware
Middleware/hooks can inspect or transform state around model/tool execution, redact data, enforce deterministic policy, log events, and limit behavior. Treat middleware as application code and unit-test it. Hard security rules belong in deterministic code.

## Human approval
For a consequential action: agent proposes target/reason/evidence → application checks policy → human approves/rejects a scoped proposal → execution service revalidates actor and target → execute → audit. An approval prompt alone is not a control; the execution boundary must verify approval and scope.

## When not to use an agent
Fixed ETL, CRUD, exact calculations, deterministic routing, and known workflows usually belong in ordinary Python or LCEL.

## Lab
Build a read-only investigation agent with maximum five tool steps and an overall timeout. Simulate a tool failure and verify safe termination.