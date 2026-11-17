# Lesson 34 — Production API Security and Authentication for AI Agents

## 1. Objective

Lesson 33 exposed the investigation workflow through FastAPI. This lesson puts a trusted security boundary around it.

The core rule is:

> The model may propose a tool call. Trusted application code must decide whether that call is permitted.

A system prompt saying "do not inspect other services" is not authorization. Authorization must be checked by deterministic code at the API and tool-execution boundaries.

## 2. Threat model

The investigation API can reveal operational information such as logs, latency, deployment history, and service health. Depending on the connected MCP servers, it may eventually be able to change production infrastructure.

Threats include:
- Anonymous or stolen-token access.
- A low-privilege user requesting a privileged operation.
- A user investigating a service outside their assignment.
- Prompt injection in user input, logs, tickets, or tool results.
- The model inventing tool arguments or attempting to switch service scope.
- Excessive requests causing model or infrastructure resource exhaustion.
- Secret leakage through prompts, logs, traces, error messages, or source control.
- Overly broad MCP credentials and tools.

OWASP API Security risks include broken authentication, broken function-level authorization, and unrestricted resource consumption. OWASP's LLM risks include prompt injection, insecure output handling, sensitive information disclosure, and excessive agency.

References: [OWASP API Security Top 10](https://devguide.owasp.org/en/07-training-education/07-api-top-ten/), [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications), [OWASP prompt injection](https://genai.owasp.org/glossary/prompt-injection/).

## 3. Security architecture

~~~text
Client
  |
  | POST /token (local demo only)
  v
FastAPI authentication
  |-- password hash verification
  |-- short-lived signed JWT
  |
  | Authorization: Bearer <token>
  v
JWT validation
  |-- signature / fixed algorithm
  |-- issuer / audience / exp / nbf
  |-- active user lookup
  v
RBAC scope check
  |-- admin: run + read + manage users
  |-- investigator: run + read
  |-- viewer: read only
  v
Service authorization
  |-- is this service assigned to this principal?
  v
Per-principal rate limiter
  v
Investigation workflow
  |
  v
Per-request MCP tool wrappers
  |-- fixed tool allow-list
  |-- force requested service to authorized service
  v
Read-only MCP server
~~~

Each boundary has a distinct purpose:
- Authentication establishes identity.
- RBAC checks what operation the identity may perform.
- Service authorization checks which target resource the identity may access.
- Tool policy enforces the same boundary at the moment the model invokes an MCP tool.
- Rate limiting bounds resource consumption.

## 4. JWT authentication

The example uses FastAPI's OAuth2 bearer-token dependency and PyJWT.

A JWT is signed, not encrypted. Its payload can be decoded by anyone who possesses the token. Never place passwords, API keys, private logs, or sensitive personal data in JWT claims.

The example token includes:
- `sub`: username / subject.
- `iss`: trusted issuer.
- `aud`: intended API audience.
- `iat`: issued-at timestamp.
- `nbf`: not-before timestamp.
- `exp`: expiry timestamp.
- `jti`: unique token identifier.

Validation pins the algorithm to HS256 and verifies issuer, audience, and required time claims. The current user is reloaded from the configured user store so deactivated users and changed roles do not keep their old permissions indefinitely.

### Password hashing

Passwords are stored as Argon2id hashes using `pwdlib[argon2]`. Never store plaintext passwords or use a fast general-purpose hash such as SHA-256 for passwords.

### Important production distinction

The `/token` username/password endpoint is **demo-only**. It demonstrates password hashing and bearer JWT validation, but it implements the OAuth 2.0 Resource Owner Password Credentials grant. The current OAuth 2.0 Security Best Current Practice (RFC 9700, section 2.4) says this grant MUST NOT be used. Do not deploy this login flow. For browser/mobile applications, use an established identity provider with OpenID Connect Authorization Code + PKCE. For machine-to-machine access, use an appropriate client-credentials flow. Do not build your own identity provider unless that is genuinely your product requirement.

References: [FastAPI OAuth2 + JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [FastAPI security first steps](https://fastapi.tiangolo.com/tutorial/security/first-steps/).

## 5. RBAC and scopes

The example defines three roles:

| Role | Scopes | Purpose |
|---|---|---|
| admin | `investigations:run`, `investigations:read`, `users:manage` | Full application administration |
| investigator | `investigations:run`, `investigations:read` | Start investigations |
| viewer | `investigations:read` | Read-only access |

The investigation endpoint requires `investigations:run`. A viewer receives HTTP 403 even if their JWT is valid.

Do not use a role name as the only authorization check. Use explicit permissions/scopes at each route and resource boundary.

## 6. Service-level authorization

RBAC alone is not enough.

An investigator may be permitted to run investigations, but only for assigned services. The demo user store assigns:
- admin: all services (`*`).
- investigator: `checkout-api` and `payments-api`.
- viewer: `checkout-api`, but the viewer cannot start investigations.

The API checks the requested service against the principal's allowed-service set before it invokes the agent.

This prevents an authorized user from changing the service field to an unrelated service.

In production, load assignments from a database or policy engine, not a hard-coded Python dictionary. Consider tenant ID, environment, region, and data classification in the authorization decision.

## 7. MCP tool authorization: enforce at the tool boundary

A common mistake is to rely only on a system prompt:

~~~text
You may inspect checkout-api only.
~~~

That is not a security control. The model can produce different tool arguments, and tool output can contain hostile instructions.

The example adds `bind_tool_to_service`:
1. It checks that a tool declares a `service` argument.
2. It wraps the original MCP tool while preserving its input schema.
3. It compares the tool's requested service with the service authorized by the API.
4. It rejects a cross-service invocation before calling the original tool.

The runtime also uses a fixed allow-list of tool names per MCP server. Unknown tools fail closed.

The authorized service comes from trusted API authorization, not from model-generated arguments. The tools are scoped per request, while MCP tool discovery is performed at startup.

For real production systems, also enforce authorization on the MCP server or downstream service itself. A compromised API process or a second client must not be able to bypass the only policy check. Prefer narrowly scoped service credentials and separate read/write capabilities.

## 8. Rate limiting and resource controls

The example includes a small in-process sliding-window limiter:
- Login attempts are keyed by remote IP.
- Investigation requests are keyed by authenticated principal.
- Excess calls return HTTP 429 and a `Retry-After` header.

This limiter is intentionally a learning implementation. It is not shared across Uvicorn workers or replicas. In production, enforce limits at an API gateway or use a shared store such as Redis.

Rate limiting is not the same as concurrency control. Also set:
- A maximum number of concurrent investigations.
- An overall request deadline.
- Per-MCP-tool timeouts.
- Maximum prompt and tool-output sizes.
- Model token and request budgets.
- Queue limits and overload behavior.

## 9. Prompt injection and untrusted tool output

Prompt injection happens when untrusted content contains instructions intended to override the model's intended behavior. It can arrive directly from the user or indirectly through logs, documents, web pages, tickets, or MCP tool output.

Defenses:
- Treat user text and tool output as data, not trusted instructions.
- Delimit and label evidence clearly in prompts.
- Never let tool output grant permissions or change the caller identity.
- Do not put secrets in the model context.
- Validate every model-produced structured value.
- Keep the available tool set minimal and read-only where possible.
- Apply authorization in Python and at the downstream service.
- Require human approval for consequential actions.
- Keep audit records of principal, service, tool name, outcome, and correlation ID without logging sensitive payloads.

There is no reliable prompt wording that completely prevents prompt injection. Design the system so that a successful injection still cannot cross a deterministic permission boundary.

## 10. Secrets and deployment

Generate a local signing key:

~~~bash
openssl rand -hex 32
~~~

Set environment variables before starting the example. Use secret-manager injection in production. Never commit a real signing key, password, token, or credential to Git.

For HS256, every service that verifies tokens must protect the shared signing secret. In multi-service deployments, consider asymmetric signing (for example RS256 or ES256) so resource services receive only the public verification key.

Use TLS for all non-local traffic. Configure token expiry, rotation, revocation strategy, key rotation, audit retention, and incident response. A signed JWT remains valid until expiry unless you add revocation or version checks.

## 11. Run the secured example

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/fastapi_agent_api/requirements.txt
~~~

Generate and export secrets for the local demo:

~~~bash
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
read -s DEMO_ADMIN_PASSWORD
export DEMO_ADMIN_PASSWORD
read -s DEMO_INVESTIGATOR_PASSWORD
export DEMO_INVESTIGATOR_PASSWORD
read -s DEMO_VIEWER_PASSWORD
export DEMO_VIEWER_PASSWORD
~~~

Start Ollama and run the API:

~~~bash
ollama pull llama3.2:3b
uvicorn main:app --app-dir examples/fastapi_agent_api --host 127.0.0.1 --port 8000
~~~

### Obtain a token

For this local demo only, the token endpoint accepts form fields:

~~~bash
curl -X POST http://127.0.0.1:8000/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=investigator' \
  --data-urlencode 'password=YOUR_INVESTIGATOR_PASSWORD'
~~~

Copy the returned `access_token`.

### Start an authorized investigation

~~~bash
curl -X POST http://127.0.0.1:8000/v1/investigations \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    "service": "checkout-api",
    "incident": "Checkout requests are timing out",
    "task": "Inspect logs, latency, and service health"
  }'
~~~

Try `orders-api` with the investigator token. It should be rejected because that service is not assigned to this user.

## 12. Run tests without Ollama or MCP

~~~bash
PYTHONPATH=examples/fastapi_agent_api python -m pytest -q examples/fastapi_agent_api/tests
~~~

Tests cover:
- Missing authentication.
- Successful investigator login and invocation.
- Wrong password.
- Viewer denied run scope.
- Investigator denied unassigned service.
- Rate limiting and `Retry-After`.
- Existing correlation ID behavior and partial results.

## 13. Security exercises

1. Replace demo users with a PostgreSQL user repository.
2. Integrate an OIDC provider and validate issuer/audience/JWKS.
3. Add token revocation or a user token-version check.
4. Add tenant and environment claims, then enforce them at every data access.
5. Add a Redis-backed rate limiter shared across replicas.
6. Add a separate human-approved workflow for write-capable MCP tools.
7. Add a security audit event for every tool call and denied authorization.
8. Add tests for expired, tampered, wrong-issuer, and wrong-audience JWTs.
9. Simulate a prompt injection inside log output and verify that the tool boundary still blocks cross-service access.

## 14. Knowledge check

1. What is the difference between authentication and authorization?
2. Why is a JWT signed but not encrypted?
3. Why does a valid investigator token still need a service-level authorization check?
4. Why is a system prompt not an authorization boundary?
5. Why should MCP tool arguments be checked after the model proposes them?
6. Why is an in-memory rate limiter insufficient for multiple workers?
7. Which authentication flow should a real browser application generally use instead of a custom username/password token endpoint?

## Completion criteria

You can explain the identity-to-tool authorization path, run the secured API, demonstrate 401/403/429 responses, constrain a caller to assigned services, and explain why model instructions are not security controls.

## References

- [FastAPI OAuth2 and JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [FastAPI security first steps](https://fastapi.tiangolo.com/tutorial/security/first-steps/)
- [RFC 9700 — OAuth 2.0 Security Best Current Practice](https://www.rfc-editor.org/rfc/rfc9700.html)
- [OWASP API Security Top 10](https://devguide.owasp.org/en/07-training-education/07-api-top-ten/)
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications)
- [OWASP prompt injection](https://genai.owasp.org/glossary/prompt-injection/)
