#!/usr/bin/env python3
"""
OptalCP Solver for RCPSP with Time-Offs

Solves 6 problem variants:
  1. no_mig_no_delay    - No Migration | No Delays
  2. mig_no_delay       - Migration | No Delays
  3. no_mig_delay_block - No Migration | Delays | Blocked
  4. mig_delay          - Migration | Delays
  5. heterogeneous      - Multi-Resource Heterogeneous Policy
  6. no_mig_delay_rel   - No Migration | Delays | Released

Usage:
    python solve_optal.py instance.data --variant 1 --timeLimit 60
    python solve_optal.py *.data --variant mig_no_delay --workers 8
"""

import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
from itertools import combinations, product

import optalcp as cp

# Import shared config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DEFAULTS, OPTAL_PARAMS, add_common_args,
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


def joint_intensity_steps(unit_ids, res_map, horizon=HORIZON):
    """Returns [(time, value), ...] where value=1 when ALL units available, else 0."""
    if not unit_ids:
        return [(0, 1)]
    times = sorted({0} | {t for uid in unit_ids if uid in res_map for t, _ in res_map[uid]})
    if not times:
        return [(0, 1)]
    return [(t, 1 if all(get_availability(u, t, res_map) > 0 for u in unit_ids) else 0) for t in times]


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
    TYPE_MAP = data['TYPE_MAP']
    
    mdl = cp.Model(name=name)
    
    # Availability functions
    res_availability = {uid: mdl.step_function(steps) for uid, steps in UNITS}
    
    # Master intervals
    T = {i: mdl.interval_var(length=size, name=f"T{i}") for i, size, _ in TASKS}
    
    # Unit intervals
    O = {(i, r): mdl.interval_var(length=size, optional=True, name=f"T{i}_U{r}")
         for i, size, reqs in TASKS for type_id, qty in reqs for r in TYPE_MAP.get(type_id, [])}
    
    # Objective
    mdl.minimize(mdl.max([T[i].end() for i in T]))
    
    # Precedences
    mdl.add([T[i].end_before_start(T[j]) for i, j in PRECEDENCES])
    
    # Alternative with cardinality (decomposed)
    for i, size, reqs in TASKS:
        for type_id, qty in reqs:
            if qty > 0 and (candidates := TYPE_MAP.get(type_id, [])):
                candidate_intervals = [O[(i, r)] for r in candidates]
                mdl.add(mdl.sum([itv.presence() for itv in candidate_intervals]) == qty)
                mdl.add([T[i].start_at_start(itv) for itv in candidate_intervals])
                mdl.add([T[i].end_at_end(itv) for itv in candidate_intervals])
    
    # NoOverlap per unit
    for r in range(M):
        intervals = [itv for (i, uid), itv in O.items() if uid == r]
        if intervals:
            mdl.add(mdl.no_overlap(intervals))
    
    # Calendar compliance
    for (i, r), itv in O.items():
        if r in res_availability:
            mdl.add(itv.forbid_extent(res_availability[r]))
    
    return mdl, {'T': T, 'O': O}


def build_model_v2_mig_no_delay(data: dict, name: str) -> tuple:
    """Variant 2: Migration | No Delays"""
    N = data['N']
    TASKS, TYPES, UNITS, PRECEDENCES = data['TASKS'], data['TYPES'], data['UNITS'], data['PRECEDENCES']
    
    mdl = cp.Model(name=name)
    
    res_types = prepare_types(TYPES)
    res_breaks = extract_breaks(UNITS)
    
    # Master intervals
    T = {i: mdl.interval_var(length=size, name=f"T{i}") for i, size, _ in TASKS}
    
    # Objective
    mdl.minimize(mdl.max([T[i].end() for i in range(N)]))
    
    # Precedences
    mdl.add([T[i].end_before_start(T[j]) for i, j in PRECEDENCES])
    
    # Capacity constraints: usage + breaks <= capacity
    for type_id, rtype in res_types.items():
        usage = mdl.sum([mdl.pulse(T[i], qty) for i, _, reqs in TASKS 
                        for req_type, qty in reqs if req_type == type_id and qty > 0])
        breaks = mdl.sum([mdl.pulse(mdl.interval_var(start=(s, s), end=(s+d, s+d)), 1)
                         for u in rtype["units"] if u in res_breaks for s, d in res_breaks[u]])
        mdl.add(usage + breaks <= rtype["capacity"])
    
    return mdl, {'T': T}


