#!/usr/bin/env python3
"""
Self-contained script to solve RCPSP-AS ASLIB instances using IBM CP Optimizer,
OptalCP, or OR-Tools CP-SAT.

Supports three solvers and two formulations:
  - cpo + simplified      IBM CP Optimizer with selection-propagation formulation
  - cpo + original        IBM CP Optimizer with branch-membership formulation
  - optalcp + simplified  OptalCP with selection-propagation formulation
  - optalcp + original    OptalCP with branch-membership formulation
  - cpsat + simplified    OR-Tools CP-SAT with selection-propagation formulation
  - cpsat + original      OR-Tools CP-SAT with branch-membership formulation

Tuned for finding good solutions fast (not proving optimality).
All instance parsing logic is inlined — no external ascp dependency needed.

Usage:
    # Solve with CPO simplified (default):
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0

    # Solve with OptalCP simplified:
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 --solver optalcp

    # Solve with OptalCP original formulation:
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 --solver optalcp -f original

    # Solve with OR-Tools CP-SAT:
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 --solver cpsat

    # Solve a slice (for splitting across cluster nodes):
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB2 --start 0 --end 1000

    # Solve specific files:
    python solve_rcpspas_aslib.py instance1a.RCP instance2a.RCP

    # 16 workers, 5 min per instance, save results:
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 -w 16 -t 300 -o results.csv

    # Resume an interrupted run:
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 -o results.csv --resume
"""

import argparse
import csv
import re
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# =============================================================================
# Instance data structures
# =============================================================================

@dataclass
class AlternativeStructureParams:
    flex: float
    nested: float
    linked: float


@dataclass
class Activity:
    id: int
    duration: int
    successors: set[int]
    branches: set[int]
    requirements: list[int]


@dataclass
class RawSubgraph:
    id: int
    branches: set[int]


@dataclass
class Subgraph(RawSubgraph):
    principal_activity: int


@dataclass(kw_only=True)
class _InstanceBase:
    resources: list[int]
    activities: list[Activity]
    name: str


@dataclass(kw_only=True)
class RawInstance(_InstanceBase):
    subgraphs: list[RawSubgraph]


@dataclass(kw_only=True)
class Instance(_InstanceBase):
    subgraphs: list[Subgraph]


@dataclass(kw_only=True)
class AslibInstance(Instance):
    params: AlternativeStructureParams
    file_a: str | None = None
    file_b: str | None = None


# =============================================================================
# File path helpers
# =============================================================================

def _other_file_path(path: str, suffix: str) -> str:
    result = re.sub(r"a\.(RCP|rcp)$", rf"{suffix}.\1", str(path), count=1)
    if result == str(path):
        raise ValueError(f"Cannot find companion file '{suffix}' for: {path}")
    return result


def _file_a_to_name(file_a: str) -> str:
    m = re.match(r"(.*)a\.rcp", Path(file_a).name, flags=re.IGNORECASE)
    assert m, f"Couldn't parse instance name from: {file_a}"
    return m.group(1)


# =============================================================================
# Instance parsing
# =============================================================================

def _read_file(file_path: str):
    def lines():
        with open(file_path, "r") as f:
            for line in map(str.strip, f):
                if line:
                    yield line
    it = lines()
    return lambda: next(it)


def _nums(line: str, to_num=int):
    return list(map(to_num, line.split()))


def _parse_subgraph(sg_id: int, line: str) -> RawSubgraph:
    [count, *branches] = _nums(line)
    assert count == len(branches)
    return RawSubgraph(sg_id, {b - 1 for b in branches})


def _parse_activity(act_id: int, n_res: int, line_a: str, line_b: str) -> Activity:
    ints_a = _nums(line_a)
    ints_b = _nums(line_b)
    duration = ints_a[0]
    resources = ints_a[1:1 + n_res]
    rest = ints_a[1 + n_res:]
    n_succ = rest[0]
    successors = rest[1:]
    assert n_succ == len(successors)
    n_branches = ints_b[0]
    branches = ints_b[1:]
    assert n_branches == len(branches)
    return Activity(
        id=act_id, duration=duration,
        successors={s - 1 for s in successors},
        branches={b - 1 for b in branches},
        requirements=resources,
    )


def _verify_topsort_and_sink(activities: list[Activity], check_sink: bool = True):
    reverse_adj: list[list[int]] = [[] for _ in activities]
    for act in activities:
        for s in act.successors:
            assert s > act.id, f"Not topologically ordered: {act.id} -> {s}"
            reverse_adj[s].append(act.id)
    if not check_sink:
        return
    sink = activities[-1].id
    queue = deque([sink])
    seen = {sink}
    while queue:
        a = queue.popleft()
        for nb in reverse_adj[a]:
            if nb not in seen:
                seen.add(nb)
                queue.append(nb)
    assert seen == {a.id for a in activities}, "Not all activities reachable from sink"
    assert activities[sink].branches == {0}


