"""
Generate large-scale benchmark instances for RCPSP with Time-Offs.

New categories beyond the original 800 instances (tiers 1-5 + 3 special):
- Tier 6: Large (50 instances)         -- 80-150 tasks
- Tier 7: Industrial (50 instances)    -- 150-300 tasks
- Tier 8: Mega (50 instances)          -- 300-600 tasks
- Tier 9: Extreme (50 instances)       -- 600-1200 tasks
- Tier 10: Massive (50 instances)      -- 1200-3000 tasks
- Special: Dense Large (50 instances)  -- 100-300 tasks, high precedence density
- Special: Many Resources (50 instances) -- 80-200 tasks, 10-20 resource types

Total: 350 new instances
"""

import os
import random
import time
from benchmark_generator import (
    BenchmarkGenerator, BenchmarkConfig,
    PrecedenceTopology, CalendarPattern,
    save_instance
)


def _scaled_breaks(horizon, break_interval_range=(40, 80)):
    """Compute number of breaks proportional to horizon."""
    interval = random.randint(*break_interval_range)
    return max(2, horizon // interval)


def generate_tier6_large(output_dir: str, count: int = 50, base_seed: int = 10000):
    """Tier 6: Large -- 80-150 tasks, 4-6 types, 6-10 units/type."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(count):
        seed = base_seed + i
        random.seed(seed)

        num_tasks = random.randint(80, 150)
        num_types = random.randint(4, 6)
        units = tuple(random.randint(6, 10) for _ in range(num_types))
        horizon = random.randint(500, 1000)
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID,
        ])
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED,
            CalendarPattern.HEAVY_START,
            CalendarPattern.HEAVY_END,
        ])

        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=3,
            max_duration=15,
            min_requirements=1,
            max_requirements=3,
            requirement_probability=0.7,
            topology=topology,
            precedence_density=random.uniform(0.12, 0.22),
            calendar_pattern=calendar,
            num_breaks_per_unit=_scaled_breaks(horizon, (50, 100)),
            avg_break_length=random.randint(5, 15),
            break_length_variance=random.uniform(0.2, 0.4),
            calendar_fragmentation=random.uniform(0.5, 0.7),
            scarcity_factor=random.uniform(1.0, 1.3),
            horizon=horizon,
            seed=seed,
        )

        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier6_{i:03d}.data",
            f"Tier 6 (Large) - Instance {i}",
        )

    print(f"Generated {count} Tier 6 (Large) instances in {output_dir}/")


def generate_tier7_industrial(output_dir: str, count: int = 50, base_seed: int = 11000):
    """Tier 7: Industrial -- 150-300 tasks, 5-8 types, 8-15 units/type."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(count):
        seed = base_seed + i
        random.seed(seed)

        num_tasks = random.randint(150, 300)
        num_types = random.randint(5, 8)
        units = tuple(random.randint(8, 15) for _ in range(num_types))
        horizon = random.randint(1000, 3000)
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID,
        ])
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED,
            CalendarPattern.CLUSTERED,
        ])

        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=3,
            max_duration=20,
            min_requirements=1,
            max_requirements=4,
            requirement_probability=0.65,
            topology=topology,
            precedence_density=random.uniform(0.08, 0.18),
            calendar_pattern=calendar,
            num_breaks_per_unit=_scaled_breaks(horizon, (50, 100)),
            avg_break_length=random.randint(8, 25),
            break_length_variance=random.uniform(0.2, 0.4),
            calendar_fragmentation=random.uniform(0.4, 0.7),
            scarcity_factor=random.uniform(0.9, 1.3),
            horizon=horizon,
            seed=seed,
        )

        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier7_{i:03d}.data",
            f"Tier 7 (Industrial) - Instance {i}",
        )

    print(f"Generated {count} Tier 7 (Industrial) instances in {output_dir}/")


