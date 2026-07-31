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

## Error Semantics

- Raise `ModelProviderConfigurationError` for missing credentials or invalid adapter configuration.
- Raise `ModelProviderExecutionError` for transport, rate-limit, SDK, or response translation failures.
- Preserve the vendor exception as `__cause__` when wrapping failures.

## Current Boundaries

The v0.2 contract is synchronous and handles one complete response. Streaming, asynchronous calls, retries, fallback routing, structured output, and tool-call orchestration remain separate runtime concerns.