"""Solver inputs for a break (contract, owner: Rishabh). R0 stub, implemented in R10."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Karthik's module; never import it at startup.
    from app.solver import SolverPerson


def load_break_people(break_id: str) -> list[SolverPerson]:
    """Everyone who RSVPed to `break_id`, as solver inputs."""
    raise NotImplementedError("load_break_people lands in R10")
