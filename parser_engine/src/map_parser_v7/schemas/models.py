from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

StepStatus = Literal["pending", "running", "done", "warning", "failed", "skipped"]


class StepRecord(BaseModel):
    id: str
    title: str
    status: StepStatus = "pending"
    duration_ms: int | None = None
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    checkpoint_output: dict[str, Any] | None = None


class PipelineResponse(BaseModel):
    job_id: str
    status: str
    current_step: str | None = None
    progress_percent: int = 0
    steps: list[StepRecord] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
