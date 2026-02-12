#!/usr/bin/env python3
"""
Run solver on all discrepancy instances from discrepancies.md

Usage:
    python run_discrepancies.py [options]

Example:
    python run_discrepancies.py --time-limit 60 --output results.csv

    # Using Kubernetes cluster with 16 workers:
    python run_discrepancies.py --k8s ./optalcp-k8s -w 16 -t 100 -o results.csv
"""

import argparse
import csv
import sys
from pathlib import Path
from datetime import datetime

from solve_rcpspas import solve, configure_solver


# Discrepancy instances from discrepancies.md
# Format: (instance_name, our_optimum, aslib_best, difference)
DISCREPANCIES = [
    ("aslib0_12968", 121, 120, 1),
    ("aslib0_12975", 136, 127, 9),
    ("aslib0_13146", 155, 138, 17),
    ("aslib0_1315", 80, 79, 1),
    ("aslib0_1362", 79, 77, 2),
    ("aslib0_13668", 130, 129, 1),
    ("aslib0_13674", 125, 123, 2),
    ("aslib0_13916", 136, 135, 1),
    ("aslib0_15189", 140, 137, 3),
    ("aslib0_15236", 170, 147, 23),
    ("aslib0_15379", 133, 131, 2),
    ("aslib0_15730", 122, 119, 3),
    ("aslib0_1594", 80, 79, 1),
    ("aslib0_1683", 83, 81, 2),
    ("aslib0_17571", 168, 166, 2),
    ("aslib0_18737", 171, 166, 5),
    ("aslib0_19092", 165, 161, 4),
    ("aslib0_19197", 210, 201, 9),
    ("aslib0_19228", 199, 197, 2),
    ("aslib0_20614", 222, 213, 9),
    ("aslib0_20665", 217, 214, 3),
    ("aslib0_20871", 223, 221, 2),
    ("aslib0_20948", 228, 219, 9),
    ("aslib0_21847", 196, 195, 1),
    ("aslib0_22372", 246, 241, 5),
    ("aslib0_22415", 240, 235, 5),
    ("aslib0_22748", 262, 225, 37),
    ("aslib0_23127", 248, 242, 6),
    ("aslib0_23181", 238, 226, 12),
    ("aslib0_23183", 271, 254, 17),
    ("aslib0_23197", 261, 247, 14),
    ("aslib0_23975", 238, 235, 3),
    ("aslib0_24384", 182, 181, 1),
    ("aslib0_24449", 173, 171, 2),
    ("aslib0_24641", 163, 156, 7),
    ("aslib0_24981", 197, 194, 3),
    ("aslib0_25575", 176, 168, 8),
    ("aslib0_25678", 193, 176, 17),
    ("aslib0_25691", 170, 162, 8),
    ("aslib0_25744", 204, 203, 1),
    ("aslib0_26936", 173, 163, 10),
    ("aslib0_26973", 191, 177, 14),
    ("aslib0_27236", 274, 234, 40),
    ("aslib0_27420", 195, 191, 4),
    ("aslib0_2747", 80, 79, 1),
    ("aslib0_27644", 157, 155, 2),
    ("aslib0_2847", 79, 77, 2),
    ("aslib0_28496", 218, 214, 4),
    ("aslib0_2880", 93, 91, 2),
    ("aslib0_28893", 213, 206, 7),
    ("aslib0_29082", 182, 180, 2),
    ("aslib0_29399", 225, 219, 6),
    ("aslib0_29446", 198, 197, 1),
    ("aslib0_29680", 204, 187, 17),
    ("aslib0_29738", 201, 196, 5),
    ("aslib0_29896", 218, 214, 4),
    ("aslib0_30748", 239, 232, 7),
    ("aslib0_30968", 217, 202, 15),
    ("aslib0_31160", 187, 184, 3),
    ("aslib0_31181", 214, 207, 7),
    ("aslib0_31187", 199, 189, 10),
    ("aslib0_31196", 202, 196, 6),
    ("aslib0_31321", 182, 177, 5),
    ("aslib0_31460", 198, 189, 9),
    ("aslib0_31636", 202, 201, 1),
    ("aslib0_3175", 89, 85, 4),
    ("aslib0_3187", 92, 91, 1),
    ("aslib0_31963", 210, 196, 14),
    ("aslib0_32566", 234, 231, 3),
    ("aslib0_32578", 212, 201, 11),
    ("aslib0_32589", 205, 176, 29),
    ("aslib0_32623", 241, 233, 8),
    ("aslib0_32634", 262, 261, 1),
    ("aslib0_32635", 231, 224, 7),
    ("aslib0_32641", 258, 254, 4),
    ("aslib0_32673", 228, 223, 5),
    ("aslib0_32737", 245, 240, 5),
    ("aslib0_32827", 236, 227, 9),
    ("aslib0_32899", 252, 251, 1),
    ("aslib0_32938", 260, 254, 6),
    ("aslib0_32968", 249, 242, 7),
    ("aslib0_33098", 297, 290, 7),
    ("aslib0_33321", 244, 239, 5),
    ("aslib0_33326", 258, 251, 7),
    ("aslib0_33471", 254, 251, 3),
    ("aslib0_33641", 226, 225, 1),
    ("aslib0_33668", 249, 245, 4),
    ("aslib0_33669", 259, 248, 11),
    ("aslib0_33680", 273, 269, 4),
    ("aslib0_33845", 257, 252, 5),
    ("aslib0_33989", 293, 287, 6),
    ("aslib0_34376", 246, 244, 2),
    ("aslib0_34397", 243, 242, 1),
    ("aslib0_34484", 251, 250, 1),
    ("aslib0_34875", 225, 219, 6),
    ("aslib0_34892", 218, 208, 10),
    ("aslib0_34968", 253, 247, 6),
    ("aslib0_35124", 245, 242, 3),
    ("aslib0_35167", 259, 254, 5),
    ("aslib0_35174", 259, 244, 15),
    ("aslib0_35212", 279, 271, 8),
    ("aslib0_35220", 247, 239, 8),
    ("aslib0_35224", 274, 256, 18),
    ("aslib0_35247", 240, 236, 4),
    ("aslib0_35373", 249, 236, 13),
    ("aslib0_35433", 258, 257, 1),
    ("aslib0_35438", 260, 259, 1),
    ("aslib0_35577", 203, 191, 12),
    ("aslib0_35676", 265, 251, 14),
    ("aslib0_35690", 255, 246, 9),
    ("aslib0_35963", 259, 256, 3),
    ("aslib0_35976", 271, 261, 10),
    ("aslib0_35995", 257, 254, 3),
    ("aslib0_3913", 85, 82, 3),
    ("aslib0_398", 100, 84, 16),
    ("aslib0_476", 101, 94, 7),
    ("aslib0_5098", 183, 180, 3),
    ("aslib0_610", 78, 76, 2),
    ("aslib0_8341", 245, 239, 6),
    ("aslib0_893", 84, 83, 1),
    ("aslib0_940", 75, 73, 2),
]


