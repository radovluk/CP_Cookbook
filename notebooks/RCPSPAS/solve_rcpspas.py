#!/usr/bin/env python3
"""
RCPSP-AS Solver using OptalCP
Based on the simplified formulation from Servranckx & Vanhoucke (2019)

Usage:
    python solve_rcpspas.py <instance_path> [options]

Example:
    python solve_rcpspas.py ../../data/rcpspas/ASLIB/ASLIB0/aslib0_25678a.RCP --time-limit 60

    # Using Kubernetes cluster:
    python solve_rcpspas.py instance.RCP --k8s ./optalcp-k8s -w 16
"""

import argparse
import os
import sys
from pathlib import Path

import optalcp as cp
from ascp.load_instance import load_instance


def configure_solver(solver_path=None):
    """Configure OptalCP to use a custom solver (e.g., K8s cluster)."""
    if solver_path:
        solver_path = Path(solver_path).resolve()
        if not solver_path.exists():
            print(f"Warning: Solver path does not exist: {solver_path}", file=sys.stderr)
        os.environ["OPTALCP_SOLVER"] = str(solver_path)
        print(f"OPTALCP_SOLVER set to: {os.environ['OPTALCP_SOLVER']}")


def create_model(instance):
    """Create OptalCP model for RCPSP-AS instance."""

    # Create dictionary mapping activity IDs to objects
    act_dict = {act.id: act for act in instance.activities}

    # Build set of branching arcs (from principal activities to their successors)
    branching_arcs = {
        (sub.principal_activity, s)
        for sub in instance.subgraphs if sub.principal_activity in act_dict
        for s in act_dict[sub.principal_activity].successors if s in act_dict
    }

    # Create model
    mdl = cp.Model()

    # (7) Create optional interval variable for each activity
    x = {i: mdl.interval_var(
        name=f"T_{i}", optional=True, length=act.duration)
        for i, act in act_dict.items()}

    # (1) Minimize makespan
    mdl.minimize(x[len(instance.activities) - 1].end())

    # (2) Source activity is present
    mdl.enforce(x[0].presence() == 1)

    # (3) Selection propagation along A_prop (non-branching arcs)
    for act in instance.activities:
        for j in act.successors:
            if j in x and (act.id, j) not in branching_arcs:
                mdl.enforce(x[act.id].presence().implies(x[j].presence()))

    # (4) Branch selection for each subgraph
    for sub in instance.subgraphs:
        if sub.principal_activity in act_dict:
            successors = [s for s in act_dict[sub.principal_activity].successors if s in x]
            if successors:
                mdl.enforce(sum(x[s].presence() for s in successors) ==
                           x[sub.principal_activity].presence())

    # (5) Precedence timing for all arcs
    for act in instance.activities:
        for j in act.successors:
            if j in x:
                mdl.enforce((x[act.id].presence() & x[j].presence()).implies(
                    x[act.id].end() <= x[j].start()))

    # (6) Resource capacity constraints
    for v, capacity in enumerate(instance.resources):
        if capacity > 0:
            pulses = [x[act.id].pulse(height=act.requirements[v])
                     for act in instance.activities if act.requirements[v] > 0]
            if pulses:
                mdl.enforce(mdl.sum(pulses) <= capacity)

    return mdl


def get_parameters(nb_workers=8, time_limit=100, log_level=2, log_period=5):
    """Create OptalCP parameters optimized for proving optimality."""

    params = cp.Parameters()

    # Basic settings
    params["nbWorkers"] = nb_workers
    params["timeLimit"] = time_limit
    params["logLevel"] = log_level
    params["logPeriod"] = log_period

    # Propagation levels
    params["cumulPropagationLevel"] = 3
    params["usePrecedenceEnergy"] = 1
    params["positionPropagationLevel"] = 3
    params["reservoirPropagationLevel"] = 2

    # Lower bound computation
    params["simpleLBShavingRounds"] = 5
    params["simpleLBMaxIterations"] = 2147483647

    # Worker configuration
    lns_worker = {"searchType": "LNS"}

    fds_worker = {
        "searchType": "FDS",
        "cumulPropagationLevel": 3,
        "positionPropagationLevel": 3
    }

    fdslb_worker = {
        "searchType": "FDSDual",
        "cumulPropagationLevel": 3,
        "positionPropagationLevel": 3
    }

    # Distribution: 2 LNS, 2 FDS, 4 FDSDual
    params["workers"] = [
        lns_worker, lns_worker,
        fds_worker, fds_worker,
        fdslb_worker, fdslb_worker, fdslb_worker, fdslb_worker,
    ]

    return params


def solve(instance_path, nb_workers=8, time_limit=100, log_level=2, log_period=5):
    """
    Solve RCPSP-AS instance.

    Returns:
        dict with keys: 'instance', 'objective', 'lower_bound', 'optimal', 'duration'
    """
    instance = load_instance(str(instance_path))
    mdl = create_model(instance)
    params = get_parameters(nb_workers, time_limit, log_level, log_period)

    result = mdl.solve(parameters=params)

    return {
        'instance': instance.name,
        'objective': result.objective if result.objective is not None else None,
        'lower_bound': result.lower_bound if hasattr(result, 'lower_bound') else None,
        'optimal': result.proof if hasattr(result, 'proof') else False,
        'duration': result.duration if hasattr(result, 'duration') else None,
        'result': result
    }


def main():
    parser = argparse.ArgumentParser(
        description='Solve RCPSP-AS instance using OptalCP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python solve_rcpspas.py instance.RCP
    python solve_rcpspas.py instance.RCP --time-limit 300 --workers 4
    python solve_rcpspas.py instance.RCP --quiet

    # Using Kubernetes cluster:
    python solve_rcpspas.py instance.RCP --k8s ./optalcp-k8s -w 16 -t 100
        """
    )
    parser.add_argument('instance', type=Path, help='Path to .RCP instance file')
    parser.add_argument('--time-limit', '-t', type=int, default=100,
                        help='Time limit in seconds (default: 100)')
    parser.add_argument('--workers', '-w', type=int, default=8,
                        help='Number of workers (default: 8)')
    parser.add_argument('--log-level', '-l', type=int, default=2, choices=[0, 1, 2, 3],
                        help='Log verbosity 0-3 (default: 2)')
    parser.add_argument('--log-period', type=int, default=5,
                        help='Log period in seconds (default: 5)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Quiet mode (only print final result)')
    parser.add_argument('--k8s', '--solver', type=Path, dest='solver',
                        help='Path to custom solver (e.g., optalcp-k8s for K8s cluster)')

    args = parser.parse_args()

    if not args.instance.exists():
        print(f"Error: Instance file not found: {args.instance}", file=sys.stderr)
        sys.exit(1)

    # Configure K8s/custom solver if specified
    if args.solver:
        configure_solver(args.solver)

    log_level = 0 if args.quiet else args.log_level

    result = solve(
        args.instance,
        nb_workers=args.workers,
        time_limit=args.time_limit,
        log_level=log_level,
        log_period=args.log_period
    )

    print(f"\n{'='*60}")
    print(f"Instance: {result['instance']}")
    print(f"Objective: {result['objective']}")
    print(f"Lower Bound: {result['lower_bound']}")
    print(f"Optimal: {result['optimal']}")
    print(f"Duration: {result['duration']:.2f}s" if result['duration'] else "Duration: N/A")
    print(f"{'='*60}")

    return result


if __name__ == '__main__':
    main()
