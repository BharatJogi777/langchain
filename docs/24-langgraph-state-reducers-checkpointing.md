# Lesson 24 — LangGraph State, Reducers, and Checkpointing

## Learning objectives

By the end of this lesson, you should be able to:

1. Design a typed graph state.
2. Explain the difference between a state schema and a node update.
3. Use default replacement semantics and custom reducers.
4. Safely combine parallel node updates.
5. Understand overwrite, append, and idempotent merge behavior.
6. Inspect checkpoints and state history.
7. Explain thread identity, checkpoint identity, and durable persistence.
8. Avoid common state and checkpointing bugs.

## 1. State is the graph's data contract

A LangGraph state schema describes the keys available to nodes. A node receives the current state and returns a partial update.

~~~python
from typing import TypedDict

class IncidentState(TypedDict):
    incident_id: str
    service: str
    summary: str
~~~

A node does not need to return every key:

~~~python
def create_summary(state: IncidentState) -> dict:
    return {"summary": f"Investigating {state['service']}"}
~~~

The graph applies that update to the current state. For a key without a reducer, the new value replaces the old value.

Think of a node return value as a patch, not a complete replacement document.

## 2. Default replacement semantics

For a normal key, a new update replaces the previous value:

~~~python
class State(TypedDict):
    status: str
~~~

If the current status is `"investigating"` and a node returns `{"status": "resolved"}`, the next state has status `"resolved"`.

This is appropriate for scalar values with a clear single writer: status, selected route, final summary, approval decision, and so on.

Avoid multiple parallel nodes writing the same scalar key unless you have deliberately designed how those writes are resolved. Conflicting writes can raise an invalid concurrent update error.

## 3. Reducers: how updates are combined

A reducer defines how an incoming update is combined with the current value for a state key.

For example, append evidence from multiple nodes:

~~~python
import operator
from typing import Annotated, TypedDict

class State(TypedDict):
    evidence: Annotated[list[str], operator.add]
~~~

If one node returns `{"evidence": ["log evidence"]}` and another returns `{"evidence": ["CPU evidence"]}`, the reducer combines the updates with the existing list.

Conceptually:

~~~text
Existing: ["deployment evidence"]
Update A: ["log evidence"]
Update B: ["CPU evidence"]
Result:   ["deployment evidence", "log evidence", "CPU evidence"]
~~~

The order of parallel updates should not be treated as a business guarantee. If ordering matters, include timestamps or sequence numbers and sort during synthesis.

## 4. Reducer choices and their trade-offs

| Strategy | Typical use | Risk |
|---|---|---|
| Default replacement | status, summary, selected route | Concurrent writes conflict |
| List append | independent evidence records | Duplicate records on replay/retry |
| Dictionary merge | keyed observations | Define collision behavior |
| Custom idempotent merge | evidence keyed by stable ID | More code and validation |

A reducer should be deterministic. It should not call an API, write a database, generate random IDs, or perform other side effects. Reducers combine state values; nodes perform work.

### Idempotent evidence merge

Appending blindly can create duplicates if the same logical evidence is submitted more than once. A custom merge can use a stable evidence ID:

~~~python
from typing import Annotated, TypedDict

