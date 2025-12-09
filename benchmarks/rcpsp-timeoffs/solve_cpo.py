#!/usr/bin/env python3
"""
IBM CP Optimizer Solver for RCPSP with Time-Offs

Solves 6 problem variants:
  1. no_mig_no_delay    - No Migration | No Delays
  2. mig_no_delay       - Migration | No Delays
  3. no_mig_delay_block - No Migration | Delays | Blocked
  4. mig_delay          - Migration | Delays
  5. heterogeneous      - Multi-Resource Heterogeneous Policy
  6. no_mig_delay_rel   - No Migration | Delays | Released

Usage:
    python solve_cpo.py instance.data --variant 1 --timeLimit 60
    python solve_cpo.py *.data --variant mig_no_delay --workers 8
"""

import json
import argparse
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from itertools import combinations, product

from docplex.cp.model import (
    CpoModel, CpoStepFunction, interval_var, 
    end_of, start_of, size_of, presence_of,
    end_before_start, alternative, no_overlap, span,
    forbid_extent, forbid_start, pulse, step_at, if_then,
    minimize, max as cpo_max, sum as cpo_sum
)

# Import shared config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DEFAULTS, CPO_PARAMS, CPO_LOG_LEVELS, add_common_args,
                    add_solver_args, get_solver_params)


HORIZON = 100_000

VARIANT_NAMES = {
    '1': 'no_mig_no_delay',
    '2': 'mig_no_delay', 
    '3': 'no_mig_delay_block',
    '4': 'mig_delay',
    '5': 'heterogeneous',
    '6': 'no_mig_delay_rel',
    'no_mig_no_delay': 'no_mig_no_delay',
    'mig_no_delay': 'mig_no_delay',
    'no_mig_delay_block': 'no_mig_delay_block',
    'mig_delay': 'mig_delay',
    'heterogeneous': 'heterogeneous',
    'no_mig_delay_rel': 'no_mig_delay_rel',
}


# =============================================================================
# PARSER SECTION
# =============================================================================

def next_line(f):
    """Read next non-empty, non-comment line."""
    while True:
        raw = f.readline()
        if not raw:
            return None
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        return [int(v) for v in line.split()]