def generate_tier8_mega(output_dir: str, count: int = 50, base_seed: int = 12000):
    """Tier 8: Mega -- 300-600 tasks, 6-10 types, 10-20 units/type."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(count):
        seed = base_seed + i
        random.seed(seed)

        num_tasks = random.randint(300, 600)
        num_types = random.randint(6, 10)
        units = tuple(random.randint(10, 20) for _ in range(num_types))
        horizon = random.randint(2000, 5000)
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID,
        ])
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED,
        ])

        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=4,
            max_duration=25,
            min_requirements=1,
            max_requirements=4,
            requirement_probability=0.6,
            topology=topology,
            precedence_density=random.uniform(0.05, 0.12),
            calendar_pattern=calendar,
            num_breaks_per_unit=_scaled_breaks(horizon, (40, 80)),
            avg_break_length=random.randint(10, 35),
            break_length_variance=random.uniform(0.2, 0.5),
            calendar_fragmentation=random.uniform(0.4, 0.6),
            scarcity_factor=random.uniform(0.9, 1.2),
            horizon=horizon,
            seed=seed,
        )

        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier8_{i:03d}.data",
            f"Tier 8 (Mega) - Instance {i}",
        )

    print(f"Generated {count} Tier 8 (Mega) instances in {output_dir}/")


def generate_tier9_extreme(output_dir: str, count: int = 50, base_seed: int = 13000):
    """Tier 9: Extreme -- 600-1200 tasks, 8-12 types, 12-25 units/type."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(count):
        seed = base_seed + i
        random.seed(seed)

        num_tasks = random.randint(600, 1200)
        num_types = random.randint(8, 12)
        units = tuple(random.randint(12, 25) for _ in range(num_types))
        horizon = random.randint(5000, 10000)
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID,
        ])
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED,
        ])

        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=5,
            max_duration=30,
            min_requirements=1,
            max_requirements=5,
            requirement_probability=0.55,
            topology=topology,
            precedence_density=random.uniform(0.03, 0.08),
            calendar_pattern=calendar,
            num_breaks_per_unit=_scaled_breaks(horizon, (40, 70)),
            avg_break_length=random.randint(15, 50),
            break_length_variance=random.uniform(0.2, 0.5),
            calendar_fragmentation=random.uniform(0.3, 0.6),
            scarcity_factor=random.uniform(0.8, 1.2),
            horizon=horizon,
            seed=seed,
        )

        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier9_{i:03d}.data",
            f"Tier 9 (Extreme) - Instance {i}",
        )

    print(f"Generated {count} Tier 9 (Extreme) instances in {output_dir}/")


def generate_tier10_massive(output_dir: str, count: int = 50, base_seed: int = 14000):
    """Tier 10: Massive -- 1200-3000 tasks, 10-15 types, 15-30 units/type."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(count):
        seed = base_seed + i
        random.seed(seed)

        num_tasks = random.randint(1200, 3000)
        num_types = random.randint(10, 15)
        units = tuple(random.randint(15, 30) for _ in range(num_types))
        horizon = random.randint(10000, 50000)
        # For very large instances, only RANDOM_DAG with low density is practical
        topology = PrecedenceTopology.RANDOM_DAG
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED,
        ])

        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=5,
            max_duration=40,
            min_requirements=1,
            max_requirements=5,
            requirement_probability=0.5,
            topology=topology,
            precedence_density=random.uniform(0.01, 0.04),
            calendar_pattern=calendar,
            num_breaks_per_unit=_scaled_breaks(horizon, (40, 80)),
            avg_break_length=random.randint(20, 80),
            break_length_variance=random.uniform(0.2, 0.5),
            calendar_fragmentation=random.uniform(0.3, 0.5),
            scarcity_factor=random.uniform(0.8, 1.1),
            horizon=horizon,
            seed=seed,
        )

        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier10_{i:03d}.data",
            f"Tier 10 (Massive) - Instance {i}",
        )

    print(f"Generated {count} Tier 10 (Massive) instances in {output_dir}/")


def generate_special_dense_large(output_dir: str, count: int = 50, base_seed: int = 15000):
    """Special: Dense Large -- 100-300 tasks with high precedence density."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(count):
        seed = base_seed + i
        random.seed(seed)

        num_tasks = random.randint(100, 300)
        num_types = random.randint(4, 6)
        units = tuple(random.randint(5, 8) for _ in range(num_types))
        horizon = random.randint(1000, 3000)
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED,
            CalendarPattern.HEAVY_START,
        ])

        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=3,
            max_duration=18,
            min_requirements=1,
            max_requirements=3,
            requirement_probability=0.7,
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=random.uniform(0.30, 0.50),  # Very high density
            calendar_pattern=calendar,
            num_breaks_per_unit=_scaled_breaks(horizon, (50, 90)),
            avg_break_length=random.randint(8, 20),
            break_length_variance=random.uniform(0.2, 0.4),
            calendar_fragmentation=random.uniform(0.4, 0.7),
            scarcity_factor=random.uniform(1.0, 1.4),
            horizon=horizon,
            seed=seed,
        )

        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/special_dense_{i:03d}.data",
            f"Special (Dense Large) - Instance {i}",
        )

    print(f"Generated {count} Special (Dense Large) instances in {output_dir}/")


