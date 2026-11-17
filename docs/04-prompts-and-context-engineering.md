# Prompt templates and context engineering

## Templates
A template separates stable instructions from dynamic values. It makes prompts reusable, testable, and reviewable.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a concise backend engineering tutor. Do not invent facts."),
    MessagesPlaceholder("history", optional=True),
    ("human", "Explain {topic} for a {level} developer.")
])
messages = prompt.invoke({"history": [], "topic": "Kafka idempotency", "level": "senior"})
print(messages)
```

Concepts: PromptTemplate, ChatPromptTemplate, MessagesPlaceholder, partial variables, few-shot examples, retrieved context, prompt versioning. Few-shot examples should represent expected behavior and include edge cases.

## Context engineering
Include only relevant, authorized, current evidence. Preserve source metadata. Remove duplicates. Define what to do when evidence conflicts or is insufficient. Test prompt versions against a fixed dataset.

## Prompt injection
User input, retrieved documents, web pages, and tool outputs are untrusted. Instructions embedded in them must not override system policy. Delimit and label evidence as data, not authority. This is defense-in-depth, not a security boundary. Enforce authorization in code; never rely on a prompt to secure tenant data or prevent destructive actions.

## Lab
Create concise and detailed prompts for the same task. Evaluate 10 questions for correctness, completeness, hallucinations, latency, and token cost. Version the prompt and keep regression examples.