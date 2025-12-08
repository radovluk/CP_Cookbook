#!/usr/bin/env python3
"""
RCPSP-AS Solver using IBM CP Optimizer

Solves Resource-Constrained Project Scheduling Problem with Alternative Subgraphs.

Usage:
    python solve_cpo.py instance.rcp --timeLimit 60 --workers 8
    python solve_cpo.py instance.rcp --SearchType DepthFirst --NoOverlapInferenceLevel Medium
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

# RCPSP-AS parser (add ascp to path)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../notebooks/RCPSPAS"))
from ascp.load_instance import load_instance


# =============================================================================
# PARSER SECTION
# =============================================================================

def parse_instance(filepath: str) -> dict:
    """Parse RCPSP-AS instance using ascp package."""
    instance = load_instance(filepath)
    act_dict = {act.id: act for act in instance.activities}
    
    # Build branch-to-branching-activity map
    M = {
        branch_id: b_k_act_id
        for sub in instance.subgraphs if sub.principal_activity in act_dict
        for b_k_act_id in act_dict[sub.principal_activity].successors if b_k_act_id in act_dict
        for branch_id in act_dict[b_k_act_id].branches.intersection(sub.branches) if branch_id != 0
    }
    M[0] = 0  # Dummy branch
    
    return {'instance': instance, 'act_dict': act_dict, 'M': M}


# =============================================================================
# MODEL SECTION
# =============================================================================

def build_model(data: dict, name: str) -> tuple:
    """Build RCPSP-AS model using CPO. Returns (model, info)."""
    instance = data['instance']
    act_dict = data['act_dict']
    M = data['M']
    n = len(instance.activities)
    
    mdl = CpoModel(name=name)
    info = {"nb_int_vars": 0, "nb_interval_vars": 0, "nb_constraints": 0}
    
    # Variables: optional intervals for each activity
    x = {i: mdl.interval_var(name=f"T_{i}", optional=True, size=act.duration)
         for i, act in act_dict.items()}
    info["nb_interval_vars"] = len(x)
    
    # Objective: minimize makespan
    mdl.add(mdl.minimize(mdl.end_of(x[n - 1])))
    info["nb_constraints"] += 1
    
    # Source is present
    mdl.add(mdl.presence_of(x[0]) == 1)
    info["nb_constraints"] += 1
    
    # Precedence (conditional)
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                mdl.add(mdl.if_then(
                    mdl.presence_of(x[act.id]) & mdl.presence_of(x[j]),
                    mdl.end_of(x[act.id]) <= mdl.start_of(x[j])))
                info["nb_constraints"] += 1
    
    # Branch selection: exactly one branch per subgraph
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            branches = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if branches:
                mdl.add(mdl.sum(mdl.presence_of(x[s]) for s in branches) ==
                       mdl.presence_of(x[sub.principal_activity]))
                info["nb_constraints"] += 1
    
    # Activity selection: present iff at least one branch selected
    for i, act in act_dict.items():
        if i != 0:
            branch_pres = [mdl.presence_of(x[M[b]]) for b in act.branches if b in M]
            if branch_pres:
                mdl.add(mdl.presence_of(x[i]) == (mdl.sum(branch_pres) > 0))
                info["nb_constraints"] += 1
    
    # Resource capacity
    for v, cap in enumerate(instance.resources):
        if cap > 0:
            pulses = [mdl.pulse(x[act.id], act.requirements[v])
                     for act in instance.activities if act.requirements[v] > 0]
            if pulses:
                mdl.add(mdl.sum(pulses) <= cap)
                info["nb_constraints"] += 1
    
    return mdl, info


# =============================================================================
# SOLVER SECTION
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
    parser = argparse.ArgumentParser(description='Solve RCPSP-AS with IBM CP Optimizer')
    add_common_args(parser)
    add_solver_args(parser, CPO_PARAMS)
    args = parser.parse_args()
    
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