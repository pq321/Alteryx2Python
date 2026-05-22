from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class ToolCertificationReport:
    tool_name: str
    maturity: str
    certification_status: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)