"""Pydantic schemas — every payload crossing the border is validated here.

`extra="forbid"` is deliberate: a renamed or misspelled field fails loudly at
the boundary instead of silently vanishing from the dashboard.
"""

from pydantic import BaseModel, ConfigDict, Field


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    priority: str = Field(pattern=r"^P[1-3]$")
    done: bool = False
    due: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    project: str | None = Field(default=None, max_length=100)


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    status: str = Field(pattern=r"^(active|paused|done)$")
    next_action: str | None = Field(default=None, max_length=300)


class OsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str = Field(max_length=40)  # ISO 8601, set by the sync client
    source: str = Field(min_length=1, max_length=100)
    tasks: list[Task] = Field(max_length=200)
    projects: list[Project] = Field(max_length=50)
    brief_note: str | None = Field(default=None, max_length=2000)
