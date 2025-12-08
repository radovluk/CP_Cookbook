#!/usr/bin/env python3
"""
Universal Benchmark Runner

Compares OptalCP vs IBM CP Optimizer on constraint programming problems.
Automatically discovers problem directories and their solver scripts.

Usage:
    python run.py rcpsp-tt                          # Run all instances
    python run.py rcpsp-tt --max 5                  # Run 5 instances
    python run.py rcpsp-as --timeLimit 120          # 2 min per instance
    python run.py rcpsp-tt --solver optal           # Only OptalCP
    python run.py rcpsp-tt --data /path/to/data     # Custom data path
"""

import os
import subprocess
import glob
import json
import sys
import time as time_module
import argparse
from pathlib import Path

# =============================================================================
# CONFIGURATION DEFAULTS
# =============================================================================

DEFAULT_PYTHON = os.environ.get("SOLVER_PYTHON", sys.executable)
DEFAULT_TIME_LIMIT = 60
DEFAULT_WORKERS = 8
DEFAULT_LOG_LEVEL = 0

# Problem-specific data patterns and paths (relative to script or problem dir)
PROBLEM_CONFIG = {
    "rcpsp-tt": {
        "data_paths": [
            "../../data/rcpsptt/rcpsp_tt_instances",
            "../data/rcpsptt/rcpsp_tt_instances",
            "data/rcpsptt/rcpsp_tt_instances",
        ],
        "patterns": ["j30*.sm", "j60*.sm", "j90*.sm"],
        "extension": ".sm",
    },
    "rcpsp-as": {
        "data_paths": [
            "../../data/rcpspas/ASLIB/ASLIB0",
            "../data/rcpspas",
            "data/rcpspas",
        ],
        "patterns": ["*.rcp", "*/*.rcp", "*/*/*.rcp", "*.RCP", "*/*.RCP", "*/*/*.RCP"],
        "extension": ".RCP",
    },
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def run_command(cmd, cwd=None, timeout=None, quiet=False):
    """Run a shell command and return the result."""
    if not quiet:
        cmd_display = cmd[:100] + "..." if len(cmd) > 100 else cmd
        print(f"  Running: {cmd_display}")
    
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            if not quiet:
                print(f"    stdout: {result.stdout[:500]}" if result.stdout else "")
                print(f"    stderr: {result.stderr[:500]}" if result.stderr else "")
        return result
    except subprocess.TimeoutExpired:
        if not quiet:
            print(f"    Timed out after {timeout}s")
        raise


def find_data_dir(problem_dir, config, custom_path=None):
    """Find the data directory for a problem."""
    if custom_path and os.path.exists(custom_path):
        return custom_path
    
    candidates = []
    for rel_path in config.get("data_paths", []):
        candidates.append(os.path.join(problem_dir, rel_path))
    
    for candidate in candidates:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    
    return None


def collect_instances(data_dir, config):
    """Collect instances based on problem configuration."""
    instances = []
    patterns = config.get("patterns", ["*" + config.get("extension", "")])
    
    for pattern in patterns:
        found = glob.glob(os.path.join(data_dir, pattern), recursive=True)
        instances.extend(found)
    
    # Also walk directory for extension
    ext = config.get("extension")
    if ext:
        for root, _, files in os.walk(data_dir):
            for f in files:
                if f.endswith(ext):
                    instances.append(os.path.join(root, f))
    
    return sorted(set(instances))


def run_solver_batched(solver_script, instances, results_file, python_path,
                       time_limit, workers, log_level, solver_name, batch_size=20):
    """Run solver on instances in batches."""
    all_results = []
    total_batches = (len(instances) + batch_size - 1) // batch_size
    
    # Convert log level based on solver
    if solver_name == "cpo":
        log_level_map = {0: 'Quiet', 1: 'Terse', 2: 'Normal', 3: 'Verbose'}
        log_arg = log_level_map.get(log_level, 'Quiet')
    else:
        log_arg = log_level
    
    for batch_start in range(0, len(instances), batch_size):
        batch = instances[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        
        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} instances)")
        
        instance_args = ' '.join(f'"{inst}"' for inst in batch)
        batch_output = results_file.replace('.json', f'-batch{batch_num}.json')
        batch_timeout = len(batch) * (time_limit + 10) + 60
        
        cmd = (f'{python_path} "{solver_script}" {instance_args} '
               f'--timeLimit {time_limit} --workers {workers} '
               f'--output "{batch_output}" --logLevel {log_arg}')
        
        try:
            run_command(cmd, timeout=batch_timeout)
            if os.path.exists(batch_output):
                with open(batch_output, 'r') as f:
                    batch_results = json.load(f)
                    all_results.extend(batch_results)
                os.remove(batch_output)
                
                solved = sum(1 for r in batch_results if r.get('objective') is not None)
                errors = sum(1 for r in batch_results if 'error' in r)
                print(f"    Solved: {solved}/{len(batch)}, Errors: {errors}")
                
        except subprocess.CalledProcessError as e:
            print(f"    Error: {e}")
        except subprocess.TimeoutExpired:
            print(f"    Batch timed out")
    
    return all_results