def parse_instance(filepath: str) -> dict:
    """Parse RCPSP-TimeOffs instance file."""
    with open(filepath, "r") as f:
        N, K, M = next_line(f)
        TYPES = [(d[0], d[2:2+d[1]]) for d in (next_line(f) for _ in range(K))]
        UNITS = [(d[0], [(d[2+2*i], d[3+2*i]) for i in range(d[1])]) 
                 for d in (next_line(f) for _ in range(M))]
        TASKS = [(d[0], d[1], [tuple(next_line(f)[:2]) for _ in range(d[2])]) 
                 for d in (next_line(f) for _ in range(N))]
        PRECEDENCES = [tuple(next_line(f)[:2]) for _ in range(next_line(f)[0])]
    
    return {
        'N': N, 'K': K, 'M': M,
        'TASKS': TASKS,
        'TYPES': TYPES,
        'UNITS': UNITS,
        'PRECEDENCES': PRECEDENCES,
        'RES_MAP': dict(UNITS),
        'TYPE_MAP': dict(TYPES),
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_availability(unit_id, time, res_map):
    """Returns availability (0 or 100) of a unit at a specific time."""
    return next((v for t, v in reversed(res_map[unit_id]) if time >= t), 0)


def step_function(steps, horizon=HORIZON):
    """Create CpoStepFunction from [(time, value), ...] pairs."""
    f = CpoStepFunction()
    for i, (t, v) in enumerate(steps):
        end = steps[i + 1][0] if i + 1 < len(steps) else horizon
        f.set_value(t, end, v)
    return f


def prepare_types(TYPES):
    """type_id -> {name, units, capacity}"""
    return {tid: {"name": f"Type_{tid}", "units": units, "capacity": len(units)} 
            for tid, units in TYPES}


def extract_breaks(UNITS, horizon=HORIZON):
    """Extract (start, duration) pairs where unit is unavailable."""
    return {
        uid: [(t, (steps[i+1][0] if i+1 < len(steps) else horizon) - t)
              for i, (t, v) in enumerate(steps) if v == 0 
              and t < (steps[i+1][0] if i+1 < len(steps) else horizon)]
        for uid, steps in UNITS if any(v == 0 for _, v in steps)
    }


def joint_intensity(unit_ids, res_map, horizon=HORIZON):
    """CpoStepFunction: 100 only when ALL units available simultaneously."""
    if not unit_ids:
        f = CpoStepFunction()
        f.set_value(0, horizon, 100)
        return f
    
    times = sorted({0} | {t for uid in unit_ids for t, _ in res_map[uid]})
    steps = [(t, 100 if all(get_availability(u, t, res_map) for u in unit_ids) else 0)
             for t in times]
    return step_function(steps, horizon)


def build_modes(TASKS, TYPE_MAP):
    """Generate all valid unit combinations for each task."""
    result = {}
    for tid, size, reqs in TASKS:
        if not reqs or all(qty == 0 for _, qty in reqs):
            result[tid] = [()]
            continue
        combos = [list(combinations(TYPE_MAP[t], q)) if q > 0 else [()] for t, q in reqs]
        result[tid] = [tuple(sorted({r for grp in c for r in grp})) for c in product(*combos)] or [()]
    return result


def capacity_windows(reqs, TYPE_MAP, RES_MAP, horizon=HORIZON):
    """Find windows where aggregate capacity >= requirements."""
    if not reqs or all(qty == 0 for _, qty in reqs):
        return [(0, horizon)]
    
    times = sorted({0, horizon} | {t for tid, qty in reqs if qty > 0 
                                   for r in TYPE_MAP.get(tid, []) if r in RES_MAP 
                                   for t, _ in RES_MAP[r]})
    
    def feasible(t):
        return all(sum(get_availability(r, t, RES_MAP) > 0 for r in TYPE_MAP.get(tid, [])) >= qty 
                   for tid, qty in reqs if qty > 0)
    
    windows = []
    for i in range(len(times) - 1):
        if feasible(times[i]):
            if windows and windows[-1][1] == times[i]:
                windows[-1] = (windows[-1][0], times[i + 1])
            else:
                windows.append((times[i], times[i + 1]))
    return windows or [(0, horizon)]


def compute_work_windows(mode, RES_MAP, horizon=HORIZON):
    """Find intervals where ALL units in mode are available."""
    if not mode:
        return [(0, horizon)]
    times = sorted({0, horizon} | {t for r in mode if r in RES_MAP for t, _ in RES_MAP[r]})
    windows = []
    for i in range(len(times) - 1):
        if all(get_availability(r, times[i], RES_MAP) > 0 for r in mode):
            if windows and windows[-1][1] == times[i]:
                windows[-1] = (windows[-1][0], times[i + 1])
            else:
                windows.append((times[i], times[i + 1]))
    return windows or [(0, horizon)]


# =============================================================================
# MODEL BUILDERS FOR EACH VARIANT
# =============================================================================

def build_model_v1_no_mig_no_delay(data: dict, name: str) -> tuple:
    """Variant 1: No Migration | No Delays"""
    N, M = data['N'], data['M']
    TASKS, UNITS, PRECEDENCES = data['TASKS'], data['UNITS'], data['PRECEDENCES']
    TYPE_MAP, RES_MAP = data['TYPE_MAP'], data['RES_MAP']
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    # Availability functions
    res_availability = {uid: step_function(steps) for uid, steps in UNITS}
    
    # Master intervals
    T = {i: interval_var(size=size, name=f"T{i}") for i, size, _ in TASKS}
    info["nb_interval_vars"] += len(T)
    
    # Unit intervals
    O = {(i, r): interval_var(size=size, optional=True, name=f"T{i}_U{r}")
         for i, size, reqs in TASKS for type_id, qty in reqs for r in TYPE_MAP.get(type_id, [])}
    info["nb_interval_vars"] += len(O)
    
    # Objective
    mdl.add(minimize(cpo_max([end_of(T[i]) for i in T])))
    info["nb_constraints"] += 1
    
    # Precedences
    for i, j in PRECEDENCES:
        mdl.add(end_before_start(T[i], T[j]))
        info["nb_constraints"] += 1
    
    # Alternative with cardinality
    for i, size, reqs in TASKS:
        for type_id, qty in reqs:
            if qty > 0 and (candidates := TYPE_MAP.get(type_id, [])):
                mdl.add(alternative(T[i], [O[(i, r)] for r in candidates], cardinality=qty))
                info["nb_constraints"] += 1
    
    # NoOverlap per unit
    for r in range(M):
        intervals = [itv for (i, uid), itv in O.items() if uid == r]
        if intervals:
            mdl.add(no_overlap(intervals))
            info["nb_constraints"] += 1
    
    # Calendar compliance
    for (i, r), itv in O.items():
        if r in res_availability:
            mdl.add(forbid_extent(itv, res_availability[r]))
            info["nb_constraints"] += 1
    
    return mdl, info, {'T': T, 'O': O}


def build_model_v2_mig_no_delay(data: dict, name: str) -> tuple:
    """Variant 2: Migration | No Delays"""
    N = data['N']
    TASKS, TYPES, PRECEDENCES = data['TASKS'], data['TYPES'], data['PRECEDENCES']
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    res_types = prepare_types(TYPES)
    res_breaks = extract_breaks(data['UNITS'])
    
    # Capacity functions
    A = {type_id: step_at(0, rtype["capacity"]) - cpo_sum([
        pulse((s, s+d), 1) for u in rtype["units"] if u in res_breaks for s, d in res_breaks[u]])
        for type_id, rtype in res_types.items()}
    
    # Master intervals
    T = {i: interval_var(size=size, name=f"T{i}") for i, size, _ in TASKS}
    info["nb_interval_vars"] += len(T)
    
    # Objective
    mdl.add(minimize(cpo_max([end_of(T[i]) for i in range(N)])))
    info["nb_constraints"] += 1
    
    # Precedences
    for i, j in PRECEDENCES:
        mdl.add(end_before_start(T[i], T[j]))
        info["nb_constraints"] += 1
    
    # Capacity constraints
    for type_id in res_types:
        usage = cpo_sum([pulse(T[i], qty) for i, _, reqs in TASKS 
                        for req_type, qty in reqs if req_type == type_id and qty > 0])
        mdl.add(A[type_id] - usage >= 0)
        info["nb_constraints"] += 1
    
    return mdl, info, {'T': T}


def build_model_v3_no_mig_delay_block(data: dict, name: str) -> tuple:
    """Variant 3: No Migration | Delays | Blocked"""
    N, M = data['N'], data['M']
    TASKS, PRECEDENCES = data['TASKS'], data['PRECEDENCES']
    TYPE_MAP, RES_MAP = data['TYPE_MAP'], data['RES_MAP']
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    task_modes = build_modes(TASKS, TYPE_MAP)
    
    # Joint intensity functions
    joint_intensities = {(i, m): joint_intensity(m, RES_MAP) 
                        for i in task_modes for m in task_modes[i]}
    
    # Master intervals
    T = {i: interval_var(name=f"T{i}") for i, _, _ in TASKS}
    info["nb_interval_vars"] += len(T)
    
    # Mode intervals with intensity
    O = {(i, m): interval_var(size=size, intensity=joint_intensities[(i, m)],
                              optional=True, name=f"T{i}_M{m}")
         for i, size, _ in TASKS for m in task_modes[i]}
    info["nb_interval_vars"] += len(O)
    
    # Objective
    mdl.add(minimize(cpo_max([end_of(T[i]) for i in range(N)])))
    info["nb_constraints"] += 1
    
    # Precedences
    for i, j in PRECEDENCES:
        mdl.add(end_before_start(T[i], T[j]))
        info["nb_constraints"] += 1
    
    # Alternative: mode selection
    for i in T:
        modes = [O[(i, m)] for m in task_modes[i]]
        if modes:
            mdl.add(alternative(T[i], modes))
            info["nb_constraints"] += 1
    
    # NoOverlap per resource
    for r in range(M):
        intervals = [O[(i, m)] for (i, m) in O if r in m]
        if intervals:
            mdl.add(no_overlap(intervals))
            info["nb_constraints"] += 1
    
    # Forbid start during unavailability
    for (i, m), itv in O.items():
        mdl.add(forbid_start(itv, joint_intensities[(i, m)]))
        info["nb_constraints"] += 1
    
    return mdl, info, {'T': T, 'O': O, 'task_modes': task_modes}


def build_model_v4_mig_delay(data: dict, name: str) -> tuple:
    """Variant 4: Migration | Delays"""
    TASKS, TYPES, PRECEDENCES = data['TASKS'], data['TYPES'], data['PRECEDENCES']
    TYPE_MAP, RES_MAP = data['TYPE_MAP'], data['RES_MAP']
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    res_types = prepare_types(TYPES)
    res_breaks = extract_breaks(data['UNITS'])
    
    # Capacity windows per task
    task_windows = {i: capacity_windows(reqs, TYPE_MAP, RES_MAP) for i, _, reqs in TASKS}
    
    # Master intervals
    T = {i: interval_var(name=f"T{i}") for i, _, _ in TASKS}
    info["nb_interval_vars"] += len(T)
    
    # Segment intervals
    S = {(i, w): interval_var(optional=True, start=(s, e-1), end=(s+1, e), name=f"T{i}_seg{w}")
         for i in task_windows for w, (s, e) in enumerate(task_windows[i])}
    info["nb_interval_vars"] += len(S)
    
    # Capacity functions
    A = {k: step_at(0, rt["capacity"]) - cpo_sum([
        pulse((s, s+d), 1) for u in rt["units"] if u in res_breaks for s, d in res_breaks[u]])
        for k, rt in res_types.items()}
    
    # Objective
    mdl.add(minimize(cpo_max([end_of(T[i]) for i in T])))
    info["nb_constraints"] += 1
    
    # Precedences
    for i, j in PRECEDENCES:
        mdl.add(end_before_start(T[i], T[j]))
        info["nb_constraints"] += 1
    
    # Span
    for i, _, _ in TASKS:
        segs = [S[(i, w)] for w in range(len(task_windows[i]))]
        if segs:
            mdl.add(span(T[i], segs))
            info["nb_constraints"] += 1
    
    # Work content
    for i, size, _ in TASKS:
        if size > 0:
            mdl.add(cpo_sum([size_of(S[(i, w)], 0) for w in range(len(task_windows[i]))]) == size)
            info["nb_constraints"] += 1
    
    # Capacity
    for k in res_types:
        pulses = [pulse(S[(i, w)], q) for i, _, reqs in TASKS 
                  for rk, q in reqs if q > 0 and rk == k 
                  for w in range(len(task_windows[i]))]
        if pulses:
            mdl.add(A[k] - cpo_sum(pulses) >= 0)
            info["nb_constraints"] += 1
    
    return mdl, info, {'T': T, 'S': S, 'task_windows': task_windows}


def build_model_v5_heterogeneous(data: dict, name: str, fixed_types=None, migration_types=None) -> tuple:
    """Variant 5: Multi-Resource Heterogeneous Policy"""
    N, M = data['N'], data['M']
    TASKS, TYPES, UNITS, PRECEDENCES = data['TASKS'], data['TYPES'], data['UNITS'], data['PRECEDENCES']
    TYPE_MAP = data['TYPE_MAP']
    
    # Default: first type fixed, rest migration
    if fixed_types is None:
        fixed_types = {0}
    if migration_types is None:
        migration_types = set(range(len(TYPES))) - fixed_types
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    res_types = prepare_types(TYPES)
    res_breaks = extract_breaks(UNITS)
    
    # Availability for fixed types
    res_availability = {r: step_function(steps) for r, steps in UNITS
                       if any(r in TYPE_MAP.get(k, []) for k in fixed_types)}
    
    # Master intervals
    T = {i: interval_var(size=size, name=f"T{i}") for i, size, _ in TASKS}
    info["nb_interval_vars"] += len(T)
    
    # Unit intervals for fixed types
    O = {(i, r): interval_var(size=size, optional=True, name=f"T{i}_U{r}")
         for i, size, reqs in TASKS for k, q in reqs if k in fixed_types and q > 0 
         for r in TYPE_MAP.get(k, [])}
    info["nb_interval_vars"] += len(O)
    
    # Capacity for migration types
    A = {k: step_at(0, rt["capacity"]) - cpo_sum([
        pulse((s, s+d), 1) for u in rt["units"] if u in res_breaks for s, d in res_breaks[u]])
        for k, rt in res_types.items() if k in migration_types}
    
    # Objective
    mdl.add(minimize(cpo_max([end_of(T[i]) for i in T])))
    info["nb_constraints"] += 1
    
    # Precedences
    for i, j in PRECEDENCES:
        mdl.add(end_before_start(T[i], T[j]))
        info["nb_constraints"] += 1
    
    # Alternative for fixed types
    for i, _, reqs in TASKS:
        for k, q in reqs:
            if k in fixed_types and q > 0:
                candidates = [O[(i, r)] for r in TYPE_MAP.get(k, [])]
                if candidates:
                    mdl.add(alternative(T[i], candidates, cardinality=q))
                    info["nb_constraints"] += 1
    
    # NoOverlap for fixed types
    for k in fixed_types:
        for r in TYPE_MAP.get(k, []):
            intervals = [itv for (i, uid), itv in O.items() if uid == r]
            if intervals:
                mdl.add(no_overlap(intervals))
                info["nb_constraints"] += 1
    
    # Calendar for fixed types
    for (i, r), itv in O.items():
        if r in res_availability:
            mdl.add(forbid_extent(itv, res_availability[r]))
            info["nb_constraints"] += 1
    
    # Capacity for migration types
    for k in migration_types:
        if k in A:
            pulses = [pulse(T[i], q) for i, _, reqs in TASKS for rk, q in reqs if rk == k and q > 0]
            if pulses:
                mdl.add(A[k] - cpo_sum(pulses) >= 0)
                info["nb_constraints"] += 1
    
    return mdl, info, {'T': T, 'O': O, 'fixed_types': fixed_types, 'migration_types': migration_types}


def build_model_v6_no_mig_delay_rel(data: dict, name: str) -> tuple:
    """Variant 6: No Migration | Delays | Released"""
    M = data['M']
    TASKS, PRECEDENCES = data['TASKS'], data['PRECEDENCES']
    TYPE_MAP, RES_MAP = data['TYPE_MAP'], data['RES_MAP']
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    task_modes = build_modes(TASKS, TYPE_MAP)
    work_windows = {(tid, m): compute_work_windows(m, RES_MAP) 
                   for tid in task_modes for m in task_modes[tid]}
    
    # Master intervals
    T = {i: interval_var(name=f"T{i}") for i, _, _ in TASKS}
    info["nb_interval_vars"] += len(T)
    
    # Mode intervals
    M_var = {(i, m): interval_var(optional=True, name=f"T{i}_M{m}")
             for i in task_modes for m in task_modes[i]}
    info["nb_interval_vars"] += len(M_var)
    
    # Segment intervals
    S = {(i, m, w): interval_var(optional=True, start=(ws, we-1), end=(ws+1, we), 
                                 name=f"T{i}_M{m}_seg{w}")
         for (i, m), windows in work_windows.items() for w, (ws, we) in enumerate(windows)}
    info["nb_interval_vars"] += len(S)
    
    # Objective
    mdl.add(minimize(cpo_max([end_of(T[i]) for i in T])))
    info["nb_constraints"] += 1
    
    # Precedences
    for i, j in PRECEDENCES:
        mdl.add(end_before_start(T[i], T[j]))
        info["nb_constraints"] += 1
    
    # Mode selection
    for i, _, _ in TASKS:
        modes = [M_var[(i, m)] for m in task_modes[i]]
        if modes:
            mdl.add(alternative(T[i], modes))
            info["nb_constraints"] += 1
    
    # Span: mode spans segments
    for (i, m), windows in work_windows.items():
        segs = [S[(i, m, w)] for w in range(len(windows))]
        if segs:
            mdl.add(span(M_var[(i, m)], segs))
            info["nb_constraints"] += 1
    
    # Work content
    for i, size, _ in TASKS:
        if size > 0:
            for m in task_modes[i]:
                windows = work_windows[(i, m)]
                segs = [S[(i, m, w)] for w in range(len(windows))]
                mdl.add(if_then(presence_of(M_var[(i, m)]), 
                               cpo_sum([size_of(s, 0) for s in segs]) == size))
                info["nb_constraints"] += 1
    
    # NoOverlap on segments per resource
    for r in range(M):
        segs = [S[(i, m, w)] for (i, m, w) in S if r in m]
        if segs:
            mdl.add(no_overlap(segs))
            info["nb_constraints"] += 1
    
    return mdl, info, {'T': T, 'M': M_var, 'S': S, 'task_modes': task_modes, 'work_windows': work_windows}


# =============================================================================
# MAIN BUILD DISPATCHER
# =============================================================================

def build_model(data: dict, name: str, variant: str) -> tuple:
    """Build model for specified variant."""
    variant = VARIANT_NAMES.get(variant, variant)
    
    builders = {
        'no_mig_no_delay': build_model_v1_no_mig_no_delay,
        'mig_no_delay': build_model_v2_mig_no_delay,
        'no_mig_delay_block': build_model_v3_no_mig_delay_block,
        'mig_delay': build_model_v4_mig_delay,
        'heterogeneous': build_model_v5_heterogeneous,
        'no_mig_delay_rel': build_model_v6_no_mig_delay_rel,
    }
    
    if variant not in builders:
        raise ValueError(f"Unknown variant: {variant}. Choose from: {list(builders.keys())}")
    
    return builders[variant](data, name)


# =============================================================================
# SOLVER
# =============================================================================

def solve(filepath: str, time_limit: int, workers: int, log_level: str,
          solver_params: dict, variant: str) -> dict:
    """Solve instance and return results."""
    name = Path(filepath).stem
    data = parse_instance(filepath)
    mdl, info, vars_dict = build_model(data, name, variant)
    
    params = {
        "TimeLimit": time_limit,
        "Workers": workers,
        "LogVerbosity": log_level,
        **solver_params
    }
    
    start = time.time()
    solution = mdl.solve(**params)
    duration = time.time() - start
    
    output = {
        "modelName": name,
        "variant": VARIANT_NAMES.get(variant, variant),
        "duration": duration,
        "solver": "IBM CP Optimizer",
        "objective": None,
        "lowerBound": None,
        "bestSolution": None,
        "bestSolutionTime": None,
        "bestLBTime": None,
        "proof": False,
        "nbSolutions": 0,
        "nbBranches": 0,
        "nbFails": 0,
        "nbLNSSteps": 0,
        "nbRestarts": 0,
        "memoryUsed": 0,
        "nbIntVars": info["nb_int_vars"],
        "nbIntervalVars": info["nb_interval_vars"],
        "nbConstraints": info["nb_constraints"],
        "nbWorkers": workers,
        "objectiveSense": "minimize",
        "solveDate": datetime.now().isoformat() + "Z",
        "parameters": params,
        "objectiveHistory": [],
        "lowerBoundHistory": [],
    }
    
    if solution:
        status = solution.get_solve_status()
        obj = solution.get_objective_values()
        solver_info = solution.get_solver_infos()
        
        if obj:
            output["objective"] = int(obj[0])
            output["bestSolution"] = int(obj[0])
            output["nbSolutions"] = 1
            
            if solver_info:
                output["nbBranches"] = solver_info.get('NumberOfBranches', 0)
                output["nbFails"] = solver_info.get('NumberOfFails', 0)
                output["nbRestarts"] = solver_info.get('NumberOfRestarts', 0)
                output["memoryUsed"] = solver_info.get('MemoryUsage', 0)
                output["bestSolutionTime"] = solver_info.get('SolveTime', duration)
                output["nbSolutions"] = solver_info.get('NumberOfSolutions', 1) or 1
            else:
                output["bestSolutionTime"] = duration
            
            output["objectiveHistory"].append({
                "objective": output["objective"],
                "solveTime": output["bestSolutionTime"]
            })
        
        if status == 'Optimal':
            output["proof"] = True
            output["lowerBound"] = output["objective"]
            output["bestLBTime"] = output["bestSolutionTime"]
            output["lowerBoundHistory"].append({
                "value": output["objective"],
                "solveTime": output["bestLBTime"]
            })
        elif status == 'Feasible' and solver_info:
            lb = solver_info.get('BestBound')
            if lb is not None:
                output["lowerBound"] = int(lb)
                output["lowerBoundHistory"].append({
                    "value": int(lb),
                    "solveTime": duration
                })
    
    return output


def main():
    parser = argparse.ArgumentParser(description='Solve RCPSP-TimeOffs with IBM CP Optimizer')
    add_common_args(parser)
    add_solver_args(parser, CPO_PARAMS)
    parser.add_argument('--variant', type=str, default='1',
                       help='Problem variant: 1-6 or name (no_mig_no_delay, mig_no_delay, etc.)')
    args = parser.parse_args()
    
    log_level = args.logLevel
    if str(log_level).isdigit():
        log_level = CPO_LOG_LEVELS.get(int(log_level), 'Quiet')
    
    solver_params = get_solver_params(args, CPO_PARAMS)
    
    results = []
    for inst in args.instances:
        print(f"Solving {inst} (variant={args.variant})...")
        try:
            r = solve(inst, args.timeLimit, args.workers, log_level, solver_params, args.variant)
            results.append(r)
            status = "Optimal" if r.get('proof') else "Feasible" if r.get('objective') else "No solution"
            print(f"  {r.get('objective', '-')} ({status}) in {r['duration']:.2f}s")
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({"modelName": Path(inst).stem, "error": str(e)})
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