def find_instance_file(instance_name, data_dir):
    """Find instance file by name (with 'a' suffix)."""
    # Instance files have 'a' suffix: aslib0_12968 -> aslib0_12968a.RCP
    filename = f"{instance_name}a.RCP"
    instance_path = data_dir / filename

    if instance_path.exists():
        return instance_path

    # Try searching recursively
    matches = list(data_dir.rglob(filename))
    if matches:
        return matches[0]

    return None


def main():
    parser = argparse.ArgumentParser(
        description='Run solver on all discrepancy instances',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_discrepancies.py -t 100 -o results.csv
    python run_discrepancies.py --start 1 --end 10 -t 60

    # Using Kubernetes cluster:
    python run_discrepancies.py --k8s ./optalcp-k8s -w 16 -t 100 -o results.csv
        """
    )
    parser.add_argument('--data-dir', '-d', type=Path,
                        default=Path('../../data/rcpspas/ASLIB/ASLIB0'),
                        help='Directory containing instance files')
    parser.add_argument('--time-limit', '-t', type=int, default=100,
                        help='Time limit per instance in seconds (default: 100)')
    parser.add_argument('--workers', '-w', type=int, default=8,
                        help='Number of workers (default: 8)')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output CSV file for results')
    parser.add_argument('--start', type=int, default=1,
                        help='Start from instance number (1-indexed)')
    parser.add_argument('--end', type=int,
                        help='End at instance number (1-indexed)')
    parser.add_argument('--instance', '-i', type=str,
                        help='Run only specific instance by name')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Quiet mode (less verbose output)')
    parser.add_argument('--k8s', '--solver', type=Path, dest='solver',
                        help='Path to custom solver (e.g., optalcp-k8s for K8s cluster)')

    args = parser.parse_args()

    # Configure K8s/custom solver if specified
    if args.solver:
        configure_solver(args.solver)

    # Resolve data directory
    data_dir = args.data_dir.resolve()
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    # Filter instances
    if args.instance:
        instances = [(name, opt, aslib, diff) for name, opt, aslib, diff in DISCREPANCIES
                    if name == args.instance]
        if not instances:
            print(f"Error: Instance '{args.instance}' not found in discrepancy list", file=sys.stderr)
            sys.exit(1)
    else:
        start_idx = args.start - 1
        end_idx = args.end if args.end else len(DISCREPANCIES)
        instances = DISCREPANCIES[start_idx:end_idx]

    results = []

    print(f"Running {len(instances)} discrepancy instances")
    print(f"Data directory: {data_dir}")
    print(f"Time limit: {args.time_limit}s per instance")
    print(f"Workers: {args.workers}")
    print("=" * 80)

    for idx, (instance_name, expected_opt, aslib_best, diff) in enumerate(instances, 1):
        print(f"\n[{idx}/{len(instances)}] {instance_name}")
        print(f"  Expected optimum: {expected_opt}, ASLIB best: {aslib_best}, Diff: {diff}")

        instance_path = find_instance_file(instance_name, data_dir)
        if not instance_path:
            print(f"  ERROR: Instance file not found!")
            results.append({
                'instance': instance_name,
                'expected_optimum': expected_opt,
                'aslib_best': aslib_best,
                'expected_diff': diff,
                'computed_objective': None,
                'lower_bound': None,
                'optimal': None,
                'duration': None,
                'status': 'FILE_NOT_FOUND'
            })
            continue

        try:
            result = solve(
                instance_path,
                nb_workers=args.workers,
                time_limit=args.time_limit,
                log_level=0 if args.quiet else 2,
                log_period=5
            )

            computed_obj = result['objective']
            is_optimal = result['optimal']

            # Verify against expected
            status = 'OK'
            if computed_obj is not None and is_optimal:
                if computed_obj != expected_opt:
                    status = f'MISMATCH (expected {expected_opt}, got {computed_obj})'
            elif computed_obj is None:
                status = 'NO_SOLUTION'
            else:
                status = 'NOT_OPTIMAL'

            results.append({
                'instance': instance_name,
                'expected_optimum': expected_opt,
                'aslib_best': aslib_best,
                'expected_diff': diff,
                'computed_objective': computed_obj,
                'lower_bound': result.get('lower_bound'),
                'optimal': is_optimal,
                'duration': result.get('duration'),
                'status': status
            })

            print(f"  Result: {computed_obj} (optimal: {is_optimal}) - {status}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                'instance': instance_name,
                'expected_optimum': expected_opt,
                'aslib_best': aslib_best,
                'expected_diff': diff,
                'computed_objective': None,
                'lower_bound': None,
                'optimal': None,
                'duration': None,
                'status': f'ERROR: {e}'
            })

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total = len(results)
    optimal_count = sum(1 for r in results if r['optimal'])
    ok_count = sum(1 for r in results if r['status'] == 'OK')
    mismatch_count = sum(1 for r in results if 'MISMATCH' in str(r['status']))
    error_count = sum(1 for r in results if 'ERROR' in str(r['status']) or r['status'] == 'FILE_NOT_FOUND')

    print(f"Total instances: {total}")
    print(f"Optimal found: {optimal_count}")
    print(f"Matching expected: {ok_count}")
    print(f"Mismatches: {mismatch_count}")
    print(f"Errors: {error_count}")

    # Save to CSV if requested
    if args.output:
        with open(args.output, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'instance', 'expected_optimum', 'aslib_best', 'expected_diff',
                'computed_objective', 'lower_bound', 'optimal', 'duration', 'status'
            ])
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved to: {args.output}")

    return results


if __name__ == '__main__':
    main()
