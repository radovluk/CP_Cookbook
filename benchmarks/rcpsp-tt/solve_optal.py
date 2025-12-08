#!/usr/bin/env python3
"""
RCPSP-TT Solver using OptalCP (Python API)

This script solves RCPSP-TT instances and outputs results in JSON format
for benchmarking comparisons.

Usage:
    python solve_optal.py <instance.sm> [--timeLimit 60] [--workers 8] [--output results.json]

Structure:
    1. PARSER SECTION - Parse instance files (replace for different problems)
    2. MODEL SECTION - Build CP model (replace for different problems)  
    3. SOLVER SECTION - Run solver and collect results (keep as-is)
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

# OptalCP Python API
import optalcp as gcp

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


def build_model(data: dict, model_name: str) -> gcp.Model:
    """
    Build the RCPSP-TT model using OptalCP Python API.
    
    Replace this function for different problem types.
    Returns: OptalCP Model object
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
    model = gcp.Model()
    model.name = model_name

    # =========================================================================
    # Variables
    # =========================================================================
    
    # (9a): a_i - mandatory interval variables for activities
    a = [model.interval_var(length=p[i], name=f'a_{i}') for i in range(abs_A)]

    # (9b): f_{i,j,r} - OPTIONAL integer flow variables with min=1
    f = {}
    for (i, j, r), U_ijr in T.items():
        f[(i, j, r)] = model.int_var(min=1, max=U_ijr, optional=True, 
                                      name=f'f_{i}_{j}_{r}')

    # (9c): z_{i,j,r} - optional interval variables for transfers
    z = {}
    for (i, j, r) in T.keys():
        z[(i, j, r)] = model.interval_var(length=Delta[i][j][r], optional=True,
                                           name=f'z_{i}_{j}_{r}')

    # =========================================================================
    # Constraints
    # =========================================================================

    # (1) Objective: Minimize makespan
    model.minimize(a[abs_A - 1].end())

    # (2) Precedence relations - MUST use model.add()!
    for (i, j) in E:
        model.add(a[i].end_before_start(a[j]))

    # (3) Source flow initialization
    for r in range(abs_R):
        outgoing = [f[(0, j, r)] for j in range(abs_A) if (0, j, r) in T]
        if outgoing:
            model.add(model.sum(outgoing) == C[r])

    # (4) Presence synchronization: flow exists iff transfer interval exists
    for key in T.keys():
        model.add(f[key].presence() == z[key].presence())

    # (5) Flow conservation (into activity)
    for i in range(1, abs_A):
        for r in range(abs_R):
            if Q[i][r] > 0:
                incoming = [f[(j, i, r)] for j in range(abs_A) if (j, i, r) in T]
                if incoming:
                    model.add(model.sum(incoming) == Q[i][r])

    # (6) Flow conservation (out of activity)
    for i in range(1, abs_A - 1):
        for r in range(abs_R):
            if Q[i][r] > 0:
                outgoing = [f[(i, j, r)] for j in range(abs_A) if (i, j, r) in T]
                if outgoing:
                    model.add(model.sum(outgoing) == Q[i][r])

    # (7) Temporal linking - MUST use model.add()!
    for (i, j, r) in T.keys():
        model.add(a[i].end_before_start(z[(i, j, r)]))
        model.add(z[(i, j, r)].end_before_start(a[j]))

    # (8) Resource capacity (cumulative constraint)
    for r in range(abs_R):
        pulses = []
        # Activity contributions
        for i in range(abs_A):
            if Q[i][r] > 0:
                pulses.append(model.pulse(a[i], Q[i][r]))
        # Transfer contributions (variable height)
        for (i, j, res) in T.keys():
            if res == r and Delta[i][j][r] > 0:
                pulses.append(model.pulse(z[(i, j, r)], f[(i, j, r)]))
        if pulses:
            model.add(model.sum(pulses) <= C[r])

    return model


# =============================================================================
# SOLVER SECTION - Keep this as-is for most problems
# =============================================================================