def _load_raw_instance(read_a, read_b, name: str,
                       check_sink: bool = True) -> RawInstance:
    [n_activities, n_resources] = _nums(read_a())
    resources = _nums(read_a())
    assert n_resources == len(resources)
    [n_subgraphs] = _nums(read_b())
    subgraphs = [_parse_subgraph(i, read_b()) for i in range(n_subgraphs)]
    total_branches = sum(len(sg.branches) for sg in subgraphs)
    all_branches = set().union(*(sg.branches for sg in subgraphs)) if subgraphs else set()
    assert set(range(1, total_branches + 1)) == all_branches
    activities = [
        _parse_activity(i, n_resources, read_a(), read_b())
        for i in range(n_activities)
    ]
    _verify_topsort_and_sink(activities, check_sink)
    return RawInstance(
        activities=activities, resources=resources,
        subgraphs=subgraphs, name=name,
    )


def _all_disjoint(*sets):
    seen = set()
    for s in sets:
        if s & seen:
            return False
        seen |= s
    return True


def _reconstruct_instance(raw: RawInstance) -> Instance:
    branching: list[int | None] = [None] * len(raw.subgraphs)
    for act in raw.activities:
        succ_branchsets = [raw.activities[s].branches for s in act.successors]
        if not all(len(bs) == 1 for bs in succ_branchsets):
            continue
        if not _all_disjoint(*succ_branchsets):
            continue
        union = set().union(*succ_branchsets) if succ_branchsets else set()
        for i, sg in enumerate(raw.subgraphs):
            if sg.branches == union:
                assert branching[i] is None, \
                    f"Subgraph {i} has multiple branching activities"
                branching[i] = act.id
                break
    for i, ba in enumerate(branching):
        assert ba is not None, f"Subgraph {i} has no branching activity"
    return Instance(
        resources=raw.resources, activities=raw.activities, name=raw.name,
        subgraphs=[
            Subgraph(id=sg.id, branches=sg.branches, principal_activity=branching[sg.id])
            for sg in raw.subgraphs
        ],
    )


def load_instance(file_a: str) -> AslibInstance:
    file_b = _other_file_path(file_a, "b")
    read_a = _read_file(file_a)
    read_b = _read_file(file_b)
    name = _file_a_to_name(file_a)
    [flex, nest, link] = _nums(read_b(), float)
    params = AlternativeStructureParams(flex, nest, link)
    raw = _load_raw_instance(read_a, read_b, name)
    instance = _reconstruct_instance(raw)
    return AslibInstance(
        resources=instance.resources, activities=instance.activities,
        subgraphs=instance.subgraphs, name=instance.name,
        params=params, file_a=file_a, file_b=file_b,
    )


# =============================================================================
# Branch membership map (needed for original formulation)
# =============================================================================

def _build_branch_map(instance: Instance) -> dict[int, int]:
    """Build M: branch_id -> branching_activity_id.

    Maps each branch ID to the activity that starts that branch.
    Branch 0 (dummy) maps to activity 0 (source).
    """
    act_dict = {act.id: act for act in instance.activities}
    M = {
        branch_id: b_k_act_id
        for sub in instance.subgraphs if sub.principal_activity in act_dict
        for b_k_act_id in act_dict[sub.principal_activity].successors
        if b_k_act_id in act_dict
        for branch_id in act_dict[b_k_act_id].branches.intersection(sub.branches)
        if branch_id != 0
    }
    M[0] = 0  # dummy branch -> source activity
    return M


# =============================================================================
# IBM CP Optimizer models
# =============================================================================

