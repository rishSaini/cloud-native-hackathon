"""Group solver: who sits together at a break (owner: Karthik, K3).

The solver decides who sits together. Kubernetes decides where.
Interfaces are fixed by docs/tasks/karthik.md, "Python interfaces".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SolverPerson:
    id: str
    needs: frozenset[str]  # opaque capability codes the table must have
    blocked: frozenset[str]  # attendee ids never to group with
    met: frozenset[str]  # attendee ids already met (repeat penalty)


@dataclass(frozen=True)
class SolverTable:
    id: str  # table Node name, e.g. "brk-tue-1530-tbl-quiet-window"
    seats: int
    caps: frozenset[str]


@dataclass
class Group:
    id: str  # "g-<8 hex>"
    table_id: str
    members: list[str]


@dataclass
class SolverResult:
    groups: list[Group]
    unplaced: list[str]
    duration_ms: int


def solve(
    people: list[SolverPerson],
    tables: list[SolverTable],
    similarity: dict[tuple[str, str], float],
    min_size: int = 2,
    max_size: int = 4,
    time_limit_ms: int = 5000,
) -> SolverResult:
    raise NotImplementedError("K3")
