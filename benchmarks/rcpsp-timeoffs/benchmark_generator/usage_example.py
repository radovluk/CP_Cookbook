"""
Usage Example: Benchmark Generation and Solution Validation
for RCPSP with Time-Offs

This script demonstrates:
1. Generating benchmarks with various difficulty levels
2. Loading instances
3. Validating solutions for all 6 problem variants
4. Computing instance statistics for difficulty analysis
"""

import os
from benchmark_generator import (
    BenchmarkGenerator, BenchmarkConfig, 
    PrecedenceTopology, CalendarPattern,
    save_instance, generate_benchmark_suite
)
from solution_validator import (
    SolutionValidator, Solution, ProblemVariant,
    validate_solution_dict, ValidationResult
)
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass


# ============================================
# INSTANCE LOADER (from your notebook)
# ============================================

def next_line(f):
    """Read next non-empty, non-comment line."""
    while True:
        raw = f.readline()
        if not raw:
            return None
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        return [int(v) for v in line.split()]


def load_instance(filename):
    """Load RCPSP instance with explicit resource types."""
    with open(filename, "r") as f:
        N, K, M = next_line(f)
        TYPES = [(d[0], d[2:2+d[1]]) for d in (next_line(f) for _ in range(K))]
        UNITS = [(d[0], [(d[2+2*i], d[3+2*i]) for i in range(d[1])]) 
                 for d in (next_line(f) for _ in range(M))]
        TASKS = [(d[0], d[1], [tuple(next_line(f)[:2]) for _ in range(d[2])]) 
                 for d in (next_line(f) for _ in range(N))]
        PRECEDENCES = [tuple(next_line(f)[:2]) for _ in range(next_line(f)[0])]
    return N, K, M, TASKS, TYPES, UNITS, PRECEDENCES


# ============================================
# INSTANCE STATISTICS
# ============================================

@dataclass
class InstanceStats:
    """Statistics about an instance's difficulty."""
    num_tasks: int
    num_work_tasks: int  # Excluding dummy start/end
    num_types: int
    num_units: int
    total_work: int  # Sum of task durations
    avg_task_duration: float
    num_precedences: int
    precedence_density: float  # edges / max possible edges
    
    # Calendar statistics
    avg_availability_ratio: float  # Time available / horizon
    calendar_fragmentation: float  # Avg breaks per unit
    avg_break_length: float
    
    # Resource pressure
    total_requirements: int
    avg_units_per_task: float
    resource_utilization_estimate: float  # work / (capacity * horizon)
    
    # Mode explosion estimate (for No-Migration variants)
    estimated_modes: int  # Product of combination counts
    
    def difficulty_score(self) -> float:
        """Compute an overall difficulty score (higher = harder)."""
        # Weighted combination of factors
        score = 0.0
        score += self.num_work_tasks * 1.0
        score += self.num_types * 2.0
        score += self.num_units * 0.5
        score += self.precedence_density * 10.0
        score += (1 - self.avg_availability_ratio) * 15.0  # Less availability = harder
        score += self.calendar_fragmentation * 3.0
        score += self.resource_utilization_estimate * 20.0
        score += min(self.estimated_modes / 1000, 50)  # Cap contribution
        return score
    
    def __str__(self):
        return f"""Instance Statistics:
  Tasks: {self.num_tasks} ({self.num_work_tasks} work tasks)
  Resources: {self.num_types} types, {self.num_units} units
  Total work: {self.total_work}, avg duration: {self.avg_task_duration:.1f}
  Precedences: {self.num_precedences}, density: {self.precedence_density:.2%}
  Calendar:
    - Avg availability: {self.avg_availability_ratio:.2%}
    - Fragmentation: {self.calendar_fragmentation:.1f} breaks/unit
    - Avg break length: {self.avg_break_length:.1f}
  Resource pressure:
    - Total requirements: {self.total_requirements}
    - Avg units/task: {self.avg_units_per_task:.1f}
    - Utilization estimate: {self.resource_utilization_estimate:.2%}
  Estimated modes: {self.estimated_modes:,}
  DIFFICULTY SCORE: {self.difficulty_score():.1f}"""


