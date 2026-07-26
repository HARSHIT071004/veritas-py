from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    output_schema: dict = field(default_factory=lambda: {"type": "object"})


class Tool(ABC):
    spec: ToolSpec

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        ...