def create_model_cpo_simplified(instance: Instance):
    """CPO model — simplified formulation (selection propagation via A_prop)."""
    from docplex.cp.model import CpoModel

    act_dict = {act.id: act for act in instance.activities}
    branching_arcs = {
        (sub.principal_activity, s)
        for sub in instance.subgraphs if sub.principal_activity in act_dict
        for s in act_dict[sub.principal_activity].successors if s in act_dict
    }
    mdl = CpoModel(name=instance.name)

    # (7) Optional interval variable per activity
    x = {i: mdl.interval_var(name=f"T_{i}", optional=True, size=act.duration)
         for i, act in act_dict.items()}

    # (1) Minimize makespan
    mdl.add(mdl.minimize(mdl.end_of(x[len(instance.activities) - 1])))

    # (2) Source activity is present
    mdl.add(mdl.presence_of(x[0]) == 1)

    # (3) Selection propagation along non-branching arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x and (act.id, j) not in branching_arcs:
                mdl.add(mdl.presence_of(x[act.id]) <= mdl.presence_of(x[j]))

    # (4) Branch selection for each subgraph
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            succs = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if succs:
                mdl.add(mdl.sum(mdl.presence_of(x[s]) for s in succs) ==
                        mdl.presence_of(x[sub.principal_activity]))

    # (5) Precedence timing for all arcs
    mdl.add(
        mdl.if_then(
            mdl.presence_of(x[act.id]) & mdl.presence_of(x[j]),
            mdl.end_of(x[act.id]) <= mdl.start_of(x[j]),
        )
        for act in instance.activities
        for j in act.successors if j in x
    )

    # (6) Resource capacity constraints
    mdl.add(
        mdl.sum(
            mdl.pulse(x[act.id], act.requirements[v])
            for act in instance.activities if act.requirements[v] > 0
        ) <= capacity
        for v, capacity in enumerate(instance.resources) if capacity > 0
    )

    return mdl


def create_model_cpo_original(instance: Instance):
    """CPO model — original formulation (explicit activity selection via M)."""
    from docplex.cp.model import CpoModel

    act_dict = {act.id: act for act in instance.activities}
    M = _build_branch_map(instance)
    mdl = CpoModel(name=instance.name)

    # (7) Optional interval variable per activity
    x = {i: mdl.interval_var(name=f"T_{i}", optional=True, size=act.duration)
         for i, act in act_dict.items()}

    # (1) Minimize makespan
    mdl.add(mdl.minimize(mdl.end_of(x[len(instance.activities) - 1])))

    # (2) Source activity is present
    mdl.add(mdl.presence_of(x[0]) == 1)

    # (3) Precedence relations for all arcs
    mdl.add(
        mdl.if_then(
            mdl.presence_of(x[act.id]) & mdl.presence_of(x[j]),
            mdl.end_of(x[act.id]) <= mdl.start_of(x[j]),
        )
        for act in instance.activities
        for j in act.successors if j in x
    )

    # (4) Subgraph branch selection
    mdl.add(
        mdl.sum(mdl.presence_of(x[s])
                for s in act_dict[sub.principal_activity].successors if s in x) ==
        mdl.presence_of(x[sub.principal_activity])
        for sub in instance.subgraphs if sub.principal_activity in act_dict
    )

    # (5) Activity selection using branch membership map M
    mdl.add(
        mdl.presence_of(x[i]) == (mdl.sum(mdl.presence_of(x[M[b_id]])
                                          for b_id in act.branches if b_id in M) > 0)
        for i, act in act_dict.items() if i != 0
    )

    # (6) Resource capacity constraints
    mdl.add(
        mdl.sum(
            mdl.pulse(x[act.id], act.requirements[v])
            for act in instance.activities if act.requirements[v] > 0
        ) <= capacity
        for v, capacity in enumerate(instance.resources) if capacity > 0
    )

    return mdl


# =============================================================================
# OptalCP models
# =============================================================================

def create_model_optalcp_simplified(instance: Instance):
    """OptalCP model — simplified formulation (selection propagation via A_prop)."""
    import optalcp as cp

    act_dict = {act.id: act for act in instance.activities}
    branching_arcs = {
        (sub.principal_activity, s)
        for sub in instance.subgraphs if sub.principal_activity in act_dict
        for s in act_dict[sub.principal_activity].successors if s in act_dict
    }
    mdl = cp.Model()

    # (7) Optional interval variable per activity
    x = {i: mdl.interval_var(name=f"T_{i}", optional=True, length=act.duration)
         for i, act in act_dict.items()}

    # (1) Minimize makespan
    mdl.minimize(x[len(instance.activities) - 1].end())

    # (2) Source activity is present
    mdl.enforce(x[0].presence() == 1)

    # (3) Selection propagation along non-branching arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x and (act.id, j) not in branching_arcs:
                mdl.enforce(x[act.id].presence().implies(x[j].presence()))

    # (4) Branch selection for each subgraph
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            succs = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if succs:
                mdl.enforce(sum(x[s].presence() for s in succs) ==
                            x[sub.principal_activity].presence())

    # (5) Precedence timing for all arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                mdl.enforce((x[act.id].presence() & x[j].presence()).implies(
                    x[act.id].end() <= x[j].start()))

    # (6) Resource capacity constraints
    for v, capacity in enumerate(instance.resources):
        if capacity > 0:
            pulses = [x[act.id].pulse(height=act.requirements[v])
                      for act in instance.activities if act.requirements[v] > 0]
            if pulses:
                mdl.enforce(mdl.sum(pulses) <= capacity)

    return mdl