def compute_stats(N, K, M, TASKS, TYPES, UNITS, PRECEDENCES, horizon=100000) -> InstanceStats:
    """Compute statistics for an instance."""
    from itertools import combinations
    from functools import reduce
    import operator
    
    # Basic counts
    work_tasks = [(tid, dur, reqs) for tid, dur, reqs in TASKS if dur > 0]
    total_work = sum(dur for _, dur, _ in TASKS)
    avg_duration = total_work / len(work_tasks) if work_tasks else 0
    
    # Precedence density
    max_edges = len(work_tasks) * (len(work_tasks) - 1) // 2
    prec_density = len(PRECEDENCES) / max_edges if max_edges > 0 else 0
    
    # Calendar statistics
    type_map = {t[0]: set(t[1]) for t in TYPES}
    
    def get_availability_stats(calendar):
        """Compute availability ratio and break count for a calendar."""
        available_time = 0
        breaks = 0
        last_value = None
        max_time = max(t for t, v in calendar)
        
        for i, (t, v) in enumerate(calendar[:-1]):
            next_t = calendar[i+1][0]
            if v > 0:
                available_time += next_t - t
            if last_value is not None and last_value > 0 and v == 0:
                breaks += 1
            last_value = v
        
        return available_time / max_time if max_time > 0 else 1.0, breaks
    
    availability_ratios = []
    break_counts = []
    break_lengths = []
    
    for uid, calendar in UNITS:
        ratio, breaks = get_availability_stats(calendar)
        availability_ratios.append(ratio)
        break_counts.append(breaks)
        
        # Compute break lengths
        for i in range(len(calendar) - 1):
            t, v = calendar[i]
            if v == 0:
                next_t = calendar[i+1][0]
                break_lengths.append(next_t - t)
    
    avg_availability = sum(availability_ratios) / len(availability_ratios) if availability_ratios else 1.0
    avg_fragmentation = sum(break_counts) / len(break_counts) if break_counts else 0
    avg_break_len = sum(break_lengths) / len(break_lengths) if break_lengths else 0
    
    # Resource pressure
    total_reqs = sum(qty for _, _, reqs in TASKS for _, qty in reqs)
    avg_units = total_reqs / len(work_tasks) if work_tasks else 0
    
    # Rough utilization estimate (assuming tasks can pack perfectly)
    avg_horizon = max(t for uid, cal in UNITS for t, v in cal)
    total_capacity = M * avg_horizon * avg_availability
    utilization = total_work / total_capacity if total_capacity > 0 else 0
    
    # Mode explosion estimate
    def count_modes(reqs):
        from math import comb
        count = 1
        for type_id, qty in reqs:
            if qty > 0 and type_id in type_map:
                n = len(type_map[type_id])
                count *= comb(n, min(qty, n))
        return count
    
    total_modes = sum(count_modes(reqs) for _, _, reqs in work_tasks)
    
    return InstanceStats(
        num_tasks=N,
        num_work_tasks=len(work_tasks),
        num_types=K,
        num_units=M,
        total_work=total_work,
        avg_task_duration=avg_duration,
        num_precedences=len(PRECEDENCES),
        precedence_density=prec_density,
        avg_availability_ratio=avg_availability,
        calendar_fragmentation=avg_fragmentation,
        avg_break_length=avg_break_len,
        total_requirements=total_reqs,
        avg_units_per_task=avg_units,
        resource_utilization_estimate=utilization,
        estimated_modes=total_modes
    )


# ============================================
# EXAMPLE: Generate and Analyze Benchmarks
# ============================================

def demo_generate_and_analyze():
    """Generate a few instances and analyze their statistics."""
    print("=" * 60)
    print("DEMO: Generating and Analyzing Benchmark Instances")
    print("=" * 60)
    
    configs = [
        ("Trivial", BenchmarkConfig(
            num_tasks=5,
            num_resource_types=1,
            units_per_type=(2,),
            topology=PrecedenceTopology.CHAIN,
            calendar_pattern=CalendarPattern.UNIFORM,
            num_breaks_per_unit=2,
            horizon=50,
            seed=42
        )),
        ("Medium", BenchmarkConfig(
            num_tasks=15,
            num_resource_types=2,
            units_per_type=(4, 3),
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=0.2,
            calendar_pattern=CalendarPattern.STAGGERED,
            num_breaks_per_unit=4,
            horizon=100,
            seed=42
        )),
        ("Hard", BenchmarkConfig(
            num_tasks=25,
            num_resource_types=3,
            units_per_type=(4, 4, 3),
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=0.25,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=6,
            calendar_fragmentation=0.8,
            horizon=150,
            seed=42
        )),
    ]
    
    os.makedirs("./demo_benchmarks", exist_ok=True)
    
    for name, config in configs:
        print(f"\n{'-' * 40}")
        print(f"Generating {name} instance...")
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        
        filename = f"./demo_benchmarks/{name.lower()}.data"
        save_instance(inst, filename, f"{name} difficulty example")
        
        # Load and analyze
        N, K, M, TASKS, TYPES, UNITS, PRECEDENCES = load_instance(filename)
        stats = compute_stats(N, K, M, TASKS, TYPES, UNITS, PRECEDENCES)
        print(stats)


# ============================================
# EXAMPLE: Solution Validation
# ============================================