def get_solver_parameters(time_limit: int, workers: int, **kwargs) -> gcp.Parameters:
    """
    Returns solver Parameters object.
    
    Parameter mapping (OptalCP → CPO equivalent):
    - timeLimit → TimeLimit (seconds)
    - nbWorkers → Workers
    - searchType="FDSLB" → SearchType="Restart" + FailureDirectedSearch="On"
    - fdsLBStrategy="Split" → (CPO uses internal heuristics)
    - noOverlapPropagationLevel=4 → NoOverlapInferenceLevel="Extended"
    - cumulPropagationLevel=3 → CumulFunctionInferenceLevel="Extended"
    - reservoirPropagationLevel=2 → (no direct CPO equivalent)
    - usePrecedenceEnergy=1 → PrecedenceInferenceLevel="Extended"
    - logLevel (0-3) → LogVerbosity ("Quiet"/"Terse"/"Normal"/"Verbose")
    - logPeriod (seconds) → LogPeriod (branches)
    """
    return gcp.Parameters(
        timeLimit=time_limit,
        nbWorkers=workers,
        searchType="FDSLB",
        fdsLBStrategy="Split",
        noOverlapPropagationLevel=4,
        cumulPropagationLevel=3,
        reservoirPropagationLevel=2,
        usePrecedenceEnergy=1,
        logLevel=kwargs.get('log_level', 2),
        logPeriod=5.0,
    )


def solve_instance(filepath: str, time_limit: int = 60, workers: int = 8, 
                   log_level: int = 2) -> dict:
    """
    Solve a single instance and return results in benchmark format.
    """
    model_name = Path(filepath).stem
    
    # Parse instance
    data = parse_instance(filepath)
    
    # Build model
    model = build_model(data, model_name)
    
    # Get parameters
    params = get_solver_parameters(time_limit, workers, log_level=log_level)
    
    # Solve - pass Parameters object
    result = model.solve(params=params)
    
    # Build output in benchmark format
    # SolveResult properties: duration, objective_value, lower_bound, proof, 
    # nb_solutions, nb_branches, nb_fails, nb_lns_steps, nb_restarts,
    # memory_used, nb_int_vars, nb_interval_vars, nb_constraints, solver
    output = {
        "modelName": model_name,
        "duration": result.duration,
        "solver": result.solver,
        "nbWorkers": workers,
        "objectiveSense": "minimize",
        "nbIntVars": result.nb_int_vars,
        "nbIntervalVars": result.nb_interval_vars,
        "nbConstraints": result.nb_constraints,
        "solveDate": datetime.now().isoformat() + "Z",
        "parameters": params._to_dict(),
        
        # Solution info
        "objective": result.objective_value,
        "lowerBound": result.lower_bound,
        "bestSolution": result.objective_value,
        "bestSolutionTime": result.solution_time,
        "bestLBTime": result.best_lb_time,
        "proof": result.proof,
        
        # Statistics
        "nbSolutions": result.nb_solutions,
        "nbBranches": result.nb_branches,
        "nbFails": result.nb_fails,
        "nbLNSSteps": result.nb_lns_steps,
        "nbRestarts": result.nb_restarts,
        "memoryUsed": result.memory_used,
        
        # History
        "objectiveHistory": [],
        "lowerBoundHistory": [],
    }
    
    # Extract history if available
    if result.objective_history:
        output["objectiveHistory"] = [
            {"objective": h['objective'], "solveTime": h['solveTime']} 
            for h in result.objective_history
        ]
    elif result.objective_value is not None:
        output["objectiveHistory"] = [{
            "objective": result.objective_value,
            "solveTime": result.solution_time or result.duration
        }]
    
    if result.lower_bound_history:
        output["lowerBoundHistory"] = [
            {"value": h['value'], "solveTime": h['solveTime']} 
            for h in result.lower_bound_history
        ]
    elif result.lower_bound is not None:
        output["lowerBoundHistory"] = [{
            "value": result.lower_bound,
            "solveTime": result.best_lb_time or result.duration
        }]
    
    return output


def main():
    parser = argparse.ArgumentParser(description='Solve with OptalCP')
    parser.add_argument('instances', nargs='+', help='Instance file(s)')
    parser.add_argument('--timeLimit', type=int, default=60, help='Time limit in seconds')
    parser.add_argument('--workers', type=int, default=8, help='Number of workers')
    parser.add_argument('--output', type=str, help='Output JSON file')
    parser.add_argument('--logLevel', type=int, default=2, choices=[0, 1, 2, 3],
                        help='Log verbosity (0=quiet, 3=verbose)')
    
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
            status = "Optimal" if result.get('proof') else "Feasible" if result.get('objective') else "No solution"
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