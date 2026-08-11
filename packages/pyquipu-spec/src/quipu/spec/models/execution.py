from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuipuResult:
    success: bool
    exit_code: int
    message: str = ""
    data: Any = None
    error: Exception | None = None
    msg_kwargs: dict[str, Any] = field(default_factory=dict)
