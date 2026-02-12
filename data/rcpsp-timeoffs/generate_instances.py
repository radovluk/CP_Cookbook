#!/usr/bin/env python3
"""
RCPSP-TimeOffs Instance Generator

Generates benchmark instances for RCPSP with Time-Offs at various scales.

Usage:
    python generate_instances.py --tier 6                    # 100 large instances (200-300 tasks)
    python generate_instances.py --tier 7                    # 100 very large instances (300-500 tasks)
    python generate_instances.py --tier 6 --count 5 --seed 0 # 5 instances for testing
"""

import argparse
import math
import os
import random
from collections import deque
from dataclasses import dataclass, field
from typing import List, Tuple, Set, Dict


# =============================================================================
# TIER CONFIGURATION
# =============================================================================

@dataclass
class TierConfig:
    name: str
    label: str
    dir_name: str
    n_min: int
    n_max: int
    k_min: int
    k_max: int
    m_min: int
    m_max: int
    units_per_type_min: int
    units_per_type_max: int
    task_size_min: int
    task_size_max: int
    cal_steps_min: int
    cal_steps_max: int
    topologies: List[str]
    calendars: List[str]
    count: int = 100


TIER_CONFIGS = {
    6: TierConfig(
        name="tier6", label="Tier 6 (Large)", dir_name="tier6_large",
        n_min=200, n_max=300,
        k_min=3, k_max=5,
        m_min=15, m_max=25,
        units_per_type_min=3, units_per_type_max=8,
        task_size_min=1, task_size_max=20,
        cal_steps_min=20, cal_steps_max=30,
        topologies=["random_dag", "grid"],
        calendars=["staggered", "random"],
    ),
    7: TierConfig(
        name="tier7", label="Tier 7 (Very Large)", dir_name="tier7_very_large",
        n_min=300, n_max=500,
        k_min=3, k_max=5,
        m_min=20, m_max=30,
        units_per_type_min=4, units_per_type_max=8,
        task_size_min=1, task_size_max=20,
        cal_steps_min=20, cal_steps_max=30,
        topologies=["random_dag", "grid"],
        calendars=["staggered", "random"],
    ),
}


# =============================================================================
# RESOURCE TYPES
# =============================================================================

def generate_resource_types(rng, K, M, upt_min, upt_max):
    """Distribute M resource units across K types."""
    counts = [upt_min] * K
    remaining = M - sum(counts)
    while remaining > 0:
        candidates = [i for i in range(K) if counts[i] < upt_max]
        if not candidates:
            break
        idx = rng.choice(candidates)
        counts[idx] += 1
        remaining -= 1

    types = []
    uid = 0
    for tid in range(K):
        unit_ids = list(range(uid, uid + counts[tid]))
        types.append((tid, unit_ids))
        uid += counts[tid]
    return types


# =============================================================================
# CALENDAR GENERATORS
# =============================================================================

