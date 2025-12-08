#!/usr/bin/env python3
"""
RCPSP-TT Benchmark Runner

Compares OptalCP (Python) vs IBM CP Optimizer (Python/DOcplex) on RCPSP-TT instances.
Runs all j30x, j60x, j90x instance sets with configurable time limit per instance.

Configuration:
    - SOLVER_PYTHON: Path to Python with both OptalCP and DOcplex installed
    - TIME_LIMIT: Seconds per instance (default 60)
    - WORKERS: Number of parallel workers (default 8)

Usage:
    python run_benchmark_python.py                 # Run all instances
    python run_benchmark_python.py --max 1         # Run only 1 instance (test mode)
    python run_benchmark_python.py --max 10        # Run first 10 instances
"""

import os
import subprocess
import glob
import json
import sys
import time as time_module
import argparse

# =============================================================================
# CONFIGURATION - Adjust these for your environment
# =============================================================================

# Path to Python with both OptalCP and DOcplex installed
SOLVER_PYTHON = "/home/lukas/optacp/bin/python3"

# Benchmark parameters
TIME_LIMIT = 5   # seconds per instance
WORKERS = 8       # parallel workers
LOG_LEVEL = 0     # 0=quiet, 1=terse, 2=normal, 3=verbose (converted per solver)

# =============================================================================
# RUNNER CODE
# =============================================================================

def run_command(cmd, cwd=None, check=True, timeout=None):
    """Run a shell command and return the result."""
    cmd_display = cmd[:100] + "..." if len(cmd) > 100 else cmd
    print(f"  Running: {cmd_display}")
    
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        if check and result.returncode != 0:
            print(f"    stdout: {result.stdout[:500]}" if result.stdout else "")
            print(f"    stderr: {result.stderr[:500]}" if result.stderr else "")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        return result
    except subprocess.TimeoutExpired:
        print(f"    Command timed out after {timeout}s")
        raise


def collect_instances(data_dir):
    """Collect all RCPSP-TT instances from j30x, j60x, j90x sets."""
    instances = []
    
    # Try multiple naming patterns
    patterns = [
        "j30*.sm",   # j301_a.sm, j3010_a.sm, etc.
        "j60*.sm",   # j601_a.sm, j6010_a.sm, etc.
        "j90*.sm",   # j901_a.sm, j9010_a.sm, etc.
    ]
    
    for pattern in patterns:
        found = glob.glob(os.path.join(data_dir, pattern))
        instances.extend(found)
    
    # Remove duplicates and sort
    instances = sorted(set(instances))
    
    return instances


def categorize_instances(instances):
    """Group instances by problem size."""
    categories = {'j30': [], 'j60': [], 'j90': [], 'other': []}
    
    for inst in instances:
        basename = os.path.basename(inst)
        if basename.startswith('j30'):
            categories['j30'].append(inst)
        elif basename.startswith('j60'):
            categories['j60'].append(inst)
        elif basename.startswith('j90'):
            categories['j90'].append(inst)
        else:
            categories['other'].append(inst)
    
    return categories


def run_solver_batched(solver_script, instances, results_file, python_path, 
                       time_limit, workers, log_level, solver_name="solver", batch_size=20):
    """Run solver on instances in batches to avoid command line limits."""
    all_results = []
    total_batches = (len(instances) + batch_size - 1) // batch_size
    
    # Convert log level based on solver
    if solver_name == "cpo":
        # CPO uses string log levels
        log_level_map = {0: 'Quiet', 1: 'Terse', 2: 'Normal', 3: 'Verbose'}
        log_arg = log_level_map.get(log_level, 'Quiet')
    else:
        # OptalCP uses numeric log levels
        log_arg = log_level
    
    for batch_start in range(0, len(instances), batch_size):
        batch = instances[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        
        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} instances)")
        
        instance_args = ' '.join(f'"{inst}"' for inst in batch)
        batch_output = results_file.replace('.json', f'-batch{batch_num}.json')
        
        # Calculate timeout: time_limit per instance + overhead
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
                os.remove(batch_output)  # Clean up
                
                # Progress report
                solved = sum(1 for r in batch_results if r.get('objective') is not None)
                errors = sum(1 for r in batch_results if 'error' in r)
                print(f"    Solved: {solved}/{len(batch)}, Errors: {errors}")
                
        except subprocess.CalledProcessError as e:
            print(f"    Error in batch {batch_num}: {e}")
        except subprocess.TimeoutExpired:
            print(f"    Batch {batch_num} timed out")
    
    return all_results


