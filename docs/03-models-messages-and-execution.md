# Models, messages, invocation, streaming, batching

## Chat models
A chat model accepts a sequence of messages and returns an AI message. Chat roles separate instructions from user content. Provider role mapping can differ.

## Message types
SystemMessage: high-level behavior constraints. HumanMessage: user input. AIMessage: assistant response and possible tool calls. ToolMessage: result tied to a tool-call ID.

```python
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
model = ChatOllama(model="llama3.2:3b", temperature=0)
messages = [SystemMessage(content="You are a careful Python tutor."), HumanMessage(content="Explain context managers.")]
response = model.invoke(messages)
print(response.content)
print(response.usage_metadata)
```

## Execution methods
invoke: one completed call. ainvoke: async call. batch/abatch: multiple inputs. stream/astream: progressive chunks. Chunk content may be partial; do not assume each chunk is a full sentence or valid JSON.

```python
for chunk in model.stream("Explain database indexing."):
    if chunk.content:
        print(chunk.content, end="", flush=True)
print()
```

## Production concerns
Set timeouts, output-token limits, and concurrency caps. Handle cancellation, provider errors, truncation, empty responses, and malformed metadata. Retry only transient failures with bounded attempts. Do not blindly retry non-idempotent tool actions. Record latency, model, status, token usage, and trace IDs without logging sensitive content.

## Lab
Implement an async model service with timeout handling and a typed response. Test success and failure with a fake model; keep live-provider tests separate.