def generate_special_many_resources(output_dir: str, count: int = 50, base_seed: int = 16000):
    """Special: Many Resources -- 80-200 tasks, 10-20 resource types, 15-30 units/type."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(count):
        seed = base_seed + i
        random.seed(seed)

        num_tasks = random.randint(80, 200)
        num_types = random.randint(10, 20)
        units = tuple(random.randint(15, 30) for _ in range(num_types))
        horizon = random.randint(1000, 5000)
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID,
        ])
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED,
        ])

        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=3,
            max_duration=20,
            min_requirements=1,
            max_requirements=4,
            requirement_probability=0.4,  # Lower since there are many types
            topology=topology,
            precedence_density=random.uniform(0.08, 0.18),
            calendar_pattern=calendar,
            num_breaks_per_unit=_scaled_breaks(horizon, (50, 100)),
            avg_break_length=random.randint(10, 30),
            break_length_variance=random.uniform(0.2, 0.5),
            calendar_fragmentation=random.uniform(0.4, 0.6),
            scarcity_factor=random.uniform(0.9, 1.2),
            horizon=horizon,
            seed=seed,
        )

        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/special_many_res_{i:03d}.data",
            f"Special (Many Resources) - Instance {i}",
        )

    print(f"Generated {count} Special (Many Resources) instances in {output_dir}/")


def generate_all(base_dir: str, count_per_category: int = 50, master_seed: int = 99):
    """Generate all new large-scale benchmark categories."""
    print("=" * 60)
    print(f"Generating {count_per_category} instances per category")
    print(f"Total: {count_per_category * 7} new instances")
    print("=" * 60)

    start = time.time()
    random.seed(master_seed)

    generate_tier6_large(f"{base_dir}/tier6_large", count_per_category, base_seed=10000)
    generate_tier7_industrial(f"{base_dir}/tier7_industrial", count_per_category, base_seed=11000)
    generate_tier8_mega(f"{base_dir}/tier8_mega", count_per_category, base_seed=12000)
    generate_tier9_extreme(f"{base_dir}/tier9_extreme", count_per_category, base_seed=13000)
    generate_tier10_massive(f"{base_dir}/tier10_massive", count_per_category, base_seed=14000)
    generate_special_dense_large(f"{base_dir}/special_dense_large", count_per_category, base_seed=15000)
    generate_special_many_resources(f"{base_dir}/special_many_resources", count_per_category, base_seed=16000)

    elapsed = time.time() - start

    print("=" * 60)
    print(f"Done! Generated {count_per_category * 7} instances in {elapsed:.1f}s")
    print(f"Output directory: {base_dir}/")
    print("=" * 60)


if __name__ == "__main__":
    generate_all(
        "/home/lukas/Desktop/CIIRC/CP_Cookbook/data/rcpsp-timeoffs",
        count_per_category=50,
        master_seed=99,
    )