def create_model_optalcp_original(instance: Instance):
    """OptalCP model — original formulation (explicit activity selection via M)."""
    import optalcp as cp

    act_dict = {act.id: act for act in instance.activities}
    M = _build_branch_map(instance)
    mdl = cp.Model()

    # (7) Optional interval variable per activity
    x = {i: mdl.interval_var(name=f"T_{i}", optional=True, length=act.duration)
         for i, act in act_dict.items()}

    # (1) Minimize makespan
    mdl.minimize(x[len(instance.activities) - 1].end())

    # (2) Source activity is present
    mdl.enforce(x[0].presence() == 1)

    # (3) Precedence relations for all arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                mdl.enforce((x[act.id].presence() & x[j].presence()).implies(
                    x[act.id].end() <= x[j].start()))

    # (4) Subgraph branch selection
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            branches = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if branches:
                mdl.enforce(sum(x[s].presence() for s in branches) ==
                            x[sub.principal_activity].presence())

    # (5) Activity selection using branch membership map M
    for i, act in act_dict.items():
        if i != 0:
            branch_presences = [x[M[b_id]].presence()
                                for b_id in act.branches if b_id in M]
            if branch_presences:
                mdl.enforce(x[i].presence() == (sum(branch_presences) > 0))

    # (6) Resource capacity constraints
    for v, capacity in enumerate(instance.resources):
        if capacity > 0:
            pulses = [x[act.id].pulse(height=act.requirements[v])
                      for act in instance.activities if act.requirements[v] > 0]
            if pulses:
                mdl.enforce(mdl.sum(pulses) <= capacity)

    return mdl


# =============================================================================
# OR-Tools CP-SAT models
# =============================================================================

@dataclass
class _CpSatModel:
    """Wrapper holding CP-SAT model and objective variable for result extraction."""
    cp_model: object
    objective_var: object


def create_model_cpsat_simplified(instance: Instance):
    """CP-SAT model — simplified formulation (selection propagation via A_prop).

    Based on the ascp package model structure with explicit boolean variables
    for activity selection, optional fixed-size intervals, and add_cumulative
    for resource constraints.
    """
    from ortools.sat.python.cp_model import CpModel

    act_dict = {act.id: act for act in instance.activities}
    H = sum(act.duration for act in instance.activities)
    branching_arcs = {
        (sub.principal_activity, s)
        for sub in instance.subgraphs if sub.principal_activity in act_dict
        for s in act_dict[sub.principal_activity].successors if s in act_dict
    }

    mdl = CpModel()
    mdl.name = instance.name

    # Variables: boolean (x_i), start time (s_i), optional interval (itv_i)
    x = {}
    s = {}
    itv = {}
    for i, act in act_dict.items():
        x[i] = mdl.new_bool_var(f"x_{i}")
        s[i] = mdl.new_int_var(0, H, f"s_{i}")
        itv[i] = mdl.new_optional_fixed_size_interval_var(
            s[i], act.duration, x[i], f"itv_{i}")

    # (1) Minimize makespan
    cmax = mdl.new_int_var(0, H, "cmax")
    for i, act in act_dict.items():
        mdl.add(s[i] + act.duration <= cmax).only_enforce_if(x[i])
    mdl.minimize(cmax)

    # (2) Source activity is present
    mdl.add(x[0] == 1)

    # (3) Selection propagation along non-branching arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x and (act.id, j) not in branching_arcs:
                mdl.add_implication(x[act.id], x[j])

    # (4) Branch selection for each subgraph
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            succs = [s_id for s_id in act_dict[sub.principal_activity].successors
                     if s_id in x]
            if succs:
                mdl.add(
                    sum(x[s_id] for s_id in succs) == x[sub.principal_activity])

    # (5) Precedence timing for all arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                (mdl.add(s[act.id] + act.duration <= s[j])
                     .only_enforce_if(x[act.id], x[j]))

    # (6) Resource capacity constraints (cumulative)
    for v, capacity in enumerate(instance.resources):
        if capacity > 0:
            intervals = []
            demands = []
            for act in instance.activities:
                intervals.append(itv[act.id])
                demands.append(act.requirements[v])
            mdl.add_cumulative(intervals, demands, capacity)

    return _CpSatModel(mdl, cmax)


