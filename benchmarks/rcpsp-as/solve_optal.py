#!/usr/bin/env python3
"""
RCPSP-AS Solver using OptalCP (Python API)

This script solves Resource-Constrained Project Scheduling Problem with 
Alternative Subgraphs (RCPSP-AS) instances and outputs results in JSON format
for benchmarking comparisons.

Usage:
    python solve_optal_rcpspas.py <instance.rcp> [--timeLimit 60] [--workers 8] [--output results.json]

Structure:
    1. PARSER SECTION - Parse instance files using ascp package
    2. MODEL SECTION - Build CP model for RCPSP-AS
    3. SOLVER SECTION - Run solver and collect results
"""

import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# OptalCP Python API
import optalcp as cp

# Add the ascp package directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../notebooks/RCPSPAS"))

# ASCP package for parsing RCPSP-AS instances
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
# MODEL SECTION - Build RCPSP-AS model using OptalCP
# =============================================================================

def build_model(data: dict, model_name: str) -> cp.Model:
    """
    Build the RCPSP-AS model using OptalCP Python API.
    
    The model formulation:
    (1) Minimize makespan: end of sink activity
    (2) Source activity is present
    (3) Precedence relations (conditional on both activities being present)
    (4) Subgraph branch selection: exactly one branch per subgraph
    (5) Activity selection: activity is present iff at least one of its branches is selected
    (6) Resource limits: cumulative constraint on renewable resources
    (7) Variables: optional interval variables for each activity
    
    Returns: OptalCP Model object
    """
    instance = data['instance']
    act_dict = data['act_dict']
    M = data['M']
    
    n_activities = len(instance.activities)
    
    # Create model
    model = cp.Model()
    model.name = model_name
    
    # =========================================================================
    # Variables
    # =========================================================================
    
    # (7) Create optional interval variable for each activity i with a fixed duration d_i
    x = {i: model.interval_var(
        name=f"T_{i}", 
        optional=True, 
        length=act.duration
    ) for i, act in act_dict.items()}
    
    # =========================================================================
    # Constraints
    # =========================================================================
    
    # (1) Minimize makespan (end time of the sink activity)
    model.minimize(x[n_activities - 1].end())
    
    # (2) Source activity is present
    model.add(x[0].presence() == 1)
    
    # (3) Precedence relations - conditional on both activities being present
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                model.add(
                    (x[act.id].presence() & x[j].presence()).implies(
                        x[act.id].end() <= x[j].start()
                    )
                )
    
    # (4) Subgraph branch selection: exactly one branch per subgraph when principal is present
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            branches = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if branches:
                model.add(
                    model.sum(x[s].presence() for s in branches) == 
                    x[sub.principal_activity].presence()
                )
    
    # (5) Activity selection: activity is present iff at least one of its branches is selected
    for i, act in act_dict.items():
        if i != 0:
            branch_presences = [x[M[b_id]].presence() for b_id in act.branches if b_id in M]
            if branch_presences:
                model.add(
                    x[i].presence() == (model.sum(branch_presences) > 0)
                )
    
    # (6) Resource limits (cumulative constraint)
    for v, capacity in enumerate(instance.resources):
        if capacity > 0:
            pulses = [
                x[act.id].pulse(height=act.requirements[v])
                for act in instance.activities 
                if act.requirements[v] > 0
            ]
            if pulses:
                model.add(model.sum(pulses) <= capacity)
    
    return model


# =============================================================================
# SOLVER SECTION - Run solver and collect results
# =============================================================================

def get_solver_parameters(time_limit: int, workers: int, **kwargs) -> cp.Parameters:
    """
    Returns solver Parameters object.
    
    Parameter mapping (OptalCP → CPO equivalent):
    - timeLimit → TimeLimit (seconds)
    - nbWorkers → Workers
    - searchType="FDSLB" → SearchType="Restart" + FailureDirectedSearch="On"
    - noOverlapPropagationLevel=4 → NoOverlapInferenceLevel="Extended"
    - cumulPropagationLevel=3 → CumulFunctionInferenceLevel="Extended"
    - usePrecedenceEnergy=1 → PrecedenceInferenceLevel="Extended"
    - logLevel (0-3) → LogVerbosity ("Quiet"/"Terse"/"Normal"/"Verbose")
    """
    return cp.Parameters(
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
    parser = argparse.ArgumentParser(description='Solve RCPSP-AS with OptalCP')
    parser.add_argument('instances', nargs='+', help='Instance file(s) (.rcp format)')
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
