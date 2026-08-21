from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    UNIT_NOT_FOUND = "UNIT_NOT_FOUND"
    COMPONENT_NOT_FOUND = "COMPONENT_NOT_FOUND"
    REQUIRED_COMPONENT_MISSING = "REQUIRED_COMPONENT_MISSING"
    INCOMPATIBLE_ATTACHMENT = "INCOMPATIBLE_ATTACHMENT"
    SKELETON_MISMATCH = "SKELETON_MISMATCH"
    MISSING_SOURCE_ASSET = "MISSING_SOURCE_ASSET"
    MISSING_TEXTURE = "MISSING_TEXTURE"
    UNSUPPORTED_MATERIAL = "UNSUPPORTED_MATERIAL"
    UNRESOLVED_ANIMATION_FAMILY = "UNRESOLVED_ANIMATION_FAMILY"
    CONVERSION_NOT_IMPLEMENTED = "CONVERSION_NOT_IMPLEMENTED"


class ConverterError(RuntimeError):
    def __init__(self, code: ErrorCode, message: str, **context: Any):
        self.code = code
        self.context = context
        detail = " ".join(f"{key}={value!r}" for key, value in sorted(context.items()))
        super().__init__(f"{code.value}: {message}" + (f" ({detail})" if detail else ""))

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": str(self), "context": self.context}