def create_model_cpsat_original(instance: Instance):
    """CP-SAT model — original formulation (explicit activity selection via branches).

    Mirrors the ascp.model.Model approach: explicit boolean variables for each
    branch, add_max_equality for activity selection (x_i = OR of branch vars),
    and add_cumulative for resources.
    """
    from ortools.sat.python.cp_model import CpModel

    act_dict = {act.id: act for act in instance.activities}
    H = sum(act.duration for act in instance.activities)

    mdl = CpModel()
    mdl.name = instance.name

    # Activity variables
    x = {}
    s = {}
    itv = {}
    for i, act in act_dict.items():
        x[i] = mdl.new_bool_var(f"x_{i}")
        s[i] = mdl.new_int_var(0, H, f"s_{i}")
        itv[i] = mdl.new_optional_fixed_size_interval_var(
            s[i], act.duration, x[i], f"itv_{i}")

    # Branch variables: branch 0 (root/dummy) is always True
    branch_vars = {0: mdl.new_constant(True)}
    for sub in instance.subgraphs:
        for bid in sub.branches:
            branch_vars[bid] = mdl.new_bool_var(f"branch_{bid}")

    # (1) Minimize makespan
    cmax = mdl.new_int_var(0, H, "cmax")
    for i, act in act_dict.items():
        mdl.add(s[i] + act.duration <= cmax).only_enforce_if(x[i])
    mdl.minimize(cmax)

    # (2) Source activity is present
    mdl.add(x[0] == 1)

    # (3) Precedence relations for all arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                (mdl.add(s[act.id] + act.duration <= s[j])
                     .only_enforce_if(x[act.id], x[j]))

    # (4) Subgraph branch selection
    for sub in instance.subgraphs:
        mdl.add(
            sum(branch_vars[bid] for bid in sub.branches)
            == x[sub.principal_activity])

    # (5) Activity selection: x_i = OR(branch_vars for branches of i)
    for i, act in act_dict.items():
        bvars = [branch_vars[bid] for bid in act.branches if bid in branch_vars]
        if bvars:
            mdl.add_max_equality(x[i], bvars)

    # (6) Resource capacity constraints (cumulative)
    for v, capacity in enumerate(instance.resources):
        if capacity > 0:
            intervals = []
            demands = []
            for act in instance.activities:
                intervals.append(itv[act.id])
                demands.append(act.requirements[v])
            mdl.add_cumulative(intervals, demands, capacity)

    return _CpSatModel(mdl, cmax)


# =============================================================================
# Model dispatch
# =============================================================================

SOLVER_CHOICES = ("cpo", "optalcp", "cpsat")
FORMULATION_CHOICES = ("simplified", "original")

MODEL_BUILDERS = {
    ("cpo", "simplified"): create_model_cpo_simplified,
    ("cpo", "original"): create_model_cpo_original,
    ("optalcp", "simplified"): create_model_optalcp_simplified,
    ("optalcp", "original"): create_model_optalcp_original,
    ("cpsat", "simplified"): create_model_cpsat_simplified,
    ("cpsat", "original"): create_model_cpsat_original,
}


# =============================================================================
# IBM CP Optimizer parameters — tuned for SPEED (solution finding)
# =============================================================================

LOG_VERBOSITY_MAP = {
    0: "Quiet",
    1: "Terse",
    2: "Normal",
    3: "Verbose",
}


def _get_cpo_parameters(nb_workers=16, time_limit=100, log_period=5000):
    """CP Optimizer parameters tuned for fast solution finding."""
    from docplex.cp.parameters import CpoParameters

    params = CpoParameters()
    params.Workers = nb_workers
    params.TimeLimit = time_limit
    params.LogPeriod = log_period

    # Always Normal verbosity so we can parse solution times from the log
    params.LogVerbosity = "Normal"

    # Auto search — let CPO pick the best strategy per instance
    params.SearchType = "Auto"

    # Disable FDS (it spends effort on proving bounds, not finding solutions)
    params.FailureDirectedSearch = "Off"

    # Lower inference levels — faster propagation, less time per node
    params.DefaultInferenceLevel = "Medium"
    params.CumulFunctionInferenceLevel = "Medium"
    params.PrecedenceInferenceLevel = "Medium"

    return params


# =============================================================================
# CPO log parsing
# =============================================================================

