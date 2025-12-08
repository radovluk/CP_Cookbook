#!/usr/bin/env python3
"""
OptalCP Solver Template

Usage:
    python solve_optal.py instance.sm --timeLimit 60 --workers 8
    python solve_optal.py instance.sm --searchType LNS --noOverlapPropagationLevel 3
"""

import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

import optalcp as cp

# Import shared config (copy config.py to problem directory or adjust path)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DEFAULTS, OPTAL_PARAMS, add_common_args, 
                    add_solver_args, get_solver_params)


# =============================================================================
# PARSER SECTION - Customize per problem
# =============================================================================

def parse_instance(filepath: str) -> dict:
    """Parse instance file. CUSTOMIZE THIS FOR YOUR PROBLEM."""
    import re
    with open(filepath, 'r') as f:
        content = f.read()
    
    data = {}
    
    # Example: RCPSP-TT parsing (replace with your format)
    match = re.search(r'jobs \(incl\. supersource/sink \):\s*(\d+)', content)
    data['n_jobs'] = int(match.group(1)) if match else 0
    
    match = re.search(r' - renewable\s*:\s*(\d+)', content)
    data['n_resources'] = int(match.group(1)) if match else 0
    
    # Parse precedence
    data['precedence_arcs'] = []
    prec_start = content.find('PRECEDENCE RELATIONS:')
    prec_end = content.find('****************', prec_start)
    for line in content[prec_start:prec_end].splitlines()[2:]:
        if not line.strip():
            continue
        parts = [int(p) for p in line.strip().split()]
        if len(parts) >= 4:
            for succ in parts[3:]:
                data['precedence_arcs'].append((parts[0] - 1, succ - 1))
    
    # Parse durations and demands
    data['durations'], data['demands'] = [], []
    req_start = content.find('REQUESTS/DURATIONS:')
    req_end = content.find('****************', req_start)
    for line in content[req_start:req_end].splitlines()[3:]:
        if not line.strip():
            continue
        parts = [int(p) for p in line.strip().split()]
        if len(parts) >= 3:
            data['durations'].append(parts[2])
            data['demands'].append(parts[3:])
    
    # Parse capacities
    cap_start = content.find('RESOURCEAVAILABILITIES:')
    cap_end = content.find('****************', cap_start)
    cap_line = content[cap_start:cap_end].splitlines()[2]
    data['capacities'] = [int(p) for p in cap_line.strip().split()]
    
    # Parse transfer times
    data['transfer_times'] = []
    current_pos = cap_end
    for _ in range(data['n_resources']):
        tt_start = content.find('TRANSFERTIMES', current_pos)
        if tt_start == -1:
            break
        tt_end = content.find('****************', tt_start)
        matrix = []
        for i, line in enumerate(content[tt_start:tt_end].splitlines()[3:]):
            if i >= data['n_jobs']:
                break
            parts = [int(p) for p in line.strip().split()]
            matrix.append(parts[1:])
        data['transfer_times'].append(matrix)
        current_pos = tt_end
    
    return data


# =============================================================================
# MODEL SECTION - Customize per problem
# =============================================================================

def compute_transitive_closure(edges, n):
    adj = [[False] * n for _ in range(n)]
    for i, j in edges:
        adj[i][j] = True
    for k in range(n):
        for i in range(n):
            for j in range(n):
                adj[i][j] = adj[i][j] or (adj[i][k] and adj[k][j])
    return [(i, j) for i in range(n) for j in range(n) if adj[i][j]]


def compute_transfers(n_jobs, n_res, Q, C, E, limit=1000):
    T, E_set = {}, set(E)
    for i in range(n_jobs):
        for j in range(n_jobs):
            if i == j or (j, i) in E_set:
                continue
            for r in range(n_res):
                src = (i == 0 or Q[i][r] > 0)
                tgt = (j == n_jobs - 1 or Q[j][r] > 0)
                if src and tgt:
                    T[(i, j, r)] = min(C[r] if i == 0 else min(Q[i][r], C[r]), limit)
    return T


