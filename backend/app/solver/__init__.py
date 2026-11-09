"""Group solver: who sits together at a break (owner: Karthik, K3).

The solver decides who sits together. Kubernetes decides where.
Interfaces are fixed by docs/tasks/karthik.md, "Python interfaces".

Algorithm (docs/AFFINITY.md, "How groups are formed"):
1. Sort people by how hard they are to place: fewest compatible tables, then most blocks.
2. Seed a group for each person not yet placed, at the free table that fits
   them with the fewest extra capabilities (special tables stay free longer).
3. Greedily add the most similar compatible people, up to the table's size.
4. Local search within the time limit: move one person or swap two, and keep
   any change that improves the objective.
5. Report everyone not in a group of at least `min_size` as unplaced.

Objective: sum of pair similarity in each group, minus a repeat penalty for
pairs who already met, minus a large penalty for each unplaced person.
Hard constraints: group size, table seats, table caps cover every member's
needs, and blocked pairs never sit together.
"""

import hashlib
import random
import time
from dataclasses import dataclass

from opentelemetry import metrics, trace

tracer = trace.get_tracer("talkscout")
meter = metrics.get_meter("talkscout")
group_size_hist = meter.create_histogram("talkscout.search.group.size", description="Sizes of groups formed")
solver_duration_hist = meter.create_histogram(
    "talkscout.search.solver.duration", unit="s", description="Group solver time"
)

REPEAT_PENALTY = 0.5
UNPLACED_PENALTY = 10.0


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


class _State:
    def __init__(self, people, tables, similarity, min_size, max_size):
        self.p = {x.id: x for x in people}
        self.t = {x.id: x for x in tables}
        self.sim = similarity
        self.min_size, self.max_size = min_size, max_size
        self.groups: dict[str, list[str]] = {}  # table id -> member ids
        self.where: dict[str, str] = {}  # person id -> table id
        self.options = {p: sum(self.fits(p, t) for t in self.t) for p in self.p}  # compatible tables

    # ---- constraints ----
    def capacity(self, table: str) -> int:
        return min(self.max_size, self.t[table].seats)

    def fits(self, person: str, table: str) -> bool:
        return self.p[person].needs <= self.t[table].caps

    def blocked(self, a: str, b: str) -> bool:
        return b in self.p[a].blocked or a in self.p[b].blocked

    def can_join(self, person: str, table: str, members: list[str]) -> bool:
        return (
            len(members) < self.capacity(table)
            and self.fits(person, table)
            and not any(self.blocked(person, m) for m in members)
        )

    # ---- objective ----
    def pair(self, a: str, b: str) -> float:
        s = self.sim.get((a, b), self.sim.get((b, a), 0.0))
        if b in self.p[a].met or a in self.p[b].met:
            s -= REPEAT_PENALTY
        return s

    def affinity(self, person: str, members) -> float:
        return sum(self.pair(person, m) for m in members if m != person)

    def group_score(self, members) -> float:
        if not members:
            return 0.0
        if len(members) < self.min_size:
            return -UNPLACED_PENALTY * len(members)
        return sum(self.pair(a, b) for i, a in enumerate(members) for b in members[i + 1:])

    def move_delta(self, person: str, target: str) -> float:
        origin = self.where.get(person)
        tgt = self.groups.get(target, [])
        delta = self.group_score(tgt + [person]) - self.group_score(tgt)
        if origin:
            org = self.groups[origin]
            delta += self.group_score([m for m in org if m != person]) - self.group_score(org)
        else:
            delta += UNPLACED_PENALTY  # an unassigned person counted as unplaced
        return delta

    def swap_delta(self, a: str, b: str) -> float:
        ta, tb = self.where[a], self.where[b]
        ga, gb = self.groups[ta], self.groups[tb]
        na = [m for m in ga if m != a] + [b]
        nb = [m for m in gb if m != b] + [a]
        return (self.group_score(na) + self.group_score(nb)) - (self.group_score(ga) + self.group_score(gb))

    def score(self) -> float:
        total = 0.0
        for members in self.groups.values():
            if len(members) >= self.min_size:
                total += sum(self.pair(a, b) for i, a in enumerate(members) for b in members[i + 1:])
            else:
                total -= UNPLACED_PENALTY * len(members)
        total -= UNPLACED_PENALTY * (len(self.p) - len(self.where))
        return total

    # ---- edits ----
    def add(self, person: str, table: str) -> None:
        self.groups.setdefault(table, []).append(person)
        self.where[person] = table

    def remove(self, person: str) -> None:
        table = self.where.pop(person)
        self.groups[table].remove(person)
        if not self.groups[table]:
            del self.groups[table]


