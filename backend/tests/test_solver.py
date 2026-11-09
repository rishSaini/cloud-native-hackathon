"""K3: the group solver keeps every hard constraint and leaves nobody needlessly alone."""

import random

from app.solver import SolverPerson, SolverTable, solve

QUIET = frozenset({"cap-c3"})
NONE = frozenset()


def person(pid, needs=NONE, blocked=(), met=()):
    return SolverPerson(pid, frozenset(needs), frozenset(blocked), frozenset(met))


def table(tid, seats=4, caps=NONE):
    return SolverTable(tid, seats, frozenset(caps))


def check_constraints(result, people, tables, max_size=4):
    by_id = {p.id: p for p in people}
    tables = {t.id: t for t in tables}
    seen = set()
    for g in result.groups:
        assert 2 <= len(g.members) <= min(max_size, tables[g.table_id].seats)
        for m in g.members:
            assert m not in seen
            seen.add(m)
            assert by_id[m].needs <= tables[g.table_id].caps
            for other in g.members:
                assert other not in by_id[m].blocked
    assert len({g.table_id for g in result.groups}) == len(result.groups)  # one group per table
    assert seen | set(result.unplaced) == set(by_id)


def test_two_compatible_people_are_never_alone():
    people = [person("a"), person("b")]
    result = solve(people, [table("t1")], {})
    assert [g.members for g in result.groups] == [["a", "b"]] and result.unplaced == []


def test_blocked_pair_never_sits_together():
    people = [person("a", blocked={"b"}), person("b"), person("c"), person("d")]
    result = solve(people, [table("t1"), table("t2")], {("a", "b"): 1.0})
    check_constraints(result, people, [table("t1"), table("t2")])
    assert not any({"a", "b"} <= set(g.members) for g in result.groups)


def test_needs_only_at_tables_with_the_cap():
    people = [person("q1", QUIET), person("q2", QUIET), person("x"), person("y")]
    tables = [table("plain"), table("quiet", caps=QUIET)]
    result = solve(people, tables, {})
    check_constraints(result, people, tables)
    quiet_group = next(g for g in result.groups if g.table_id == "quiet")
    assert {"q1", "q2"} <= set(quiet_group.members)


def test_size_and_seats_limits():
    people = [person(f"p{i}") for i in range(9)]
    tables = [table("t1", seats=3), table("t2", seats=3), table("t3", seats=3)]
    result = solve(people, tables, {})
    check_constraints(result, people, tables)
    assert result.unplaced == []


def test_nine_people_with_four_seat_tables_are_not_left_alone():
    people = [person(f"p{i}") for i in range(9)]
    tables = [table(f"t{i}") for i in range(4)]
    result = solve(people, tables, {})
    check_constraints(result, people, tables)
    assert result.unplaced == []  # 4+3+2 or 3+3+3, never 4+4+1


def test_similar_people_sit_together():
    people = [person(x) for x in "abcd"]
    sim = {("a", "b"): 0.9, ("c", "d"): 0.9, ("a", "c"): 0.1, ("b", "d"): 0.1}
    result = solve(people, [table("t1", seats=2), table("t2", seats=2)], sim)
    assert sorted(g.members for g in result.groups) == [["a", "b"], ["c", "d"]]


def test_repeat_penalty_prefers_new_people():
    people = [person("a", met={"b"}), person("b", met={"a"}), person("c"), person("d")]
    sim = {(x, y): 0.5 for x in "abcd" for y in "abcd" if x != y}
    result = solve(people, [table("t1", seats=2), table("t2", seats=2)], sim)
    assert not any(set(g.members) == {"a", "b"} for g in result.groups)


def test_200_people_finish_in_time_and_are_deterministic():
    rng = random.Random(7)
    people = [person(f"p{i:03d}", QUIET if i % 10 == 0 else NONE,
                     blocked={f"p{(i + 1) % 200:03d}"} if i % 25 == 0 else ()) for i in range(200)]
    tables = [table(f"t{i:02d}", caps=QUIET if i < 6 else NONE) for i in range(50)]
    sim = {(f"p{i:03d}", f"p{j:03d}"): rng.random() for i in range(200) for j in rng.sample(range(200), 20) if i != j}
    first = solve(people, tables, sim, time_limit_ms=5000)
    check_constraints(first, people, tables)
    assert first.duration_ms < 6000
    assert len(first.unplaced) == 0
    second = solve(people, tables, sim, time_limit_ms=5000)
    assert [(g.table_id, g.members) for g in first.groups] == [(g.table_id, g.members) for g in second.groups]


def test_more_people_than_seats_reports_the_rest():
    people = [person(f"p{i}") for i in range(6)]
    result = solve(people, [table("t1")], {})
    check_constraints(result, people, [table("t1")])
    assert len(result.unplaced) == 2
