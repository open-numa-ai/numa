# Model Providers

Model Providers isolate vendor SDKs from Agent behavior. Numa defines the synchronous request and response contract but does not bundle network providers in the core package.

## Contracts

- `ModelRequest` contains an immutable message sequence, optional model name, provider parameters, and application metadata.
- `ModelResponse` contains an assistant `Message`, resolved model name, optional `ModelUsage`, and provider metadata.
- `ModelProvider` exposes a stable `name` and synchronous `generate()` method.
- `ModelUsage` records input and output tokens when the vendor reports them.

## Implement an Adapter

An optional provider package translates between Numa and its vendor SDK at one boundary:

```python
from numa import Message, MessageRole, ModelRequest, ModelResponse
from numa.providers import ModelProvider, ModelProviderExecutionError


class VendorProvider(ModelProvider):
    def __init__(self, client: object) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "vendor"

    def generate(self, request: ModelRequest) -> ModelResponse:
        try:
            # Translate request.messages and request.parameters for the SDK.
            content = "response from vendor"
        except Exception as exc:
            raise ModelProviderExecutionError("Vendor request failed") from exc

        return ModelResponse(
            message=Message(role=MessageRole.ASSISTANT, content=content),
            model=request.model,
        )
```

Keep API keys and SDK clients inside the adapter or application composition root. Do not put credentials in `ModelRequest.metadata`.

## Reference Agent

`LLMAgent` is a small synchronous reference implementation that shows how to compose an `Agent`
with any `ModelProvider`:

```python
from numa import AgentRuntime, Task
from numa.agents import LLMAgent
from numa.providers import EchoModelProvider

agent = LLMAgent(
    EchoModelProvider(),
    system_prompt="Answer concisely.",
    model="echo",
    parameters={"temperature": 0},
)
result = AgentRuntime().run(agent, Task(description="Hello"))
```

For each run, the Agent sends messages in this order:

1. The configured system prompt, when present.
2. The existing `Context.messages` in their original order.
3. A user message containing the current `Task.description`.

The request metadata includes `execution_id=task.id`, which lets an
`InstrumentedModelProvider` correlate Provider events with the surrounding Agent lifecycle. The
Agent does not modify the input Context; `AgentRuntime` appends the returned assistant message after
the Agent completes.

This implementation performs exactly one synchronous Provider call. Applications remain
responsible for prompt templates, history selection, structured outputs, Tool loops, retries, and
vendor-specific configuration. Use a custom `Agent` when those policies differ.

## Error Semantics

- Raise `ModelProviderConfigurationError` for missing credentials or invalid adapter configuration.
- Raise `ModelProviderExecutionError` for transport, rate-limit, SDK, or response translation failures.
- Preserve the vendor exception as `__cause__` when wrapping failures.

## Current Boundaries

The Provider contract and reference Agent are synchronous and handle one complete response.
Streaming, asynchronous calls, retries, fallback routing, structured output, and tool-call
orchestration remain separate concerns.
