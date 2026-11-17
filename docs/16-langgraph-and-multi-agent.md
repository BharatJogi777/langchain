# LangGraph and multi-agent orchestration

## Why graphs
Complex workflows need explicit state, conditional routing, parallel branches, retries, checkpoints, interrupts, and human approval. LangGraph models workflows as nodes and edges over shared state.

## Concepts
State is typed workflow data. Nodes read state and return updates. Edges define transitions. Conditional edges route. Checkpoints persist progress. Interrupts pause for external input. Subgraphs compose reusable workflows.

```text
START -> classify_incident -> route
                         |-> logs specialist --|
                         |-> k8s specialist ---|-> synthesize -> human review -> END
```

## Multi-agent patterns
Subagents as tools (simple supervisor, often sequential); handoffs (control transfer); router (select specialist); parallel fan-out/fan-in (independent specialists); hierarchical teams (more complex). Use distinct agents only when responsibilities, tool permissions, context, or evaluation differ. More agents add latency, cost, state, and coordination failure.

## State design
Use explicit fields such as incident_id, tenant_id, service, evidence, findings, approval_status, actions_taken, and errors. Define which node may update each field. Prefer deterministic functions for known workflow steps and LLM calls only where language reasoning adds value.

## Lab
Build a graph that classifies an incident, runs log and Kubernetes checks in parallel, merges findings, and produces a read-only report. Add an interrupt before any hypothetical remediation.