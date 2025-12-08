#!/usr/bin/env python3
"""
RCPSP-AS Solver using OptalCP

Solves Resource-Constrained Project Scheduling Problem with Alternative Subgraphs.

Usage:
    python solve_optal.py instance.rcp --timeLimit 60 --workers 8
    python solve_optal.py instance.rcp --searchType LNS --cumulPropagationLevel 2
"""

import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

import optalcp as cp

# Import shared config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DEFAULTS, OPTAL_PARAMS, add_common_args,
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

def build_model(data: dict, name: str) -> cp.Model:
    """Build RCPSP-AS model using OptalCP."""
    instance = data['instance']
    act_dict = data['act_dict']
    M = data['M']
    n = len(instance.activities)
    
    model = cp.Model()
    model.name = name
    
    # Variables: optional intervals for each activity
    x = {i: model.interval_var(name=f"T_{i}", optional=True, length=act.duration)
         for i, act in act_dict.items()}
    
    # Objective: minimize makespan
    model.minimize(x[n - 1].end())
    
    # Source is present
    model.add(x[0].presence() == 1)
    
    # Precedence (conditional)
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                model.add((x[act.id].presence() & x[j].presence()).implies(
                    x[act.id].end() <= x[j].start()))
    
    # Branch selection: exactly one branch per subgraph
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            branches = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if branches:
                model.add(model.sum(x[s].presence() for s in branches) == 
                         x[sub.principal_activity].presence())
    
    # Activity selection: present iff at least one branch selected
    for i, act in act_dict.items():
        if i != 0:
            branch_pres = [x[M[b]].presence() for b in act.branches if b in M]
            if branch_pres:
                model.add(x[i].presence() == (model.sum(branch_pres) > 0))
    
    # Resource capacity
    for v, cap in enumerate(instance.resources):
        if cap > 0:
            pulses = [x[act.id].pulse(height=act.requirements[v])
                     for act in instance.activities if act.requirements[v] > 0]
            if pulses:
                model.add(model.sum(pulses) <= cap)
    
    return model


# =============================================================================
# SOLVER SECTION
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
    parser = argparse.ArgumentParser(description='Solve RCPSP-AS with OptalCP')
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