def generate_staggered_calendar(rng, uid, num_steps, horizon, total_units):
    """Regular on/off calendar with phase offset per unit."""
    num_cycles = max(1, num_steps // 2)
    cycle_len = horizon / num_cycles
    on_frac = rng.uniform(0.82, 0.92)
    on_dur = cycle_len * on_frac
    off_dur = cycle_len * (1 - on_frac)

    # Phase offset for staggering
    offset = (uid * cycle_len / max(1, total_units)) % cycle_len

    steps = [(0, 100)]
    t = int(offset + rng.uniform(-2, 2))
    t = max(1, t)

    while len(steps) < num_steps - 1 and t < horizon:
        # Off period
        steps.append((t, 0))
        t_on = t + max(1, int(off_dur + rng.uniform(-2, 2)))
        if t_on >= horizon or len(steps) >= num_steps - 1:
            break
        # On period
        steps.append((t_on, 100))
        t = t_on + max(1, int(on_dur + rng.uniform(-3, 3)))

    # Sentinel at horizon
    steps.append((horizon, 0))
    return steps


def generate_random_calendar(rng, uid, num_steps, horizon, total_units):
    """Irregular calendar with random on/off intervals."""
    avg_segment = horizon / max(1, num_steps - 1)
    start_avail = rng.choice([True, False])
    steps = [(0, 100 if start_avail else 0)]

    t = 0
    for _ in range(num_steps - 2):
        current_val = steps[-1][1]
        if current_val == 100:
            # On -> off: variable on-duration
            gap = max(2, int(rng.uniform(0.3, 1.8) * avg_segment))
        else:
            # Off -> on: short off-duration
            gap = rng.randint(2, max(3, int(0.15 * avg_segment)))
        t += gap
        if t >= horizon:
            break
        steps.append((t, 0 if current_val == 100 else 100))

    steps.append((horizon, 0))
    return steps


# =============================================================================
# DAG TOPOLOGY GENERATORS
# =============================================================================

def generate_random_dag(rng, N, avg_successors=5):
    """Layered random DAG. Tasks 0=source, N+1=sink, 1..N=internal."""
    source, sink = 0, N + 1

    num_layers = max(3, int(math.sqrt(N)))
    layer = {source: 0, sink: num_layers + 1}
    for t in range(1, N + 1):
        layer[t] = rng.randint(1, num_layers)

    # Group by layer
    layers = {}
    for t, l in layer.items():
        layers.setdefault(l, []).append(t)

    sorted_layer_ids = sorted(layers.keys())
    edges = set()

    # Source -> first internal layer
    first_layer = sorted_layer_ids[1]
    for t in layers[first_layer]:
        edges.add((source, t))

    # Inter-layer edges
    for li_idx in range(1, len(sorted_layer_ids) - 1):
        li = sorted_layer_ids[li_idx]
        later_tasks = []
        for lj_idx in range(li_idx + 1, len(sorted_layer_ids) - 1):
            later_tasks.extend(layers[sorted_layer_ids[lj_idx]])

        if not later_tasks:
            continue

        for t in layers[li]:
            n_succ = max(1, rng.randint(
                max(1, avg_successors - 2),
                avg_successors + 2
            ))
            n_succ = min(n_succ, len(later_tasks))
            succs = rng.sample(later_tasks, n_succ)
            for s in succs:
                edges.add((t, s))

    # Last internal layer -> sink
    last_layer = sorted_layer_ids[-2]
    for t in layers[last_layer]:
        edges.add((t, sink))

    return edges


def generate_grid_dag(rng, N):
    """2D grid DAG. Tasks 0=source, N+1=sink, 1..N=internal."""
    source, sink = 0, N + 1

    cols = max(2, int(math.sqrt(N * 2)))
    rows = max(2, math.ceil(N / cols))

    # Map grid cells to task IDs
    grid = {}
    tid = 1
    for r in range(rows):
        for c in range(cols):
            if tid > N:
                break
            grid[(r, c)] = tid
            tid += 1

    edges = set()

    # Grid edges: right, down, occasional diagonal
    for (r, c), t in grid.items():
        if (r, c + 1) in grid:
            edges.add((t, grid[(r, c + 1)]))
        if (r + 1, c) in grid:
            edges.add((t, grid[(r + 1, c)]))
        if (r + 1, c + 1) in grid and rng.random() < 0.3:
            edges.add((t, grid[(r + 1, c + 1)]))

    # Source -> first column
    for r in range(rows):
        if (r, 0) in grid:
            edges.add((source, grid[(r, 0)]))

    # Last column -> sink
    max_col = max(c for (r, c) in grid)
    for r in range(rows):
        if (r, max_col) in grid:
            edges.add((grid[(r, max_col)], sink))

    return edges


# =============================================================================
# DAG VALIDATION
# =============================================================================

def validate_and_repair_dag(edges, N):
    """Ensure all tasks reachable from source, all reach sink, no cycles."""
    source, sink = 0, N + 1
    all_tasks = set(range(N + 2))

    # Build adjacency
    adj = {i: set() for i in range(N + 2)}
    radj = {i: set() for i in range(N + 2)}
    for u, v in edges:
        adj[u].add(v)
        radj[v].add(u)

    # Forward BFS from source
    visited_fwd = set()
    queue = deque([source])
    visited_fwd.add(source)
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in visited_fwd:
                visited_fwd.add(v)
                queue.append(v)

    # Fix unreachable tasks
    for t in range(1, N + 1):
        if t not in visited_fwd:
            edges.add((source, t))
            adj[source].add(t)
            radj[t].add(source)

    # Backward BFS from sink
    visited_bwd = set()
    queue = deque([sink])
    visited_bwd.add(sink)
    while queue:
        u = queue.popleft()
        for v in radj[u]:
            if v not in visited_bwd:
                visited_bwd.add(v)
                queue.append(v)

    # Fix tasks that can't reach sink
    for t in range(1, N + 1):
        if t not in visited_bwd:
            edges.add((t, sink))
            adj[t].add(sink)
            radj[sink].add(t)

    # Verify acyclicity (Kahn's algorithm)
    in_degree = {i: len(radj[i]) for i in range(N + 2)}
    queue = deque([i for i in range(N + 2) if in_degree[i] == 0])
    count = 0
    while queue:
        u = queue.popleft()
        count += 1
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    assert count == N + 2, f"Cycle detected: sorted {count} of {N + 2} tasks"
    return edges


# =============================================================================
# TASK GENERATION
# =============================================================================

def generate_tasks(rng, N, K, types, size_min, size_max):
    """Generate N+2 tasks: source (0), internal (1..N), sink (N+1)."""
    tasks = []

    # Source
    tasks.append((0, 0, [(tid, 0) for tid, _ in types]))

    # Internal tasks
    for t in range(1, N + 1):
        size = rng.randint(size_min, size_max)
        reqs = []
        for tid, unit_ids in types:
            max_qty = min(3, len(unit_ids))
            if rng.random() < 0.6 and max_qty > 0:
                qty = rng.randint(1, max_qty)
            else:
                qty = 0
            reqs.append((tid, qty))

        # Ensure at least one non-zero requirement
        if all(qty == 0 for _, qty in reqs):
            idx = rng.randint(0, K - 1)
            reqs[idx] = (types[idx][0], 1)

        tasks.append((t, size, reqs))

    # Sink
    tasks.append((N + 1, 0, [(tid, 0) for tid, _ in types]))

    return tasks


# =============================================================================
# INSTANCE WRITER
# =============================================================================

def write_instance(filepath, tier_label, instance_idx, config_str,
                   N_total, K, M, types, calendars, tasks, edges):
    """Write instance in the standard .data format."""
    edge_list = sorted(edges)

    with open(filepath, 'w') as f:
        f.write(f"# {tier_label} - Instance {instance_idx}\n")
        f.write(f"# Generated with config: {config_str}\n")
        f.write(f"\n")

        f.write(f"# HEADER: <num_tasks> <num_types> <num_units>\n")
        f.write(f"{N_total} {K} {M}\n")
        f.write(f"\n")

        f.write(f"# RESOURCE TYPES\n")
        f.write(f"# Format: <type_id> <num_units> <unit_id1> <unit_id2> ...\n")
        for tid, unit_ids in types:
            f.write(f"{tid} {len(unit_ids)} {' '.join(map(str, unit_ids))}\n")
        f.write(f"\n")

        f.write(f"# RESOURCE UNITS (Calendars)\n")
        f.write(f"# Format: <unit_id> <num_steps> <t1> <v1> <t2> <v2> ...\n")
        for uid, steps in calendars:
            pairs = ' '.join(f"{t} {v}" for t, v in steps)
            f.write(f"{uid} {len(steps)} {pairs}\n")
        f.write(f"\n")

        f.write(f"# TASKS\n")
        f.write(f"# Format: <task_id> <size> <num_reqs>\n")
        f.write(f"# Then for each requirement: <type_id> <qty>\n")
        for tid, size, reqs in tasks:
            f.write(f"{tid} {size} {len(reqs)}\n")
            for type_id, qty in reqs:
                f.write(f" {type_id} {qty}\n")
        f.write(f"\n")

        f.write(f"# PRECEDENCES\n")
        f.write(f"{len(edge_list)}\n")
        for u, v in edge_list:
            f.write(f"{u} {v}\n")


# =============================================================================
# INSTANCE ORCHESTRATOR
# =============================================================================

def generate_instance(rng, cfg, instance_idx):
    """Generate a single instance."""
    N = rng.randint(cfg.n_min, cfg.n_max)
    K = rng.randint(cfg.k_min, cfg.k_max)

    m_min = max(cfg.m_min, K * cfg.units_per_type_min)
    m_max = min(cfg.m_max, K * cfg.units_per_type_max)
    M = rng.randint(m_min, m_max)

    topology = rng.choice(cfg.topologies)
    calendar_style = rng.choice(cfg.calendars)

    types = generate_resource_types(rng, K, M,
                                     cfg.units_per_type_min,
                                     cfg.units_per_type_max)

    horizon = int(N * rng.uniform(8.5, 10.5))
    num_steps = rng.randint(cfg.cal_steps_min, cfg.cal_steps_max)

    calendars = []
    cal_fn = (generate_staggered_calendar if calendar_style == "staggered"
              else generate_random_calendar)
    for _, unit_ids in types:
        for uid in unit_ids:
            steps = cal_fn(rng, uid, num_steps, horizon, M)
            calendars.append((uid, steps))

    if topology == "random_dag":
        avg_succ = rng.randint(3, 8)
        edges = generate_random_dag(rng, N, avg_successors=avg_succ)
    else:
        edges = generate_grid_dag(rng, N)

    edges = validate_and_repair_dag(edges, N)

    tasks = generate_tasks(rng, N, K, types,
                           cfg.task_size_min, cfg.task_size_max)

    config_str = f"N={N}, K={K}, topology={topology}, calendar={calendar_style}"
    N_total = N + 2

    return (config_str, N_total, K, M, types, calendars, tasks, edges)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate RCPSP-TimeOffs benchmark instances'
    )
    parser.add_argument('--tier', type=int, required=True,
                        choices=sorted(TIER_CONFIGS.keys()),
                        help='Tier to generate')
    parser.add_argument('--count', type=int, default=None,
                        help='Number of instances (default: from tier config)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory (default: auto from tier)')
    args = parser.parse_args()

    cfg = TIER_CONFIGS[args.tier]
    count = args.count or cfg.count
    out_dir = args.output_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        cfg.dir_name
    )
    os.makedirs(out_dir, exist_ok=True)

    rng = random.Random(args.seed)

    print(f"Generating {count} {cfg.label} instances...")
    print(f"  Tasks: {cfg.n_min}-{cfg.n_max}, Types: {cfg.k_min}-{cfg.k_max}, "
          f"Units: {cfg.m_min}-{cfg.m_max}")
    print(f"  Output: {out_dir}/")

    for i in range(count):
        data = generate_instance(rng, cfg, i)
        filename = f"{cfg.name}_{i:03d}.data"
        filepath = os.path.join(out_dir, filename)
        write_instance(filepath, cfg.label, i, *data)
        if (i + 1) % 10 == 0 or i == 0:
            N_total = data[1]
            print(f"  [{i+1:3d}/{count}] {filename} (N={N_total})")

    print(f"Done. {count} instances in {out_dir}/")


if __name__ == "__main__":
    main()
