#!/usr/bin/env python3
"""
IBM CP Optimizer Solver Template

Usage:
    python solve_cpo.py instance.sm --timeLimit 60 --workers 8
    python solve_cpo.py instance.sm --SearchType DepthFirst --NoOverlapInferenceLevel Medium
"""

import json
import argparse
import sys
import os
import time
from pathlib import Path
from datetime import datetime

from docplex.cp.model import CpoModel

# Import shared config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DEFAULTS, CPO_PARAMS, CPO_LOG_LEVELS, add_common_args,
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
    
    match = re.search(r'jobs \(incl\. supersource/sink \):\s*(\d+)', content)
    data['n_jobs'] = int(match.group(1)) if match else 0
    
    match = re.search(r' - renewable\s*:\s*(\d+)', content)
    data['n_resources'] = int(match.group(1)) if match else 0
    
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
    
    cap_start = content.find('RESOURCEAVAILABILITIES:')
    cap_end = content.find('****************', cap_start)
    cap_line = content[cap_start:cap_end].splitlines()[2]
    data['capacities'] = [int(p) for p in cap_line.strip().split()]
    
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


def build_model(data: dict, name: str) -> tuple:
    """Build CP model. CUSTOMIZE THIS FOR YOUR PROBLEM. Returns (model, info)."""
    n, n_res = data['n_jobs'], data['n_resources']
    p, C = data['durations'], data['capacities']
    Q = [row[:] for row in data['demands']]
    Q[0], Q[n-1] = C[:], C[:]
    E = compute_transitive_closure(data['precedence_arcs'], n)
    Delta = [[[data['transfer_times'][r][i][j] for r in range(n_res)] 
              for j in range(n)] for i in range(n)]
    T = compute_transfers(n, n_res, Q, C, E)
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    # Variables
    a = [mdl.interval_var(size=p[i], name=f'a_{i}') for i in range(n)]
    info["nb_interval_vars"] += n
    
    f = {k: mdl.integer_var(min=0, max=v, name=f'f_{k}') for k, v in T.items()}
    info["nb_int_vars"] += len(f)
    
    z = {k: mdl.interval_var(size=Delta[k[0]][k[1]][k[2]], optional=True, name=f'z_{k}') 
         for k in T}
    info["nb_interval_vars"] += len(z)
    
    cumul_pulses = {k: mdl.pulse(z[k], (0, T[k])) for k in T if Delta[k[0]][k[1]][k[2]] > 0}
    
    # Objective
    mdl.add(mdl.minimize(mdl.end_of(a[n-1])))
    info["nb_constraints"] += 1
    
    # Constraints
    for i, j in E:
        mdl.add(mdl.end_before_start(a[i], a[j]))
        info["nb_constraints"] += 1
    
    for r in range(n_res):
        out = [f[(0, j, r)] for j in range(n) if (0, j, r) in T]
        if out:
            mdl.add(mdl.sum(out) == C[r])
            info["nb_constraints"] += 1
    
    for k in T:
        if Delta[k[0]][k[1]][k[2]] == 0:
            mdl.add(mdl.if_then(f[k] >= 1, mdl.presence_of(z[k])))
            mdl.add(mdl.if_then(mdl.presence_of(z[k]), f[k] >= 1))
            info["nb_constraints"] += 2
        else:
            mdl.add(f[k] == mdl.height_at_start(z[k], cumul_pulses[k]))
            info["nb_constraints"] += 1
    
    for i in range(1, n):
        for r in range(n_res):
            if Q[i][r] > 0:
                inc = [f[(j, i, r)] for j in range(n) if (j, i, r) in T]
                if inc:
                    mdl.add(mdl.sum(inc) == Q[i][r])
                    info["nb_constraints"] += 1
    
    for i in range(1, n-1):
        for r in range(n_res):
            if Q[i][r] > 0:
                out = [f[(i, j, r)] for j in range(n) if (i, j, r) in T]
                if out:
                    mdl.add(mdl.sum(out) == Q[i][r])
                    info["nb_constraints"] += 1
    
    for k in T:
        mdl.add(mdl.end_before_start(a[k[0]], z[k]))
        mdl.add(mdl.end_before_start(z[k], a[k[1]]))
        info["nb_constraints"] += 2
    
    for r in range(n_res):
        pulses = [mdl.pulse(a[i], Q[i][r]) for i in range(n) if Q[i][r] > 0]
        pulses += [cumul_pulses[k] for k in cumul_pulses if k[2] == r]
        if pulses:
            mdl.add(mdl.sum(pulses) <= C[r])
            info["nb_constraints"] += 1
    
    return mdl, info


# =============================================================================
# SOLVER SECTION - Generic, keep as-is
# =============================================================================

def solve(filepath: str, time_limit: int, workers: int, log_level: str,
          solver_params: dict) -> dict:
    """Solve instance and return results."""
    name = Path(filepath).stem
    data = parse_instance(filepath)
    mdl, info = build_model(data, name)
    
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
    parser = argparse.ArgumentParser(description='Solve with IBM CP Optimizer')
    add_common_args(parser)
    add_solver_args(parser, CPO_PARAMS)
    args = parser.parse_args()
    
    # Convert log level
    log_level = args.logLevel
    if str(log_level).isdigit():
        log_level = CPO_LOG_LEVELS.get(int(log_level), 'Quiet')
    
    solver_params = get_solver_params(args, CPO_PARAMS)
    
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