def build_model(data: dict, name: str) -> cp.Model:
    """Build CP model. CUSTOMIZE THIS FOR YOUR PROBLEM."""
    n, n_res = data['n_jobs'], data['n_resources']
    p, C = data['durations'], data['capacities']
    Q = [row[:] for row in data['demands']]
    Q[0], Q[n-1] = C[:], C[:]
    E = compute_transitive_closure(data['precedence_arcs'], n)
    Delta = [[[data['transfer_times'][r][i][j] for r in range(n_res)] 
              for j in range(n)] for i in range(n)]
    T = compute_transfers(n, n_res, Q, C, E)
    
    model = cp.Model()
    model.name = name
    
    # Variables
    a = [model.interval_var(length=p[i], name=f'a_{i}') for i in range(n)]
    f = {k: model.int_var(min=1, max=v, optional=True, name=f'f_{k}') for k, v in T.items()}
    z = {k: model.interval_var(length=Delta[k[0]][k[1]][k[2]], optional=True, name=f'z_{k}') 
         for k in T}
    
    # Objective
    model.minimize(a[n-1].end())
    
    # Constraints
    for i, j in E:
        model.add(a[i].end_before_start(a[j]))
    
    for r in range(n_res):
        out = [f[(0, j, r)] for j in range(n) if (0, j, r) in T]
        if out:
            model.add(model.sum(out) == C[r])
    
    for k in T:
        model.add(f[k].presence() == z[k].presence())
    
    for i in range(1, n):
        for r in range(n_res):
            if Q[i][r] > 0:
                inc = [f[(j, i, r)] for j in range(n) if (j, i, r) in T]
                if inc:
                    model.add(model.sum(inc) == Q[i][r])
    
    for i in range(1, n-1):
        for r in range(n_res):
            if Q[i][r] > 0:
                out = [f[(i, j, r)] for j in range(n) if (i, j, r) in T]
                if out:
                    model.add(model.sum(out) == Q[i][r])
    
    for k in T:
        model.add(a[k[0]].end_before_start(z[k]))
        model.add(z[k].end_before_start(a[k[1]]))
    
    for r in range(n_res):
        pulses = [model.pulse(a[i], Q[i][r]) for i in range(n) if Q[i][r] > 0]
        pulses += [model.pulse(z[k], f[k]) for k in T if k[2] == r and Delta[k[0]][k[1]][r] > 0]
        if pulses:
            model.add(model.sum(pulses) <= C[r])
    
    return model


# =============================================================================
# SOLVER SECTION - Generic, keep as-is
# =============================================================================

def solve(filepath: str, time_limit: int, workers: int, log_level: int, 
          solver_params: dict) -> dict:
    """Solve instance and return results."""
    name = Path(filepath).stem
    data = parse_instance(filepath)
    model = build_model(data, name)
    
    params = cp.Parameters(
        timeLimit=time_limit,
        nbWorkers=workers,
        logLevel=log_level,
        **solver_params
    )
    
    result = model.solve(params=params)
    
    output = {
        "modelName": name,
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
        "parameters": params._to_dict(),
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
    parser = argparse.ArgumentParser(description='Solve with OptalCP')
    add_common_args(parser)
    add_solver_args(parser, OPTAL_PARAMS)
    args = parser.parse_args()
    
    log_level = int(args.logLevel) if str(args.logLevel).isdigit() else 0
    solver_params = get_solver_params(args, OPTAL_PARAMS)
    
    results = []
    for inst in args.instances:
        print(f"Solving {inst}...")
        try:
            r = solve(inst, args.timeLimit, args.workers, log_level, solver_params)
            results.append(r)
            status = "Optimal" if r.get('proof') else "Feasible" if r.get('objective') else "No solution"
            print(f"  {r.get('objective', '-')} ({status}) in {r['duration']:.2f}s")
        except Exception as e:
            print(f"  Error: {e}")
            results.append({"modelName": Path(inst).stem, "error": str(e)})
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()