def _hardness(st: _State, person: str):
    compatible = sum(st.fits(person, t) for t in st.t)
    return (compatible, -len(st.p[person].blocked), person)


def _greedy(st: _State) -> None:
    order = sorted(st.p, key=lambda x: _hardness(st, x))
    for person in order:
        if person in st.where:
            continue
        free = [t for t in st.t if t not in st.groups and st.fits(person, t) and st.capacity(t) >= st.min_size]
        if not free:
            continue
        table = min(free, key=lambda t: (len(st.t[t].caps - st.p[person].needs), -st.t[t].seats, t))
        st.add(person, table)
        while len(st.groups[table]) < st.capacity(table):
            candidates = [q for q in order if q not in st.where and st.can_join(q, table, st.groups[table])]
            if not candidates:
                break
            # Fewest other options first, so a quiet table goes to people who need quiet.
            best = max(candidates, key=lambda q: (-st.options[q], st.affinity(q, st.groups[table]), -order.index(q)))
            st.add(best, table)
    # Anyone left joins an existing group with space, where they fit best.
    for person in order:
        if person in st.where:
            continue
        options = [t for t, members in st.groups.items() if st.can_join(person, t, members)]
        if options:
            st.add(person, max(options, key=lambda t: (st.affinity(person, st.groups[t]), t)))


def _local_search(st: _State, rng: random.Random, deadline: float, max_rounds: int = 200) -> None:
    for _ in range(max_rounds):
        improved = False
        people = sorted(st.p)
        rng.shuffle(people)
        for person in people:
            if time.monotonic() > deadline:
                return
            # Move: to another table (used or free) where the person may sit.
            origin = st.where.get(person)
            best, best_delta = None, 1e-9
            for target in st.t:
                if target != origin and st.can_join(person, target, st.groups.get(target, [])):
                    d = st.move_delta(person, target)
                    if d > best_delta:
                        best, best_delta = target, d
            if best:
                if origin:
                    st.remove(person)
                st.add(person, best)
                improved = True
                continue
            # Swap: with a person at another table, if both fit and nobody is blocked.
            if not origin:
                continue
            for other in people:
                o_table = st.where.get(other)
                if not o_table or o_table == origin:
                    continue
                if not (st.fits(person, o_table) and st.fits(other, origin)):
                    continue
                a_rest = [m for m in st.groups[origin] if m != person]
                b_rest = [m for m in st.groups[o_table] if m != other]
                if any(st.blocked(person, m) for m in b_rest) or any(st.blocked(other, m) for m in a_rest):
                    continue
                if st.swap_delta(person, other) > 1e-9:
                    st.remove(person)
                    st.remove(other)
                    st.add(person, o_table)
                    st.add(other, origin)
                    improved = True
                    break
        if not improved:
            return


def _group_id(table: str, members: list[str]) -> str:
    return "g-" + hashlib.sha1(f"{table}:{','.join(sorted(members))}".encode()).hexdigest()[:8]


def solve(
    people: list[SolverPerson],
    tables: list[SolverTable],
    similarity: dict[tuple[str, str], float],
    min_size: int = 2,
    max_size: int = 4,
    time_limit_ms: int = 5000,
    seed: int = 0,
) -> SolverResult:
    start = time.monotonic()
    with tracer.start_as_current_span("talkscout.search.solver.run") as span:
        st = _State(people, tables, similarity, min_size, max_size)
        _greedy(st)
        _local_search(st, random.Random(seed), start + time_limit_ms / 1000)

        groups, unplaced = [], [p for p in sorted(st.p) if p not in st.where]
        for table in sorted(st.groups):
            members = sorted(st.groups[table])
            if len(members) >= min_size:
                groups.append(Group(id=_group_id(table, members), table_id=table, members=members))
                group_size_hist.record(len(members))
            else:
                unplaced.extend(members)
        duration_ms = int((time.monotonic() - start) * 1000)
        solver_duration_hist.record(duration_ms / 1000)
        from app.telemetry.attrs import set_attrs

        set_attrs(span, solver_duration_ms=duration_ms, group_size=len(groups))
    return SolverResult(groups=groups, unplaced=sorted(unplaced), duration_ms=duration_ms)
