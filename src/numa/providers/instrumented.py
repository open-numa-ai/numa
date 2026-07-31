"""Structured event instrumentation for model providers."""

from uuid import uuid4

from numa.events import Event, EventBus, EventType
from numa.providers.base import ModelProvider, ModelRequest, ModelResponse


class InstrumentedModelProvider(ModelProvider):
    """Decorate a model provider with structured lifecycle events."""

    def __init__(self, provider: ModelProvider, event_bus: EventBus) -> None:
        self._provider = provider
        self._event_bus = event_bus

    @property
    def name(self) -> str:
        return self._provider.name

    def generate(self, request: ModelRequest) -> ModelResponse:
        execution_id = request.metadata.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id:
            execution_id = str(uuid4())

        self._event_bus.emit(
            Event(
                type=EventType.PROVIDER_STARTED,
                execution_id=execution_id,
                component_name=self.name,
                metadata={"model": request.model},
            )
        )
        try:
            response = self._provider.generate(request)
        except Exception as exc:
            self._event_bus.emit(
                Event(
                    type=EventType.PROVIDER_FAILED,
                    execution_id=execution_id,
                    component_name=self.name,
                    metadata={"error_type": type(exc).__name__, "model": request.model},
                )
            )
            raise

        self._event_bus.emit(
            Event(
                type=EventType.PROVIDER_COMPLETED,
                execution_id=execution_id,
                component_name=self.name,
                metadata={"model": response.model},
            )
        )
        return response