def print_summary(results, solver_name):
    """Print summary statistics."""
    if not results:
        print(f"  {solver_name}: No results")
        return
    
    total = len(results)
    errors = [r for r in results if 'error' in r]
    successful = [r for r in results if 'error' not in r and r.get('objective') is not None]
    proven = [r for r in successful if r.get('proof', False)]
    
    print(f"\n  {solver_name}:")
    print(f"    Total: {total}, Solved: {len(successful)} ({100*len(successful)/total:.1f}%)")
    print(f"    Proven optimal: {len(proven)} ({100*len(proven)/total:.1f}%), Errors: {len(errors)}")
    
    if successful:
        times = [r.get('duration', 0) for r in successful]
        print(f"    Avg time: {sum(times)/len(times):.2f}s, Max: {max(times):.2f}s")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Universal CP Benchmark Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py rcpsp-tt                     # Run all RCPSP-TT instances
  python run.py rcpsp-as --max 10            # Run first 10 RCPSP-AS instances
  python run.py rcpsp-tt --solver optal      # Run only OptalCP
  python run.py rcpsp-tt --timeLimit 120     # 2 minutes per instance
  python run.py rcpsp-tt --data /path/data   # Custom data directory
        """
    )
    
    # Required
    parser.add_argument('problem', help='Problem directory name (e.g., rcpsp-tt, rcpsp-as)')
    
    # Optional
    parser.add_argument('--max', type=int, default=None,
                        help='Maximum instances to run (default: all)')
    parser.add_argument('--timeLimit', type=int, default=DEFAULT_TIME_LIMIT,
                        help=f'Time limit per instance in seconds (default: {DEFAULT_TIME_LIMIT})')
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
                        help=f'Number of parallel workers (default: {DEFAULT_WORKERS})')
    parser.add_argument('--logLevel', type=int, default=DEFAULT_LOG_LEVEL, choices=[0, 1, 2, 3],
                        help='Log verbosity 0-3 (default: 0)')
    parser.add_argument('--solver', choices=['optal', 'cpo', 'both'], default='both',
                        help='Which solver(s) to run (default: both)')
    parser.add_argument('--python', default=DEFAULT_PYTHON,
                        help=f'Python interpreter path (default: {DEFAULT_PYTHON})')
    parser.add_argument('--data', default=None,
                        help='Custom data directory path')
    parser.add_argument('--output', default=None,
                        help='Custom output directory (default: <problem>/results)')
    parser.add_argument('--no-compare', action='store_true',
                        help='Skip comparison report generation')
    
    args = parser.parse_args()
    
    start_time = time_module.time()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    problem_dir = os.path.join(base_dir, args.problem)
    
    # Validate problem directory
    if not os.path.isdir(problem_dir):
        print(f"Error: Problem directory '{args.problem}' not found")
        print(f"Available: {[d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and not d.startswith('.')]}")
        return 1
    
    # Get problem config
    config = PROBLEM_CONFIG.get(args.problem, {
        "data_paths": ["../../data", "../data", "data"],
        "patterns": ["*.*"],
        "extension": None,
    })
    
    # Find data directory
    data_dir = find_data_dir(problem_dir, config, args.data)
    if not data_dir:
        print(f"Error: Data directory not found for '{args.problem}'")
        print(f"Tried paths relative to {problem_dir}:")
        for p in config.get("data_paths", []):
            print(f"  - {p}")
        print("Use --data to specify a custom path")
        return 1
    
    # Setup output directory
    results_dir = args.output or os.path.join(problem_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    
    # Find solver scripts
    solve_optal = os.path.join(problem_dir, "solve_optal.py")
    solve_cpo = os.path.join(problem_dir, "solve_cpo.py")
    
    has_optal = os.path.exists(solve_optal)
    has_cpo = os.path.exists(solve_cpo)
    
    if not has_optal and not has_cpo:
        print(f"Error: No solver scripts found in {problem_dir}")
        print("Expected: solve_optal.py and/or solve_cpo.py")
        return 1
    
    # Collect instances
    instances = collect_instances(data_dir, config)
    if not instances:
        print(f"No instances found in {data_dir}")
        return 1
    
    total_available = len(instances)
    if args.max:
        instances = instances[:args.max]
    
    # Print configuration
    print("=" * 70)
    print(f"Benchmark: {args.problem.upper()}")
    print("=" * 70)
    print(f"  Python:     {args.python}")
    print(f"  Data:       {data_dir}")
    print(f"  Output:     {results_dir}")
    print(f"  Time limit: {args.timeLimit}s")
    print(f"  Workers:    {args.workers}")
    print(f"  Instances:  {len(instances)}" + (f" (of {total_available})" if args.max else ""))
    print(f"  Solvers:    {args.solver}")
    
    estimated = len(instances) * args.timeLimit * (2 if args.solver == 'both' else 1) / 60
    print(f"  Est. time:  ~{estimated:.1f} min (worst case)")
    print("=" * 70)
    
    optal_results = []
    cpo_results = []
    
    # Run OptalCP
    if args.solver in ('optal', 'both') and has_optal:
        print(f"\n{'=' * 70}")
        print("Running OptalCP")
        print("=" * 70)
        
        optal_file = os.path.join(results_dir, "optalcp-results.json")
        optal_results = run_solver_batched(
            solve_optal, instances, optal_file,
            args.python, args.timeLimit, args.workers, args.logLevel, "optal"
        )
        
        with open(optal_file, 'w') as f:
            json.dump(optal_results, f, indent=2)
        print(f"\nSaved: {optal_file}")
    
    # Run CPO
    if args.solver in ('cpo', 'both') and has_cpo:
        print(f"\n{'=' * 70}")
        print("Running IBM CP Optimizer")
        print("=" * 70)
        
        cpo_file = os.path.join(results_dir, "cpo-results.json")
        cpo_results = run_solver_batched(
            solve_cpo, instances, cpo_file,
            args.python, args.timeLimit, args.workers, args.logLevel, "cpo"
        )
        
        with open(cpo_file, 'w') as f:
            json.dump(cpo_results, f, indent=2)
        print(f"\nSaved: {cpo_file}")
    
    # Generate comparison
    if not args.no_compare and optal_results and cpo_results:
        print(f"\n{'=' * 70}")
        print("Generating Comparison Report")
        print("=" * 70)
        
        compare_tool = os.path.join(base_dir, "compare/compare.mjs")
        comparison_dir = os.path.join(results_dir, "comparison")
        
        if os.path.exists(compare_tool):
            optal_file = os.path.join(results_dir, "optalcp-results.json")
            cpo_file = os.path.join(results_dir, "cpo-results.json")
            
            cmd = (f'node "{compare_tool}" "{args.problem.upper()} Benchmark" '
                   f'"OptalCP" "{optal_file}" '
                   f'"IBM CP Optimizer" "{cpo_file}" '
                   f'"{comparison_dir}"')
            
            try:
                run_command(cmd, cwd=base_dir)
                print(f"Report: {comparison_dir}/main.html")
            except Exception as e:
                print(f"Comparison failed: {e}")
        else:
            print(f"Compare tool not found: {compare_tool}")
    
    # Summary
    elapsed = time_module.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"Complete! ({elapsed/60:.1f} min)")
    print("=" * 70)
    
    if optal_results:
        print_summary(optal_results, "OptalCP")
    if cpo_results:
        print_summary(cpo_results, "IBM CP Optimizer")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