def demo_validation():
    """Demonstrate solution validation for different variants."""
    print("\n" + "=" * 60)
    print("DEMO: Solution Validation")
    print("=" * 60)
    
    # Create a small test instance
    tasks = [
        (0, 0, [(0, 0), (1, 0)]),  # Dummy start
        (1, 3, [(0, 1), (1, 1)]),  # Task 1: needs 1 machine + 1 worker
        (2, 2, [(0, 1), (1, 0)]),  # Task 2: needs 1 machine only
        (3, 0, [(0, 0), (1, 0)]),  # Dummy end
    ]
    
    types = [
        (0, [0, 1]),  # Machines
        (1, [2, 3]),  # Workers
    ]
    
    # Machine 0: available [0-5), [8-15)
    # Machine 1: available [0-3), [6-15)
    # Worker 2: available [0-10)
    # Worker 3: available [3-15)
    units = [
        (0, [(0, 100), (5, 0), (8, 100), (15, 0)]),
        (1, [(0, 100), (3, 0), (6, 100), (15, 0)]),
        (2, [(0, 100), (10, 0), (15, 0)]),
        (3, [(0, 0), (3, 100), (15, 0)]),
    ]
    
    precedences = [(0, 1), (0, 2), (1, 3), (2, 3)]
    
    print("\nTest Instance:")
    print("  Tasks: 1 (dur=3, needs 1 machine + 1 worker), 2 (dur=2, needs 1 machine)")
    print("  Machine 0: available [0-5), [8-15)")
    print("  Machine 1: available [0-3), [6-15)")
    print("  Worker 2: available [0-10)")
    print("  Worker 3: available [3-15)")
    
    # Test Case 1: Valid solution for Variant 1 (No Migration | No Delays)
    print("\n" + "-" * 40)
    print("Test 1: Valid solution for No Migration | No Delays")
    solution1 = {
        0: [(0, 0, ())],      # Dummy start at t=0
        1: [(0, 3, (0, 2))],   # Task 1: machine 0, worker 2, time [0-3)
        2: [(8, 10, (0,))],   # Task 2: machine 0, time [8-10)
        3: [(10, 10, ())],    # Dummy end at t=10
    }
    result = validate_solution_dict(solution1, tasks, types, units, precedences,
                                     ProblemVariant.NO_MIG_NO_DELAY)
    print(f"  Solution: Task 1 @ [0,3) on (M0,W2), Task 2 @ [8,10) on (M0)")
    print(f"  Result: {result}")
    
    # Test Case 2: Invalid - resource unavailable
    print("\n" + "-" * 40)
    print("Test 2: Invalid - resource unavailable during execution")
    solution2 = {
        0: [(0, 0, ())],
        1: [(3, 6, (0, 2))],   # Task 1: machine 0 unavailable at t=5
        2: [(8, 10, (0,))],
        3: [(10, 10, ())],
    }
    result = validate_solution_dict(solution2, tasks, types, units, precedences,
                                     ProblemVariant.NO_MIG_NO_DELAY)
    print(f"  Solution: Task 1 @ [3,6) on (M0,W2)")
    print(f"  Result: {result}")
    
    # Test Case 3: Valid for Migration variant - aggregate capacity
    print("\n" + "-" * 40)
    print("Test 3: Valid solution for Migration | No Delays")
    solution3 = {
        0: [(0, 0, ())],
        1: [(0, 3, (0, 2))],   # Task 1: uses aggregate capacity
        2: [(0, 2, (1,))],    # Task 2: parallel on different machine
        3: [(3, 3, ())],
    }
    result = validate_solution_dict(solution3, tasks, types, units, precedences,
                                     ProblemVariant.MIG_NO_DELAY)
    print(f"  Solution: Task 1 @ [0,3), Task 2 @ [0,2) (parallel)")
    print(f"  Result: {result}")
    
    # Test Case 4: Migration detected - invalid for No Migration
    print("\n" + "-" * 40)
    print("Test 4: Migration detected - invalid for No Migration variant")
    solution4 = {
        0: [(0, 0, ())],
        1: [(0, 2, (0, 2)), (2, 3, (1, 2))],  # Changed machine!
        2: [(8, 10, (0,))],
        3: [(10, 10, ())],
    }
    result = validate_solution_dict(solution4, tasks, types, units, precedences,
                                     ProblemVariant.NO_MIG_NO_DELAY)
    print(f"  Solution: Task 1 @ [0,2) on (M0,W2) then [2,3) on (M1,W2)")
    print(f"  Result: {result}")
    
    # Test Case 5: Heterogeneous policy
    print("\n" + "-" * 40)
    print("Test 5: Heterogeneous policy - machines fixed, workers can migrate")
    solution5 = {
        0: [(0, 0, ())],
        1: [(0, 2, (0, 2)), (2, 3, (0, 3))],  # Machine 0 fixed, worker changed
        2: [(8, 10, (0,))],
        3: [(10, 10, ())],
    }
    result = validate_solution_dict(solution5, tasks, types, units, precedences,
                                     ProblemVariant.HETEROGENEOUS,
                                     fixed_types={0}, migration_types={1})
    print(f"  Solution: Task 1 with fixed M0, workers 2->3")
    print(f"  Result: {result}")


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    # Generate full benchmark suite
    print("Generating full benchmark suite...")
    generate_benchmark_suite("./benchmarks", seed=42)
    
    # Demo specific instances
    demo_generate_and_analyze()
    
    # Demo validation
    demo_validation()
    
    print("\n" + "=" * 60)
    print("Done! Check ./benchmarks/ for the full benchmark suite.")
    print("=" * 60)