def _parse_cpo_best_solution_time(solver_log: str) -> float | None:
    """Parse the time of the last '!' solution line from CPO solver log.

    CPO logs improving solutions as lines like:
        !          123   0.42s ...
    The second token after '!' is the time. We want the last such line.
    """
    last_time = None
    for line in solver_log.splitlines():
        line = line.strip()
        if line.startswith("!") and not line.startswith("! ----") and not line.startswith("! ="):
            tokens = line.split()
            for tok in tokens[1:]:
                if tok.endswith("s"):
                    try:
                        last_time = float(tok[:-1])
                        break
                    except ValueError:
                        continue
    return last_time


# =============================================================================
# Solve with IBM CP Optimizer
# =============================================================================

def _solve_with_cpo(mdl, nb_workers, time_limit, log_verbosity, log_period,
                    solver_path):
    """Run CPO solver. Returns (cmax, state, runtime, best_solution_time)."""
    from docplex.cp.config import context as cpo_context
    from io import StringIO

    if solver_path:
        cpo_context.solver.local.execfile = str(solver_path)

    params = _get_cpo_parameters(nb_workers, time_limit, log_period)

    log_buffer = StringIO()
    if log_verbosity > 0:
        class TeeStream:
            def __init__(self, *streams):
                self.streams = streams
            def write(self, data):
                for s in self.streams:
                    s.write(data)
            def flush(self):
                for s in self.streams:
                    s.flush()
        log_output = TeeStream(sys.stdout, log_buffer)
    else:
        log_output = log_buffer

    t0 = time.monotonic()
    result = mdl.solve(params=params, log_output=log_output)
    wall_time = round(time.monotonic() - t0, 3)

    solve_status = result.get_solve_status() if result else None
    obj_values = result.get_objective_values() if result else None
    cmax = int(obj_values[0]) if obj_values else None

    if solve_status == "Optimal":
        state = "Optimal"
    elif cmax is not None:
        state = "Feasible"
    else:
        state = "NoSolution"

    best_solution_time = _parse_cpo_best_solution_time(log_buffer.getvalue())

    return cmax, state, wall_time, best_solution_time


# =============================================================================
# Solve with OptalCP
# =============================================================================