def print_summary(results, solver_name):
    """Print summary statistics for solver results."""
    if not results:
        print(f"  {solver_name}: No results")
        return
    
    total = len(results)
    errors = [r for r in results if 'error' in r]
    successful = [r for r in results if 'error' not in r and r.get('objective') is not None]
    proven = [r for r in successful if r.get('proof', False)]
    
    print(f"\n  {solver_name}:")
    print(f"    Total instances: {total}")
    print(f"    Solutions found: {len(successful)} ({100*len(successful)/total:.1f}%)")
    print(f"    Proven optimal: {len(proven)} ({100*len(proven)/total:.1f}%)")
    print(f"    Errors: {len(errors)}")
    
    if successful:
        times = [r.get('duration', 0) for r in successful]
        avg_time = sum(times) / len(times)
        max_time = max(times)
        print(f"    Avg solve time: {avg_time:.2f}s")
        print(f"    Max solve time: {max_time:.2f}s")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='RCPSP-TT Benchmark Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_benchmark_python.py                 # Run all instances
  python run_benchmark_python.py --max 1         # Test mode: run only 1 instance
  python run_benchmark_python.py --max 10        # Run first 10 instances
  python run_benchmark_python.py --max 5 --timeLimit 30  # 5 instances, 30s each
        """
    )
    parser.add_argument('--max', type=int, default=None,
                        help='Maximum number of instances to run (default: all)')
    parser.add_argument('--timeLimit', type=int, default=TIME_LIMIT,
                        help=f'Time limit per instance in seconds (default: {TIME_LIMIT})')
    parser.add_argument('--workers', type=int, default=WORKERS,
                        help=f'Number of parallel workers (default: {WORKERS})')
    args = parser.parse_args()
    
    start_time = time_module.time()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "../../data/rcpsptt/rcpsp_tt_instances")
    results_dir = os.path.join(base_dir, "results")
    
    os.makedirs(results_dir, exist_ok=True)

    # =========================================================================
    # Collect all instances
    # =========================================================================
    instances = collect_instances(data_dir)
    
    if not instances:
        print(f"No instances found in {data_dir}")
        print("Expected files matching: j30*.sm, j60*.sm, j90*.sm")
        if os.path.exists(data_dir):
            files = os.listdir(data_dir)[:10]
            print(f"Sample files in directory: {files}")
        return

    # Apply max instances limit if specified
    total_available = len(instances)
    if args.max is not None:
        instances = instances[:args.max]
        print(f"\n*** TEST MODE: Limited to {args.max} instance(s) ***\n")

    categories = categorize_instances(instances)
    
    print("="*70)
    print("RCPSP-TT Benchmark Runner")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Python: {SOLVER_PYTHON}")
    print(f"  Time limit: {args.timeLimit}s per instance")
    print(f"  Workers: {args.workers}")
    if args.max is not None:
        print(f"  Max instances: {args.max} (of {total_available} available)")
    print(f"\nInstances to run: {len(instances)}")
    print(f"  j30x (30 jobs): {len(categories['j30'])}")
    print(f"  j60x (60 jobs): {len(categories['j60'])}")
    print(f"  j90x (90 jobs): {len(categories['j90'])}")
    if categories['other']:
        print(f"  other: {len(categories['other'])}")
    
    estimated_time = len(instances) * args.timeLimit * 2 / 60  # 2 solvers
    print(f"\nEstimated time: ~{estimated_time:.1f} minutes (worst case)")
    print("="*70)

    # =========================================================================
    # 1. Run OptalCP Benchmarks
    # =========================================================================
    print("\n" + "="*70)
    print("Running OptalCP Benchmarks")
    print("="*70)
    
    optalcp_results_file = os.path.join(results_dir, "optalcp-results-full.json")
    solve_optal_script = os.path.join(base_dir, "solve_optal.py")
    
    optal_results = []
    if not os.path.exists(solve_optal_script):
        print(f"WARNING: solve_optal.py not found at {solve_optal_script}")
        print("Skipping OptalCP benchmarks")
    else:
        optal_results = run_solver_batched(
            solve_optal_script, instances, optalcp_results_file,
            SOLVER_PYTHON, args.timeLimit, args.workers, LOG_LEVEL, solver_name="optal"
        )
    
    with open(optalcp_results_file, 'w') as f:
        json.dump(optal_results, f, indent=2)
    print(f"\nOptalCP results saved to {optalcp_results_file}")

    # =========================================================================
    # 2. Run IBM CP Optimizer Benchmarks
    # =========================================================================
    print("\n" + "="*70)
    print("Running IBM CP Optimizer Benchmarks")
    print("="*70)
    
    cpo_results_file = os.path.join(results_dir, "cpo-results-full.json")
    solve_cpo_script = os.path.join(base_dir, "solve_cpo.py")
    
    cpo_results = []
    if not os.path.exists(solve_cpo_script):
        print(f"WARNING: solve_cpo.py not found at {solve_cpo_script}")
        print("Skipping CPO benchmarks")
    else:
        cpo_results = run_solver_batched(
            solve_cpo_script, instances, cpo_results_file,
            SOLVER_PYTHON, args.timeLimit, args.workers, LOG_LEVEL, solver_name="cpo"
        )
    
    with open(cpo_results_file, 'w') as f:
        json.dump(cpo_results, f, indent=2)
    print(f"\nCPO results saved to {cpo_results_file}")

    # =========================================================================
    # 3. Generate Comparison Report
    # =========================================================================
    print("\n" + "="*70)
    print("Generating Comparison Report")
    print("="*70)
    
    comparison_dir = os.path.join(results_dir, "comparison-report")
    compare_tool = os.path.join(base_dir, "../compare/compare.mjs")
    
    if os.path.exists(compare_tool):
        cmd = (f'node "{compare_tool}" "RCPSP-TT Benchmark (j30/j60/j90)" '
               f'"OptalCP" "{optalcp_results_file}" '
               f'"IBM CP Optimizer" "{cpo_results_file}" '
               f'"{comparison_dir}"')
        
        try:
            run_command(cmd, cwd=base_dir)
            print(f"\nComparison report: {comparison_dir}/main.html")
        except subprocess.CalledProcessError as e:
            print(f"Error generating comparison: {e}")
    else:
        print(f"Compare tool not found at {compare_tool}")

    # =========================================================================
    # Summary
    # =========================================================================
    elapsed = time_module.time() - start_time
    
    print("\n" + "="*70)
    print("Benchmark Complete!")
    print("="*70)
    print(f"\nTotal time: {elapsed/60:.1f} minutes")
    
    print_summary(optal_results, "OptalCP")
    print_summary(cpo_results, "IBM CP Optimizer")
    
    print(f"\nOutput files:")
    print(f"  OptalCP: {optalcp_results_file}")
    print(f"  CPO: {cpo_results_file}")
    if os.path.exists(os.path.join(comparison_dir, "main.html")):
        print(f"  Report: {comparison_dir}/main.html")
        print(f"\nView report: xdg-open {comparison_dir}/main.html")


if __name__ == "__main__":
    main()