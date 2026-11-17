# Structured output, parsers, validation

## Why structured output
Downstream code should not scrape arbitrary prose. Ask for schema-shaped output, parse it, and validate it. Syntactically valid JSON is not necessarily truthful or authorized.

```python
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
class IncidentSummary(BaseModel):
    service: str = Field(min_length=1)
    severity: str
    symptoms: list[str]
    recommended_checks: list[str]
model = ChatOllama(model="llama3.2:3b", temperature=0)
structured_model = model.with_structured_output(IncidentSummary)
result = structured_model.invoke("Checkout has repeated 502 responses and elevated latency.")
print(result)
```

Structured output support depends on model/provider. If native enforcement is unavailable, use a parser with bounded repair and fail safely. Parsers include StrOutputParser, JsonOutputParser, and PydanticOutputParser. Provider-native structured output is useful when supported and reliable.

Validate required fields, types, ranges, enums, lengths, cross-field invariants, referenced IDs against authorized records, and tool arguments before execution. A valid schema can still contain false facts; validate claims against trusted evidence separately.

For malformed results, allow a bounded repair attempt, then fail safely or request human review. Avoid unlimited correction loops.

## Lab
Create a schema with a severity enum, bounded summary, and evidence references. Test missing fields, invalid severity, extra fields, and an unauthorized resource ID.