def _solve_with_optalcp(mdl, nb_workers, time_limit, log_verbosity, log_period):
    """Run OptalCP solver. Returns (cmax, state, runtime, best_solution_time)."""
    import optalcp as cp

    params = cp.Parameters()
    params["nbWorkers"] = nb_workers
    params["timeLimit"] = time_limit
    params["logLevel"] = min(log_verbosity, 2)  # OptalCP uses 0-2
    params["logPeriod"] = max(1, log_period // 1000)  # CPO uses ms, OptalCP seconds

    t0 = time.monotonic()
    result = mdl.solve(parameters=params)
    wall_time = round(time.monotonic() - t0, 3)

    cmax = None
    try:
        if result is not None and result.objective is not None:
            cmax = int(result.objective)
    except (AttributeError, TypeError):
        pass

    if result is not None and getattr(result, "proof", False):
        state = "Optimal"
    elif cmax is not None:
        state = "Feasible"
    else:
        state = "NoSolution"

    # OptalCP SolveResult.solution_time: seconds from start when best solution was found
    best_solution_time = None
    try:
        st = result.solution_time
        if st is not None:
            best_solution_time = round(st, 3)
    except (AttributeError, TypeError):
        pass

    return cmax, state, wall_time, best_solution_time


# =============================================================================
# Solve with OR-Tools CP-SAT
# =============================================================================

def _solve_with_cpsat(mdl_data, nb_workers, time_limit, log_verbosity):
    """Run CP-SAT solver. Returns (cmax, state, runtime, best_solution_time)."""
    from ortools.sat.python.cp_model import (
        CpSolver, CpSolverSolutionCallback, OPTIMAL, FEASIBLE,
    )

    solver = CpSolver()
    solver.parameters.num_workers = nb_workers
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = (log_verbosity > 0)

    # Track best solution time via callback
    best_wall_time = [None]

    class _Callback(CpSolverSolutionCallback):
        def __init__(self):
            CpSolverSolutionCallback.__init__(self)
        def on_solution_callback(self):
            best_wall_time[0] = self.wall_time

    callback = _Callback()
    t0 = time.monotonic()
    sys.stdout.flush()
    status = solver.solve(mdl_data.cp_model, callback)
    sys.stdout.flush()
    wall_time = round(time.monotonic() - t0, 3)

    if status == OPTIMAL:
        state = "Optimal"
        cmax = int(solver.objective_value)
    elif status == FEASIBLE:
        state = "Feasible"
        cmax = int(solver.objective_value)
    else:
        state = "NoSolution"
        cmax = None

    bst = round(best_wall_time[0], 3) if best_wall_time[0] is not None else None
    return cmax, state, wall_time, bst


# =============================================================================
# Solve single instance
# =============================================================================

def solve_instance(instance_path, solver="cpo", formulation="simplified",
                   nb_workers=16, time_limit=100,
                   log_verbosity=2, log_period=5000,
                   solver_path=None) -> dict:
    """Solve a single RCPSP-AS instance."""
    instance = load_instance(str(instance_path))

    build_fn = MODEL_BUILDERS[(solver, formulation)]
    mdl = build_fn(instance)

    if solver == "cpo":
        cmax, state, runtime, best_solution_time = _solve_with_cpo(
            mdl, nb_workers, time_limit, log_verbosity, log_period, solver_path)
    elif solver == "optalcp":
        cmax, state, runtime, best_solution_time = _solve_with_optalcp(
            mdl, nb_workers, time_limit, log_verbosity, log_period)
    else:  # cpsat
        cmax, state, runtime, best_solution_time = _solve_with_cpsat(
            mdl, nb_workers, time_limit, log_verbosity)

    return {
        "filename": Path(instance_path).name,
        "cmax": cmax,
        "state": state,
        "runtime": runtime,
        "best_solution_time": best_solution_time,
    }


# =============================================================================
# Instance discovery & CSV logging
# =============================================================================

def _natural_sort_key(path: Path):
    """Sort key that treats numeric parts as integers: aslib0_1, aslib0_2, ..., aslib0_10."""
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', path.name)]


def discover_instances(data_dir: Path) -> list[Path]:
    files = list(data_dir.glob("*a.RCP")) + list(data_dir.glob("*a.rcp"))
    return sorted(files, key=_natural_sort_key)


CSV_FIELDS = ["filename", "cmax", "state", "runtime", "best_solution_time"]


def load_solved_instances(csv_path: Path) -> set[str]:
    solved = set()
    if csv_path.exists():
        with open(csv_path, "r", newline="") as f:
            for row in csv.DictReader(f):
                solved.add(row["filename"])
    return solved


def init_csv(csv_path: Path, append: bool = False):
    if append and csv_path.exists():
        return
    with open(csv_path, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()


def append_result(csv_path: Path, row: dict):
    with open(csv_path, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)


# =============================================================================
# Batch runner
# =============================================================================

def run_batch(instance_files: list[Path], args) -> list[dict]:
    total = len(instance_files)
    csv_path = Path(args.output) if args.output else None

    solved_set: set[str] = set()
    if args.resume and csv_path and csv_path.exists():
        solved_set = load_solved_instances(csv_path)
        print(f"Resuming: {len(solved_set)} instances already solved, skipping.")

    if csv_path:
        init_csv(csv_path, append=args.resume)

    log_verbosity = 0 if args.quiet else args.log_verbosity
    results: list[dict] = []
    n_solved = 0
    n_optimal = 0
    n_errors = 0
    batch_start = time.monotonic()

    for idx, instance_path in enumerate(instance_files):
        instance_filename = instance_path.name

        if instance_filename in solved_set:
            continue

        n_solved += 1
        print(f"\n{'='*70}")
        print(f"[{idx+1}/{total}] {instance_filename}")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        sys.stdout.flush()

        try:
            result = solve_instance(
                instance_path,
                solver=args.solver,
                formulation=args.formulation,
                nb_workers=args.workers,
                time_limit=args.time_limit,
                log_verbosity=log_verbosity,
                log_period=args.log_period,
                solver_path=args.solver_path,
            )

            if result["state"] == "Optimal":
                n_optimal += 1

            print(f"  -> cmax={result['cmax']}  state={result['state']}  "
                  f"runtime={result['runtime']}s  "
                  f"best_solution_time={result['best_solution_time']}s")

        except Exception as e:
            result = {
                "filename": instance_filename,
                "cmax": None,
                "state": f"ERROR: {e}",
                "runtime": None,
                "best_solution_time": None,
            }
            n_errors += 1
            print(f"  -> ERROR: {e}", file=sys.stderr)

        results.append(result)
        if csv_path:
            append_result(csv_path, result)
        sys.stdout.flush()

    batch_time = time.monotonic() - batch_start
    print(f"\n{'='*70}")
    print("BATCH SUMMARY")
    print(f"{'='*70}")
    print(f"  Total:    {total}")
    print(f"  Solved:   {n_solved}")
    print(f"  Optimal:  {n_optimal}")
    print(f"  Errors:   {n_errors}")
    print(f"  Skipped:  {len(solved_set)}")
    print(f"  Time:     {batch_time:.1f}s ({batch_time/3600:.2f}h)")
    if csv_path:
        print(f"  CSV:      {csv_path}")
    print(f"{'='*70}")

    return results


# =============================================================================
# CLI
# =============================================================================

SOLVER_NAMES = {
    "cpo": "IBM CP Optimizer",
    "optalcp": "OptalCP",
    "cpsat": "OR-Tools CP-SAT",
}


def main():
    parser = argparse.ArgumentParser(
        description="Solve RCPSP-AS ASLIB instances with IBM CP Optimizer, OptalCP, or OR-Tools CP-SAT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 --start 0 --end 20 -t 10 -w 16 -o results.csv
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 --solver optalcp -f original
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 --solver cpsat
    python solve_rcpspas_aslib.py instance1a.RCP instance2a.RCP -t 60 -w 8
    python solve_rcpspas_aslib.py -d /path/to/ASLIB/ASLIB0 -o results.csv --resume
        """,
    )

    parser.add_argument("instances", nargs="*", type=Path,
                        help="Specific instance files (*a.RCP) to solve")
    parser.add_argument("--data-dir", "-d", type=Path,
                        help="Directory to discover all *a.RCP instances from")

    parser.add_argument("--solver", choices=SOLVER_CHOICES, default="cpo",
                        help="Solver: cpo (IBM CP Optimizer), optalcp, or cpsat "
                             "(OR-Tools) (default: cpo)")
    parser.add_argument("--formulation", "-f", choices=FORMULATION_CHOICES,
                        default="simplified",
                        help="Model formulation: simplified (selection propagation) "
                             "or original (branch membership) (default: simplified)")

    parser.add_argument("--start", type=int, default=0,
                        help="Start index (0-based) for instance slice (default: 0)")
    parser.add_argument("--end", type=int, default=None,
                        help="End index (exclusive) for instance slice")

    parser.add_argument("--time-limit", "-t", type=int, default=100,
                        help="Time limit per instance in seconds (default: 100)")
    parser.add_argument("--workers", "-w", type=int, default=16,
                        help="Number of workers (default: 16)")
    parser.add_argument("--log-verbosity", "-l", type=int, default=2,
                        choices=[0, 1, 2, 3],
                        help="0=Quiet 1=Terse 2=Normal 3=Verbose (default: 2)")
    parser.add_argument("--log-period", type=int, default=5000,
                        help="Log period in ms (default: 5000)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress solver output (sets log-verbosity=Quiet)")

    parser.add_argument("--solver-path", "-s", type=Path,
                        help="Path to CP Optimizer executable (cpoptimizer); CPO only")
    parser.add_argument("--output", "-o", type=Path,
                        help="Output CSV file (written incrementally)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip instances already present in the output CSV")

    args = parser.parse_args()

    if args.instances and args.data_dir:
        parser.error("Specify either positional instance files or --data-dir, not both.")
    if not args.instances and not args.data_dir:
        parser.error("Provide instance files or --data-dir.")

    if args.data_dir:
        data_dir = args.data_dir.resolve()
        if not data_dir.exists():
            print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
            sys.exit(1)
        instance_files = discover_instances(data_dir)
        if not instance_files:
            print(f"Error: No *a.RCP files found in {data_dir}", file=sys.stderr)
            sys.exit(1)
        instance_files = instance_files[args.start:args.end]
    else:
        instance_files = args.instances
        for f in instance_files:
            if not f.exists():
                print(f"Error: File not found: {f}", file=sys.stderr)
                sys.exit(1)

    solver_label = SOLVER_NAMES[args.solver]
    print(f"RCPSP-AS ASLIB Solver ({solver_label} — {args.formulation} formulation)")
    print(f"{'='*70}")
    print(f"  Instances:      {len(instance_files)}")
    if args.data_dir:
        print(f"  Data dir:       {args.data_dir.resolve()}")
        if args.start or args.end:
            print(f"  Slice:          [{args.start}:{args.end}]")
    print(f"  Solver:         {solver_label}")
    print(f"  Formulation:    {args.formulation}")
    print(f"  Time limit:     {args.time_limit}s")
    print(f"  Workers:        {args.workers}")
    print(f"  Log verbosity:  {LOG_VERBOSITY_MAP.get(0 if args.quiet else args.log_verbosity)}")
    if args.solver == "cpo":
        print(f"  Solver path:    {args.solver_path or 'default'}")
    print(f"  Output CSV:     {args.output or '(none)'}")
    print(f"  Started at:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    sys.stdout.flush()

    run_batch(instance_files, args)


if __name__ == "__main__":
    main()
