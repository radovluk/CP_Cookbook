#!/usr/bin/env python3
"""
RCPSP-TT Solver using IBM CP Optimizer (DOcplex)

This script solves RCPSP-TT instances and outputs results in JSON format
for benchmarking comparisons.

Usage:
    python solve_cpo.py <instance.sm> [--timeLimit 60] [--workers 8] [--output results.json]

Structure:
    1. PARSER SECTION - Parse instance files (replace for different problems)
    2. MODEL SECTION - Build CP model (replace for different problems)  
    3. SOLVER SECTION - Run solver and collect results (keep as-is)
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

# IBM CP Optimizer Python API
from docplex.cp.model import CpoModel

# =============================================================================
# PARSER SECTION - Replace this for different problem types
# =============================================================================

def parse_instance(filepath: str) -> dict:
    """
    Parses a .sm file (PSPLIB format for RCPSP with transfer times)
    and returns a dictionary with the project data.
    
    Replace this function for different problem formats.
    """
    with open(filepath, 'r') as f:
        content = f.read()

    import re
    data = {}
    
    match = re.search(r'jobs \(incl\. supersource/sink \):\s*(\d+)', content)
    data['n_jobs'] = int(match.group(1)) if match else 0
    
    match = re.search(r' - renewable\s*:\s*(\d+)', content)
    data['n_resources'] = int(match.group(1)) if match else 0
    
    n_jobs = data['n_jobs']
    n_res = data['n_resources']

    # Parse precedence relations
    data['precedence_arcs'] = []
    prec_start = content.find('PRECEDENCE RELATIONS:')
    prec_end = content.find('****************', prec_start)
    prec_section = content[prec_start:prec_end]
    
    for line in prec_section.splitlines()[2:]:
        if not line.strip():
            continue
        parts = [int(p) for p in line.strip().split()]
        if len(parts) < 3:
            continue
        predecessor = parts[0]
        successors = parts[3:]
        for succ in successors:
            data['precedence_arcs'].append((predecessor - 1, succ - 1))

    # Parse durations and demands
    data['durations'] = []
    data['demands'] = []
    req_start = content.find('REQUESTS/DURATIONS:')
    req_end = content.find('****************', req_start)
    req_section = content[req_start:req_end]

    for line in req_section.splitlines()[3:]:
        if not line.strip():
            continue
        parts = [int(p) for p in line.strip().split()]
        if len(parts) < 3:
            continue
        data['durations'].append(parts[2])
        data['demands'].append(parts[3:])

    # Parse capacities
    cap_start = content.find('RESOURCEAVAILABILITIES:')
    cap_end = content.find('****************', cap_start)
    cap_section = content[cap_start:cap_end]
    cap_line = cap_section.splitlines()[2]
    data['capacities'] = [int(p) for p in cap_line.strip().split()]

    # Parse transfer times
    data['transfer_times'] = []
    current_pos = cap_end

    for _ in range(n_res):
        tt_start = content.find('TRANSFERTIMES', current_pos)
        if tt_start == -1:
            break
        tt_end = content.find('****************', tt_start)
        tt_section = content[tt_start:tt_end]
        
        matrix = []
        lines = tt_section.splitlines()[3:]
        
        for i in range(n_jobs):
            if i >= len(lines):
                break
            line = lines[i]
            parts = [int(p) for p in line.strip().split()]
            matrix.append(parts[1:])
            
        data['transfer_times'].append(matrix)
        current_pos = tt_end
        
    return data


# =============================================================================
# MODEL SECTION - Replace this for different problem types
# =============================================================================

def compute_transitive_closure(edges: list, n_jobs: int) -> list:
    """Computes transitive closure using Floyd-Warshall."""
    adj = [[False] * n_jobs for _ in range(n_jobs)]
    for i, j in edges:
        adj[i][j] = True
    for k in range(n_jobs):
        for i in range(n_jobs):
            for j in range(n_jobs):
                adj[i][j] = adj[i][j] or (adj[i][k] and adj[k][j])
    return [(i, j) for i in range(n_jobs) for j in range(n_jobs) if adj[i][j]]


def compute_possible_transfers(abs_A: int, abs_R: int, Q: list, C: list, E: list, 
                                max_flow_limit: int = 1000) -> dict:
    """Generates feasible transfers T and upper bounds U."""
    T = {}
    E_set = set(E)
    for i in range(abs_A):
        for j in range(abs_A):
            if i == j or (j, i) in E_set:
                continue
            for r in range(abs_R):
                source_has = (i == 0 or Q[i][r] > 0)
                target_needs = (j == abs_A - 1 or Q[j][r] > 0)
                if source_has and target_needs:
                    max_flow = C[r] if i == 0 else min(Q[i][r], C[r])
                    T[(i, j, r)] = min(max_flow, max_flow_limit)
    return T


class ModelInfo:
    """Container for model statistics."""
    def __init__(self):
        self.nb_int_vars = 0
        self.nb_interval_vars = 0
        self.nb_constraints = 0


def build_model(data: dict, model_name: str) -> tuple:
    """
    Build the RCPSP-TT model using IBM CP Optimizer (DOcplex).
    
    Replace this function for different problem types.
    Returns: (CpoModel, ModelInfo)
    """
    abs_A = data['n_jobs']
    abs_R = data['n_resources']
    p = data['durations']
    C = data['capacities']
    Q = [row[:] for row in data['demands']]  # Copy to avoid mutation
    E = compute_transitive_closure(data['precedence_arcs'], abs_A)

    # Enforce Q[0,r] = Cr and Q[last,r] = Cr
    Q[0] = C[:]
    Q[abs_A - 1] = C[:]

    # Reorganize transfer times: Delta[i][j][r]
    Delta = [[[data['transfer_times'][r][i][j] for r in range(abs_R)] 
              for j in range(abs_A)] for i in range(abs_A)]

    T = compute_possible_transfers(abs_A, abs_R, Q, C, E)

    # Create model
    mdl = CpoModel(name=model_name)
    info = ModelInfo()

    # =========================================================================
    # Variables
    # =========================================================================
    
    # (10a): a_i - mandatory interval variables for activities
    a = [mdl.interval_var(size=p[i], name=f'a_{i}') for i in range(abs_A)]
    info.nb_interval_vars += abs_A

    # (10b): f_{i,j,r} - integer flow variables (non-optional for CPO compatibility)
    f = {}
    for (i, j, r), U_ijr in T.items():
        f[(i, j, r)] = mdl.integer_var(min=0, max=U_ijr, name=f'f_{i}_{j}_{r}')
        info.nb_int_vars += 1

    # (10c): z_{i,j,r} - optional interval variables for transfers
    z = {}
    for (i, j, r) in T.keys():
        z[(i, j, r)] = mdl.interval_var(size=Delta[i][j][r], optional=True,
                                         name=f'z_{i}_{j}_{r}')
        info.nb_interval_vars += 1

    # Helper: pulse expressions for cumulative constraint
    cumul_pulses = {}
    for (i, j, r) in T.keys():
        if Delta[i][j][r] > 0:
            cumul_pulses[(i, j, r)] = mdl.pulse(z[(i, j, r)], (0, T[(i, j, r)]))

    # =========================================================================
    # Constraints
    # =========================================================================

    # (1) Objective: Minimize makespan
    mdl.add(mdl.minimize(mdl.end_of(a[abs_A - 1])))
    info.nb_constraints += 1

    # (2) Precedence relations
    for (i, j) in E:
        mdl.add(mdl.end_before_start(a[i], a[j]))
        info.nb_constraints += 1

    # (3) Source flow initialization
    for r in range(abs_R):
        outgoing = [f[(0, j, r)] for j in range(abs_A) if (0, j, r) in T]
        if outgoing:
            mdl.add(mdl.sum(outgoing) == C[r])
            info.nb_constraints += 1

    # (4) Presence synchronization (bidirectional for CPO)
    for (i, j, r) in T.keys():
        if Delta[i][j][r] == 0:
            # Instantaneous transfers: use bidirectional implications
            mdl.add(mdl.if_then(f[(i, j, r)] >= 1, mdl.presence_of(z[(i, j, r)])))
            mdl.add(mdl.if_then(mdl.presence_of(z[(i, j, r)]), f[(i, j, r)] >= 1))
            info.nb_constraints += 2
        else:
            # Durative transfers: height_at_start links flow and presence
            mdl.add(f[(i, j, r)] == mdl.height_at_start(z[(i, j, r)], cumul_pulses[(i, j, r)]))
            info.nb_constraints += 1

    # (5) Flow conservation (into activity)
    for i in range(1, abs_A):
        for r in range(abs_R):
            if Q[i][r] > 0:
                incoming = [f[(j, i, r)] for j in range(abs_A) if (j, i, r) in T]
                if incoming:
                    mdl.add(mdl.sum(incoming) == Q[i][r])
                    info.nb_constraints += 1

    # (6) Flow conservation (out of activity)
    for i in range(1, abs_A - 1):
        for r in range(abs_R):
            if Q[i][r] > 0:
                outgoing = [f[(i, j, r)] for j in range(abs_A) if (i, j, r) in T]
                if outgoing:
                    mdl.add(mdl.sum(outgoing) == Q[i][r])
                    info.nb_constraints += 1

    # (7) Temporal linking
    for (i, j, r) in T.keys():
        mdl.add(mdl.end_before_start(a[i], z[(i, j, r)]))
        mdl.add(mdl.end_before_start(z[(i, j, r)], a[j]))
        info.nb_constraints += 2

    # (8) Resource capacity (cumulative constraint)
    for r in range(abs_R):
        pulses = []
        # Activity contributions
        for i in range(abs_A):
            if Q[i][r] > 0:
                pulses.append(mdl.pulse(a[i], Q[i][r]))
        # Transfer contributions
        for (i, j, res), pulse in cumul_pulses.items():
            if res == r:
                pulses.append(pulse)
        if pulses:
            mdl.add(mdl.sum(pulses) <= C[r])
            info.nb_constraints += 1

    return mdl, info


# =============================================================================
# SOLVER SECTION - Keep this as-is for most problems
# =============================================================================

def get_solver_parameters(time_limit: int, workers: int, **kwargs) -> dict:
    """
    Returns solver parameters dict matching OptalCP configuration.
    
    Parameter mapping (OptalCP → CPO):
    - timeLimit → TimeLimit (seconds)
    - nbWorkers → Workers
    - searchType="FDSLB" → SearchType="Restart" + FailureDirectedSearch="On"
    - noOverlapPropagationLevel=4 → NoOverlapInferenceLevel="Extended"
    - cumulPropagationLevel=3 → CumulFunctionInferenceLevel="Extended"  
    - reservoirPropagationLevel=2 → (no direct equivalent, handled internally)
    - usePrecedenceEnergy=1 → PrecedenceInferenceLevel="Extended"
    - logLevel → LogVerbosity
    - logPeriod (seconds) → LogPeriod (branches, ~5000 for similar frequency)
    """
    # Map log level: OptalCP uses 0-3, CPO uses symbolic
    log_level = kwargs.get('log_level', 2)
    log_verbosity_map = {0: 'Quiet', 1: 'Terse', 2: 'Normal', 3: 'Verbose'}
    log_verbosity = log_verbosity_map.get(log_level, 'Normal')
    
    return {
        # Basic limits
        "TimeLimit": time_limit,
        "Workers": workers,
        
        # Search configuration (matching FDSLB behavior)
        "SearchType": "Restart",
        "FailureDirectedSearch": "On",
        
        # Inference levels (matching OptalCP propagation levels)
        # OptalCP level 4 = highest → CPO "Extended"
        # OptalCP level 3 = high → CPO "Extended" or "Medium"
        # OptalCP level 2 = medium → CPO "Medium"
        "NoOverlapInferenceLevel": "Extended",      # matches noOverlapPropagationLevel=4
        "CumulFunctionInferenceLevel": "Extended",  # matches cumulPropagationLevel=3
        "PrecedenceInferenceLevel": "Extended",     # matches usePrecedenceEnergy=1
        
        # Logging
        "LogVerbosity": log_verbosity,
        "LogPeriod": 5000,  # branches (OptalCP uses 5 seconds)
    }


def solve_instance(filepath: str, time_limit: int = 60, workers: int = 8, 
                   log_level: int = 2) -> dict:
    """
    Solve a single instance and return results in benchmark format.
    """
    import time
    model_name = Path(filepath).stem
    
    # Parse instance
    data = parse_instance(filepath)
    
    # Build model
    mdl, info = build_model(data, model_name)
    
    # Get parameters
    params = get_solver_parameters(time_limit, workers, log_level=log_level)
    
    # Solve
    start_time = time.time()
    solution = mdl.solve(**params)
    solve_time = time.time() - start_time
    
    # Build output in benchmark format
    output = {
        "modelName": model_name,
        "duration": solve_time,
        "solver": "IBM CP Optimizer (DOcplex)",
        "nbWorkers": workers,
        "objectiveSense": "minimize",
        "nbIntVars": info.nb_int_vars,
        "nbIntervalVars": info.nb_interval_vars,
        "nbConstraints": info.nb_constraints,
        "solveDate": datetime.now().isoformat() + "Z",
        "parameters": params,
        
        # Initialize defaults
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
        "objectiveHistory": [],
        "lowerBoundHistory": [],
    }

    if solution:
        solve_status = solution.get_solve_status()
        obj_values = solution.get_objective_values()
        
        if obj_values:
            obj_value = int(obj_values[0])
            output["objective"] = obj_value
            output["bestSolution"] = obj_value
            output["nbSolutions"] = 1
            
            # Get solver info
            solver_info = solution.get_solver_infos()
            if solver_info:
                output["nbBranches"] = solver_info.get('NumberOfBranches', 0)
                output["nbFails"] = solver_info.get('NumberOfFails', 0)
                output["nbRestarts"] = solver_info.get('NumberOfRestarts', 0)
                output["memoryUsed"] = solver_info.get('MemoryUsage', 0)
                output["bestSolutionTime"] = solver_info.get('SolveTime', solve_time)
                nb_sol = solver_info.get('NumberOfSolutions', 1)
                if nb_sol:
                    output["nbSolutions"] = nb_sol
            else:
                output["bestSolutionTime"] = solve_time
            
            output["objectiveHistory"].append({
                "objective": obj_value,
                "solveTime": output["bestSolutionTime"]
            })
        
        # Check optimality
        if solve_status == 'Optimal':
            output["proof"] = True
            output["lowerBound"] = output["objective"]
            output["bestLBTime"] = output["bestSolutionTime"]
            output["lowerBoundHistory"].append({
                "value": output["objective"],
                "solveTime": output["bestLBTime"]
            })
        elif solve_status == 'Feasible':
            output["proof"] = False
            if solver_info:
                lb = solver_info.get('BestBound')
                if lb is not None:
                    output["lowerBound"] = int(lb)
                    output["lowerBoundHistory"].append({
                        "value": int(lb),
                        "solveTime": solve_time
                    })
        elif solve_status == 'Infeasible':
            output["proof"] = "Infeasible"
    
    return output


def main():
    parser = argparse.ArgumentParser(description='Solve with IBM CP Optimizer')
    parser.add_argument('instances', nargs='+', help='Instance file(s)')
    parser.add_argument('--timeLimit', type=int, default=60, help='Time limit in seconds')
    parser.add_argument('--workers', type=int, default=8, help='Number of workers')
    parser.add_argument('--output', type=str, help='Output JSON file')
    parser.add_argument('--logLevel', type=str, default='Quiet', 
                        choices=['Quiet', 'Terse', 'Normal', 'Verbose'],
                        help='Log verbosity level')
    
    args = parser.parse_args()
    
    results = []
    for instance in args.instances:
        print(f"Solving {instance}...")
        try:
            result = solve_instance(
                instance, 
                time_limit=args.timeLimit,
                workers=args.workers,
                log_level=args.logLevel
            )
            results.append(result)
            status = "Optimal" if result.get('proof') == True else "Feasible" if result.get('objective') else "No solution"
            print(f"  Objective: {result.get('objective', 'No solution')} ({status}) in {result['duration']:.3f}s")
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "modelName": Path(instance).stem,
                "error": str(e)
            })
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()