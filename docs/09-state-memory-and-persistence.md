# State, memory, checkpointers, stores

## Distinctions
Context window: data sent in one model request. Conversation state: messages and app state for a thread. Checkpoint: persisted execution snapshot. Long-term store: records available across threads/sessions. An LLM does not remember previous API calls unless history/state is supplied.

## Thread-scoped checkpointing
LangChain agents are built on LangGraph foundations and can use a checkpointer. A thread ID scopes the conversation.

```python
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent
agent = create_agent(model=model, tools=tools, checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "demo-thread-1"}}
agent.invoke({"messages": [{"role": "user", "content": "My service is checkout."}]}, config=config)
result = agent.invoke({"messages": [{"role": "user", "content": "Which service did I mention?"}]}, config=config)
print(result["messages"][-1].content)
```

InMemorySaver is for learning/tests; data disappears on restart and is not shared across workers. Production needs a supported durable checkpointer with migrations, retention, backups, and access control.

## Long-term memory
Define namespace (tenant/user), schema/version, provenance, write permission, retention, deletion, encryption, access logs, and conflict resolution. Do not store every message. Summarize selectively and retain source/time/confidence. Never trust model-generated memory as verified fact without policy.

## Privacy
Enforce tenant isolation in persistence. Never use a caller-supplied thread ID as authorization. Verify ownership before loading state. Keep secrets and sensitive data out of prompts and memory unless there is an approved need and protection.

## Lab
Build thread-scoped chat state, then document replacement with a durable backend. Test that one thread cannot read another thread's history.