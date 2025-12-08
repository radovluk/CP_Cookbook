#!/usr/bin/env python3
"""
RCPSP-AS Solver using IBM CP Optimizer (DOcplex)

This script solves Resource-Constrained Project Scheduling Problem with 
Alternative Subgraphs (RCPSP-AS) instances and outputs results in JSON format
for benchmarking comparisons.

Usage:
    python solve_cpo_rcpspas.py <instance.rcp> [--timeLimit 60] [--workers 8] [--output results.json]

Structure:
    1. PARSER SECTION - Parse instance files using ascp package
    2. MODEL SECTION - Build CP model for RCPSP-AS
    3. SOLVER SECTION - Run solver and collect results
"""

import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# IBM CP Optimizer Python API
from docplex.cp.model import CpoModel

# Add the ascp package directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../notebooks/RCPSPAS"))

# Now import normally
from ascp.load_instance import load_instance
from ascp.instance import AslibInstance


# =============================================================================
# PARSER SECTION - Parse RCPSP-AS instances using ascp package
# =============================================================================

def parse_instance(filepath: str) -> dict:
    """
    Parses an RCPSP-AS instance file using the ascp package.
    
    Returns a dictionary with:
        - instance: AslibInstance object
        - act_dict: mapping of activity ID to activity object
        - M: mapping of branch ID to branching activity ID
    """
    instance = load_instance(filepath)
    
    # Create a dictionary to map activity IDs (0-based) to their objects
    act_dict = {act.id: act for act in instance.activities}
    
    # Build branching activity map: links branch_id to branching_activity_id
    M = {
        branch_id: b_k_act_id
        for sub in instance.subgraphs if sub.principal_activity in act_dict
        for b_k_act_id in act_dict[sub.principal_activity].successors if b_k_act_id in act_dict
        for branch_id in act_dict[b_k_act_id].branches.intersection(sub.branches) if branch_id != 0
    }
    
    # Manually add the dummy branch k* (ID 0) mapping to its branching activity (ID 0)
    M[0] = 0
    
    return {
        'instance': instance,
        'act_dict': act_dict,
        'M': M,
    }


# =============================================================================
# MODEL SECTION - Build RCPSP-AS model using IBM CP Optimizer
# =============================================================================

class ModelInfo:
    """Container for model statistics."""
    def __init__(self):
        self.nb_int_vars = 0
        self.nb_interval_vars = 0
        self.nb_constraints = 0


def build_model(data: dict, model_name: str) -> tuple:
    """
    Build the RCPSP-AS model using IBM CP Optimizer (DOcplex).
    
    The model formulation:
    (1) Minimize makespan: end of sink activity
    (2) Source activity is present
    (3) Precedence relations (conditional on both activities being present)
    (4) Subgraph branch selection: exactly one branch per subgraph
    (5) Activity selection: activity is present iff at least one of its branches is selected
    (6) Resource limits: cumulative constraint on renewable resources
    (7) Variables: optional interval variables for each activity
    
    Returns: (CpoModel, ModelInfo)
    """
    instance = data['instance']
    act_dict = data['act_dict']
    M = data['M']
    
    n_activities = len(instance.activities)
    
    # Create model
    mdl = CpoModel(name=model_name)
    info = ModelInfo()
    
    # =========================================================================
    # Variables
    # =========================================================================
    
    # (7) Create optional interval variable for each activity i with a fixed duration d_i
    x = {i: mdl.interval_var(
        name=f"T_{i}", 
        optional=True, 
        size=act.duration
    ) for i, act in act_dict.items()}
    info.nb_interval_vars = len(x)
    
    # =========================================================================
    # Constraints
    # =========================================================================
    
    # (1) Minimize the makespan (end time of the sink activity)
    mdl.add(mdl.minimize(mdl.end_of(x[n_activities - 1])))
    info.nb_constraints += 1
    
    # (2) Source activity is present
    mdl.add(mdl.presence_of(x[0]) == 1)
    info.nb_constraints += 1
    
    # (3) Precedence relations - conditional on both activities being present
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                mdl.add(
                    mdl.if_then(
                        mdl.presence_of(x[act.id]) & mdl.presence_of(x[j]),
                        mdl.end_of(x[act.id]) <= mdl.start_of(x[j])
                    )
                )
                info.nb_constraints += 1
    
    # (4) Subgraph branch selection: exactly one branch per subgraph when principal is present
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            branches = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if branches:
                mdl.add(
                    mdl.sum(mdl.presence_of(x[s]) for s in branches) == 
                    mdl.presence_of(x[sub.principal_activity])
                )
                info.nb_constraints += 1
    
    # (5) Activity selection: activity is present iff at least one of its branches is selected
    for i, act in act_dict.items():
        if i != 0:
            branch_presences = [mdl.presence_of(x[M[b_id]]) for b_id in act.branches if b_id in M]
            if branch_presences:
                mdl.add(
                    mdl.presence_of(x[i]) == (mdl.sum(branch_presences) > 0)
                )
                info.nb_constraints += 1
    
    # (6) Resource limits (cumulative constraint)
    for v, capacity in enumerate(instance.resources):
        if capacity > 0:
            pulses = [
                mdl.pulse(x[act.id], act.requirements[v])
                for act in instance.activities 
                if act.requirements[v] > 0
            ]
            if pulses:
                mdl.add(mdl.sum(pulses) <= capacity)
                info.nb_constraints += 1
    
    return mdl, info


# =============================================================================
# SOLVER SECTION - Run solver and collect results
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
    - usePrecedenceEnergy=1 → PrecedenceInferenceLevel="Extended"
    - logLevel → LogVerbosity
    """
    # Map log level: OptalCP uses 0-3, CPO uses symbolic
    log_level = kwargs.get('log_level', 'Quiet')
    if isinstance(log_level, int):
        log_verbosity_map = {0: 'Quiet', 1: 'Terse', 2: 'Normal', 3: 'Verbose'}
        log_level = log_verbosity_map.get(log_level, 'Quiet')
    
    return {
        # Basic limits
        "TimeLimit": time_limit,
        "Workers": workers,
        
        # Search configuration (matching FDSLB behavior)
        "SearchType": "Restart",
        "FailureDirectedSearch": "On",
        
        # Inference levels (matching OptalCP propagation levels)
        "NoOverlapInferenceLevel": "Extended",
        "CumulFunctionInferenceLevel": "Extended",
        "PrecedenceInferenceLevel": "Extended",
        
        # Logging
        "LogVerbosity": log_level,
        "LogPeriod": 5000,
    }


def solve_instance(filepath: str, time_limit: int = 60, workers: int = 8, 
                   log_level: str = 'Quiet') -> dict:
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
    parser = argparse.ArgumentParser(description='Solve RCPSP-AS with IBM CP Optimizer')
    parser.add_argument('instances', nargs='+', help='Instance file(s) (.rcp format)')
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