def build_model_v3_no_mig_delay_block(data: dict, name: str) -> tuple:
    """Variant 3: No Migration | Delays | Blocked"""
    N, M = data['N'], data['M']
    TASKS, PRECEDENCES = data['TASKS'], data['PRECEDENCES']
    TYPE_MAP, RES_MAP = data['TYPE_MAP'], data['RES_MAP']
    
    mdl = cp.Model(name=name)
    
    task_modes = build_modes(TASKS, TYPE_MAP)
    
    # Joint intensity step functions
    joint_intensities = {}
    for i in task_modes:
        for m in task_modes[i]:
            steps = joint_intensity_steps(m, RES_MAP)
            if steps:
                joint_intensities[(i, m)] = mdl.step_function(steps)
    
    # Master intervals
    T = {i: mdl.interval_var(name=f"T{i}") for i, _, _ in TASKS}
    
    # Mode intervals
    O = {(i, m): mdl.interval_var(optional=True, name=f"T{i}_M{m}")
         for i in task_modes for m in task_modes[i]}
    
    # Objective
    mdl.minimize(mdl.max([T[i].end() for i in range(N)]))
    
    # Precedences
    mdl.add([T[i].end_before_start(T[j]) for i, j in PRECEDENCES])
    
    # Alternative: mode selection
    for i in T:
        modes_for_task = [O[(i, m)] for m in task_modes[i]]
        if modes_for_task:
            mdl.add(mdl.alternative(T[i], modes_for_task))
    
    # NoOverlap per resource
    for r in range(M):
        intervals = [O[(i, m)] for (i, m) in O if r in m]
        if intervals:
            mdl.add(mdl.no_overlap(intervals))
    
    # Work content: size = integral of intensity
    for i, size, _ in TASKS:
        if size > 0:
            for m in task_modes[i]:
                if (i, m) in joint_intensities:
                    work = mdl.step_function_sum(joint_intensities[(i, m)], O[(i, m)])
                    mdl.add(work.guard(size) == size)
    
    # Forbid start during unavailability
    for (i, m), itv in O.items():
        if (i, m) in joint_intensities and m:
            mdl.add(itv.forbid_start(joint_intensities[(i, m)]))
    
    return mdl, {'T': T, 'O': O, 'task_modes': task_modes}


