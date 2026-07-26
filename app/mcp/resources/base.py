from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ResourceSpec:
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


class Resource(ABC):
    spec: ResourceSpec

    @abstractmethod
    async def read(self, uri_params: Optional[dict] = None) -> Any:
        ...

    @abstractmethod
    async def write(self, data: Any, uri_params: Optional[dict] = None) -> bool:
        ...
