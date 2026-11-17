# Runnables and LCEL

## Runnable contract
A Runnable is a composable operation with a common execution interface: invoke, ainvoke, batch, abatch, stream, and astream. Streaming semantics vary by component.

LCEL (LangChain Expression Language) composes runnables with the pipe operator.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
prompt = ChatPromptTemplate.from_template("Explain {topic} in three bullet points.")
model = ChatOllama(model="llama3.2:3b", temperature=0)
chain = prompt | model | StrOutputParser()
print(chain.invoke({"topic": "database indexes"}))
```

## Core primitives
RunnableLambda adapts a Python callable. RunnablePassthrough preserves input. RunnablePassthrough.assign adds derived fields to dictionary input. RunnableParallel runs independent branches on the same input and returns a dictionary. RunnableSequence is sequential composition. RunnableBranch routes using predicates. with_config attaches run config/tags/metadata. with_retry and with_fallbacks add explicit failure behavior. Verify exact methods against your pinned version.

```python
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
parallel = RunnableParallel({"upper": RunnableLambda(str.upper), "length": RunnableLambda(len)})
print(parallel.invoke("langchain"))
assigned = RunnablePassthrough.assign(normalized=RunnableLambda(lambda d: d["query"].strip().lower()))
print(assigned.invoke({"query": "  PAYMENTS TIMEOUT  "}))
```

Branches receive the same input. Parallel calls can increase provider load, cost, and peak memory. Use async methods in async servers; bound concurrency and avoid blocking the event loop.

## Lab
Build normalize → deterministic short/long branch → prompt → model → parser. Test empty input and both branches. Add a fallback for a simulated transient model failure.