def build_model_v4_mig_delay(data: dict, name: str) -> tuple:
    """Variant 4: Migration | Delays"""
    TASKS, TYPES, UNITS, PRECEDENCES = data['TASKS'], data['TYPES'], data['UNITS'], data['PRECEDENCES']
    TYPE_MAP, RES_MAP = data['TYPE_MAP'], data['RES_MAP']
    
    mdl = cp.Model(name=name)
    
    res_types = prepare_types(TYPES)
    res_breaks = extract_breaks(UNITS)
    
    # Capacity windows per task
    task_windows = {i: capacity_windows(reqs, TYPE_MAP, RES_MAP) for i, _, reqs in TASKS}
    
    # Master intervals
    T = {i: mdl.interval_var(name=f"T{i}") for i, _, _ in TASKS}
    
    # Segment intervals
    S = {(i, w): mdl.interval_var(optional=True, start=(s, e-1), end=(s+1, e), name=f"T{i}_seg{w}")
         for i in task_windows for w, (s, e) in enumerate(task_windows[i])}
    
    # Objective
    mdl.minimize(mdl.max([T[i].end() for i in T]))
    
    # Precedences
    mdl.add([T[i].end_before_start(T[j]) for i, j in PRECEDENCES])
    
    # Span
    for i, _, _ in TASKS:
        segs = [S[(i, w)] for w in range(len(task_windows[i]))]
        if segs:
            mdl.add(mdl.span(T[i], segs))
    
    # Work content
    for i, size, _ in TASKS:
        if size > 0:
            mdl.add(mdl.sum([S[(i, w)].length().guard(0) for w in range(len(task_windows[i]))]) == size)
    
    # Capacity on segments
    for type_id, rtype in res_types.items():
        usage = mdl.sum([mdl.pulse(S[(i, w)], qty) for i, _, reqs in TASKS 
                        for req_type, qty in reqs if req_type == type_id and qty > 0
                        for w in range(len(task_windows[i]))])
        breaks = mdl.sum([mdl.pulse(mdl.interval_var(start=(s, s), end=(s+d, s+d)), 1)
                         for u in rtype["units"] if u in res_breaks for s, d in res_breaks[u]])
        mdl.add(usage + breaks <= rtype["capacity"])
    
    return mdl, {'T': T, 'S': S, 'task_windows': task_windows}


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
    
    mdl = cp.Model(name=name)
    
    res_types = prepare_types(TYPES)
    res_breaks = extract_breaks(UNITS)
    
    # Availability for fixed types
    res_availability = {r: mdl.step_function(steps) for r, steps in UNITS
                       if any(r in TYPE_MAP.get(k, []) for k in fixed_types)}
    
    # Master intervals
    T = {i: mdl.interval_var(length=size, name=f"T{i}") for i, size, _ in TASKS}
    
    # Unit intervals for fixed types
    O = {(i, r): mdl.interval_var(length=size, optional=True, name=f"T{i}_U{r}")
         for i, size, reqs in TASKS for k, q in reqs if k in fixed_types and q > 0 
         for r in TYPE_MAP.get(k, [])}
    
    # Objective
    mdl.minimize(mdl.max([T[i].end() for i in T]))
    
    # Precedences
    mdl.add([T[i].end_before_start(T[j]) for i, j in PRECEDENCES])
    
    # Fixed types: select units with cardinality + synchronization
    for i, size, reqs in TASKS:
        for k, q in reqs:
            if k in fixed_types and q > 0:
                candidates = [O[(i, r)] for r in TYPE_MAP.get(k, [])]
                if candidates:
                    mdl.add(mdl.sum([itv.presence() for itv in candidates]) == q)
                    mdl.add([T[i].start_at_start(itv) for itv in candidates])
                    mdl.add([T[i].end_at_end(itv) for itv in candidates])
    
    # NoOverlap per unit for fixed types
    for k in fixed_types:
        for r in TYPE_MAP.get(k, []):
            intervals = [O[(i, r)] for (i, uid) in O if uid == r]
            if intervals:
                mdl.add(mdl.no_overlap(intervals))
    
    # Calendar for fixed types
    for (i, r), itv in O.items():
        if r in res_availability:
            mdl.add(itv.forbid_extent(res_availability[r]))
    
    # Capacity for migration types
    for k in migration_types:
        if k not in res_types:
            continue
        rtype = res_types[k]
        usage = mdl.sum([mdl.pulse(T[i], q) for i, _, reqs in TASKS for rk, q in reqs if rk == k and q > 0])
        breaks = mdl.sum([mdl.pulse(mdl.interval_var(start=(s, s), end=(s+d, s+d)), 1)
                         for u in rtype["units"] if u in res_breaks for s, d in res_breaks[u]])
        mdl.add(usage + breaks <= rtype["capacity"])
    
    return mdl, {'T': T, 'O': O, 'fixed_types': fixed_types, 'migration_types': migration_types}