def merge_evidence(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_id = {item["evidence_id"]: item for item in existing}
    for item in incoming:
        by_id[item["evidence_id"]] = item
    return list(by_id.values())

class State(TypedDict):
    evidence: Annotated[list[dict], merge_evidence]
~~~

This is a last-write-wins merge by evidence ID. In a production system, define whether a later record is allowed to replace an earlier record, and preserve provenance and timestamps. The stable ID must be generated outside the reducer.

## 5. Parallel writes

When a graph fans out to independent nodes, each node can return its own partial update. A reducer is how compatible updates to the same state key are combined.

~~~text
                 START
                   |
              fan out
             /   |    \
          logs metrics infra
             \   |    /
               join
                 |
              summarize
~~~

The example project in this lesson implements this pattern with three collectors. Each collector returns one evidence item and the state reducer combines them.

Important: a reducer does not make external operations safe. Use idempotency keys, bounded retries, timeouts, and concurrency limits at the tool boundary (see Lesson 22).

## 6. Checkpoints and threads

A checkpointer persists graph state at execution boundaries. The configurable `thread_id` groups checkpoints for one logical graph thread.

~~~python
config = {"configurable": {"thread_id": "incident-INC-100"}}
result = graph.invoke(initial_state, config=config)
snapshot = graph.get_state(config)
print(snapshot.values)
~~~

A thread ID is not:
- an authenticated user identity;
- an authorization token;
- a unique incident ID by itself;
- a guarantee that only one worker can write the thread at a time.

Your API must authorize access to a thread before reading or resuming it. Use a tenant-aware ownership check in your application layer.

## 7. Inspect state and history

With a checkpointer enabled, inspect the current snapshot:

~~~python
snapshot = graph.get_state(config)
print(snapshot.values)
print(snapshot.next)
print(snapshot.config)
~~~

Inspect prior snapshots:

~~~python
for snapshot in graph.get_state_history(config):
    print(snapshot.metadata)
    print(snapshot.values)
~~~

State history is useful for debugging and audit investigations. It is not automatically a complete business audit log. Record consequential decisions and side effects in a dedicated audit system.

## 8. update_state is not an ordinary node

You can programmatically update a thread's state using `graph.update_state(config, values)`. This creates a new checkpoint update. It is useful for trusted application actions, operator corrections, or carefully designed resume flows.

Do not expose arbitrary state updates directly to an untrusted client. Validate the requested change, authorize the actor, and restrict which keys may be modified.

When a graph uses reducers, updates made through `update_state` are applied using those reducers too. Understand the reducer before using it for manual updates: adding an item to a list reducer appends; it does not replace the list.

## 9. In-memory versus durable checkpointers

An in-memory saver is convenient for local examples and tests. Its contents disappear when the process exits.

For production, use a durable checkpointer supported by the LangGraph version and deployment you have selected. The SQLite checkpointer is useful for local persistence experiments; PostgreSQL-backed persistence is often a better fit for a multi-instance service.

Operational concerns:
- retention and deletion policy;
- encryption and access control;
- tenant isolation;
- database backups and restore tests;
- schema/package version compatibility;
- concurrent writers and worker ownership;
- checkpoint growth and cleanup;
- recovery after process termination.

Pin the checkpointer package version alongside LangGraph. Verify its current setup instructions before deploying; checkpoint integrations are separate packages and their APIs can evolve.

## 10. Common mistakes

1. Treating graph state as a global Python dictionary shared by all users.
2. Mutating nested state values in place instead of returning updates.
3. Having parallel nodes write the same scalar key.
4. Blindly appending duplicate evidence on retries.
5. Assuming parallel branch result order is stable.
6. Storing credentials or huge raw logs in checkpoints.
7. Treating thread_id as authorization.
8. Assuming an in-memory saver survives a restart.
9. Using graph history as the only audit trail.
10. Allowing clients to modify arbitrary checkpoint state.

## 11. Run the example

From the repository root:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_state/requirements.txt
python examples/langgraph_state/main.py
python -m unittest discover -s examples/langgraph_state -p "test_*.py" -v
~~~

The example uses mock collectors and an in-memory checkpointer. It requires no API key or external service.

## 12. Exercises

1. Add a fourth collector for deployment history.
2. Change evidence append to a custom stable-ID merge.
3. Add a `failed_sources` field with a reducer and report partial failures.
4. Add a `tenant_id` to the request model, but enforce tenant authorization outside the graph.
5. Inspect the graph's state history after execution.
6. Add a test proving duplicate evidence IDs do not create duplicate entries.
7. Experiment with two separate thread IDs and verify that their state remains isolated.

## 13. Knowledge check

1. What happens to a normal state key when a node returns a new value?
2. What problem does a reducer solve for parallel branches?
3. Why can list append create duplicates?
4. What does a thread_id identify?
5. Why is a checkpointer not a replacement for an audit log?
6. Why must the API authorize a user before exposing a thread's state?

## Official references

- State and reducers: https://docs.langchain.com/oss/python/langgraph/graph-api
- Persistence and threads: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph concepts: https://docs.langchain.com/oss/python/langgraph/overview
