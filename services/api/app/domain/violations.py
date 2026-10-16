"""Typed constraint violations with stable constraint identifiers.

Constraint id grammar (cited by the UI and by the agent):
  prec:<from>-><to>        precedence edge
  release:<task>           earliest start
  deadline:<task>          hard latest finish
  skill:<task>:<req>       requirement skill
  overlap:<resource>       resource capacity (no double booking)
  avail:<resource>         resource availability / unavailability windows
  standby:<resource>       standby resource activation rule
  duration:<task>          compression bounds
  optional:<task>          deferral permission
  plan:<task>              plan completeness
  patch[:...]              malformed intervention patch
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Violation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    constraint_id: str
    message: str
    task_id: str | None = None
    resource_id: str | None = None

    @classmethod
    def of(
        cls,
        code: str,
        constraint_id: str,
        message: str,
        *,
        task_id: str | None = None,
        resource_id: str | None = None,
    ) -> Violation:
        return cls(code=code, constraint_id=constraint_id, message=message, task_id=task_id, resource_id=resource_id)