def build_model_v6_no_mig_delay_rel(data: dict, name: str) -> tuple:
    """Variant 6: No Migration | Delays | Released"""
    M = data['M']
    TASKS, PRECEDENCES = data['TASKS'], data['PRECEDENCES']
    TYPE_MAP, RES_MAP = data['TYPE_MAP'], data['RES_MAP']
    
    mdl = cp.Model(name=name)
    
    task_modes = build_modes(TASKS, TYPE_MAP)
    work_windows = {(tid, m): compute_work_windows(m, RES_MAP) 
                   for tid in task_modes for m in task_modes[tid]}
    
    # Master intervals
    T = {i: mdl.interval_var(name=f"T{i}") for i, _, _ in TASKS}
    
    # Mode intervals
    M_var = {(i, m): mdl.interval_var(optional=True, name=f"T{i}_M{m}")
             for i in task_modes for m in task_modes[i]}
    
    # Segment intervals
    S = {(i, m, w): mdl.interval_var(optional=True, start=(ws, we-1), end=(ws+1, we), 
                                     name=f"T{i}_M{m}_seg{w}")
         for (i, m), windows in work_windows.items() for w, (ws, we) in enumerate(windows)}
    
    # Objective
    mdl.minimize(mdl.max([T[i].end() for i in T]))
    
    # Precedences
    mdl.add([T[i].end_before_start(T[j]) for i, j in PRECEDENCES])
    
    # Mode selection
    for i, _, _ in TASKS:
        modes = [M_var[(i, m)] for m in task_modes[i]]
        if modes:
            mdl.add(mdl.alternative(T[i], modes))
    
    # Span: mode spans segments
    for (i, m), windows in work_windows.items():
        segs = [S[(i, m, w)] for w in range(len(windows))]
        if segs:
            mdl.add(mdl.span(M_var[(i, m)], segs))
    
    # Work content
    for i, size, _ in TASKS:
        if size > 0:
            for m in task_modes[i]:
                seg_sum = mdl.sum([S[(i, m, w)].length().guard(0) for w in range(len(work_windows[(i, m)]))])
                mdl.add(mdl.implies(M_var[(i, m)].presence(), seg_sum == size))
    
    # NoOverlap on segments per resource
    for r in range(M):
        segs = [S[(i, m, w)] for (i, m, w) in S if r in m]
        if segs:
            mdl.add(mdl.no_overlap(segs))
    
    return mdl, {'T': T, 'M': M_var, 'S': S, 'task_modes': task_modes, 'work_windows': work_windows}


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

def solve(filepath: str, time_limit: int, workers: int, log_level: int,
          solver_params: dict, variant: str) -> dict:
    """Solve instance and return results."""
    name = Path(filepath).stem
    data = parse_instance(filepath)
    mdl, vars_dict = build_model(data, name, variant)
    
    params = cp.Parameters(
        timeLimit=time_limit,
        nbWorkers=workers,
        logLevel=log_level,
        **solver_params
    )
    
    result = mdl.solve(params=params)
    
    output = {
        "modelName": name,
        "variant": VARIANT_NAMES.get(variant, variant),
        "duration": result.duration,
        "solver": result.solver,
        "objective": result.objective_value,
        "lowerBound": result.lower_bound,
        "bestSolution": result.objective_value,
        "bestSolutionTime": result.solution_time,
        "bestLBTime": result.best_lb_time,
        "proof": result.proof,
        "nbSolutions": result.nb_solutions,
        "nbBranches": result.nb_branches,
        "nbFails": result.nb_fails,
        "nbLNSSteps": result.nb_lns_steps,
        "nbRestarts": result.nb_restarts,
        "memoryUsed": result.memory_used,
        "nbIntVars": result.nb_int_vars,
        "nbIntervalVars": result.nb_interval_vars,
        "nbConstraints": result.nb_constraints,
        "nbWorkers": workers,
        "objectiveSense": "minimize",
        "solveDate": datetime.now().isoformat() + "Z",
        "parameters": params._to_dict() if hasattr(params, '_to_dict') else {},
        "objectiveHistory": [],
        "lowerBoundHistory": [],
    }
    
    # Build history
    if hasattr(result, 'objective_history') and result.objective_history:
        output["objectiveHistory"] = [{"objective": h['objective'], "solveTime": h['solveTime']} 
                                       for h in result.objective_history]
    elif result.objective_value is not None:
        output["objectiveHistory"] = [{"objective": result.objective_value, 
                                        "solveTime": result.solution_time or result.duration}]
    
    if hasattr(result, 'lower_bound_history') and result.lower_bound_history:
        output["lowerBoundHistory"] = [{"value": h['value'], "solveTime": h['solveTime']} 
                                        for h in result.lower_bound_history]
    elif result.lower_bound is not None:
        output["lowerBoundHistory"] = [{"value": result.lower_bound, 
                                         "solveTime": result.best_lb_time or result.duration}]
    
    return output


def main():
    parser = argparse.ArgumentParser(description='Solve RCPSP-TimeOffs with OptalCP')
    add_common_args(parser)
    add_solver_args(parser, OPTAL_PARAMS)
    parser.add_argument('--variant', type=str, default='1',
                       help='Problem variant: 1-6 or name (no_mig_no_delay, mig_no_delay, etc.)')
    args = parser.parse_args()
    
    log_level = int(args.logLevel) if str(args.logLevel).isdigit() else 0
    solver_params = get_solver_params(args, OPTAL_PARAMS)
    
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
