"""
Generate 100 instances from each benchmark category.

Categories:
- Tier 1: Trivial (100 instances)
- Tier 2: Easy (100 instances)
- Tier 3: Medium (100 instances)
- Tier 4: Hard (100 instances)
- Tier 5: Very Hard (100 instances)
- Special: Calendar Stress (100 instances)
- Special: Mode Explosion (100 instances)
- Special: Tight Windows (100 instances)

Total: 800 instances
"""

import os
import random
from benchmark_generator import (
    BenchmarkGenerator, BenchmarkConfig,
    PrecedenceTopology, CalendarPattern,
    save_instance
)


def generate_tier1_trivial(output_dir: str, count: int = 100, base_seed: int = 1000):
    """Generate trivial instances - small, simple structure."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        # Vary parameters slightly within trivial range
        num_tasks = random.randint(3, 6)
        num_types = 1
        units = (random.randint(2, 3),)
        topology = random.choice([PrecedenceTopology.CHAIN, PrecedenceTopology.PARALLEL])
        calendar = random.choice([CalendarPattern.UNIFORM, CalendarPattern.STAGGERED])
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=2,
            max_duration=5,
            min_requirements=1,
            max_requirements=min(2, units[0]),
            topology=topology,
            precedence_density=0.1,
            calendar_pattern=calendar,
            num_breaks_per_unit=random.randint(1, 2),
            avg_break_length=random.randint(3, 6),
            horizon=40 + num_tasks * 5,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst, 
            f"{output_dir}/tier1_{i:03d}.data",
            f"Tier 1 (Trivial) - Instance {i}"
        )
    
    print(f"Generated {count} Tier 1 (Trivial) instances in {output_dir}/")


def generate_tier2_easy(output_dir: str, count: int = 100, base_seed: int = 2000):
    """Generate easy instances - small but nontrivial."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        num_tasks = random.randint(6, 10)
        num_types = random.randint(1, 2)
        units = tuple(random.randint(2, 4) for _ in range(num_types))
        topology = random.choice([
            PrecedenceTopology.TREE, 
            PrecedenceTopology.DIAMOND,
            PrecedenceTopology.RANDOM_DAG
        ])
        calendar = random.choice([
            CalendarPattern.UNIFORM, 
            CalendarPattern.STAGGERED,
            CalendarPattern.RANDOM
        ])
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=2,
            max_duration=8,
            min_requirements=1,
            max_requirements=2,
            topology=topology,
            precedence_density=random.uniform(0.1, 0.2),
            calendar_pattern=calendar,
            num_breaks_per_unit=random.randint(2, 4),
            avg_break_length=random.randint(3, 7),
            calendar_fragmentation=random.uniform(0.3, 0.5),
            horizon=60 + num_tasks * 5,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier2_{i:03d}.data",
            f"Tier 2 (Easy) - Instance {i}"
        )
    
    print(f"Generated {count} Tier 2 (Easy) instances in {output_dir}/")


def generate_tier3_medium(output_dir: str, count: int = 100, base_seed: int = 3000):
    """Generate medium instances - standard difficulty."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        num_tasks = random.randint(12, 20)
        num_types = random.randint(2, 3)
        units = tuple(random.randint(3, 5) for _ in range(num_types))
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID,
            PrecedenceTopology.DIAMOND
        ])
        calendar = random.choice([
            CalendarPattern.STAGGERED,
            CalendarPattern.RANDOM,
            CalendarPattern.CLUSTERED
        ])
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=3,
            max_duration=12,
            min_requirements=1,
            max_requirements=2,
            topology=topology,
            precedence_density=random.uniform(0.15, 0.25),
            calendar_pattern=calendar,
            num_breaks_per_unit=random.randint(3, 6),
            avg_break_length=random.randint(4, 8),
            calendar_fragmentation=random.uniform(0.4, 0.6),
            scarcity_factor=random.uniform(0.9, 1.2),
            horizon=100 + num_tasks * 5,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier3_{i:03d}.data",
            f"Tier 3 (Medium) - Instance {i}"
        )
    
    print(f"Generated {count} Tier 3 (Medium) instances in {output_dir}/")


def generate_tier4_hard(output_dir: str, count: int = 100, base_seed: int = 4000):
    """Generate hard instances - challenging."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        num_tasks = random.randint(20, 35)
        num_types = random.randint(2, 4)
        units = tuple(random.randint(3, 6) for _ in range(num_types))
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID
        ])
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.HEAVY_START,
            CalendarPattern.HEAVY_END
        ])
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=3,
            max_duration=15,
            min_requirements=1,
            max_requirements=3,
            topology=topology,
            precedence_density=random.uniform(0.2, 0.35),
            calendar_pattern=calendar,
            num_breaks_per_unit=random.randint(5, 8),
            avg_break_length=random.randint(3, 7),
            calendar_fragmentation=random.uniform(0.5, 0.8),
            scarcity_factor=random.uniform(1.0, 1.4),
            horizon=150 + num_tasks * 5,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier4_{i:03d}.data",
            f"Tier 4 (Hard) - Instance {i}"
        )
    
    print(f"Generated {count} Tier 4 (Hard) instances in {output_dir}/")


def generate_tier5_very_hard(output_dir: str, count: int = 100, base_seed: int = 5000):
    """Generate very hard instances - stress test."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        num_tasks = random.randint(35, 60)
        num_types = random.randint(3, 5)
        units = tuple(random.randint(4, 7) for _ in range(num_types))
        topology = random.choice([
            PrecedenceTopology.RANDOM_DAG,
            PrecedenceTopology.GRID
        ])
        calendar = random.choice([
            CalendarPattern.RANDOM,
            CalendarPattern.STAGGERED
        ])
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=2,
            max_duration=15,
            min_requirements=1,
            max_requirements=3,
            topology=topology,
            precedence_density=random.uniform(0.15, 0.3),
            calendar_pattern=calendar,
            num_breaks_per_unit=random.randint(6, 12),
            avg_break_length=random.randint(3, 8),
            calendar_fragmentation=random.uniform(0.6, 0.9),
            scarcity_factor=random.uniform(1.0, 1.3),
            horizon=200 + num_tasks * 5,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/tier5_{i:03d}.data",
            f"Tier 5 (Very Hard) - Instance {i}"
        )
    
    print(f"Generated {count} Tier 5 (Very Hard) instances in {output_dir}/")


def generate_special_calendar_stress(output_dir: str, count: int = 100, base_seed: int = 6000):
    """Generate calendar stress instances - many short breaks, long tasks."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        num_tasks = random.randint(12, 20)
        num_types = random.randint(2, 3)
        units = tuple(random.randint(3, 5) for _ in range(num_types))
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=8,
            max_duration=20,  # Long tasks
            min_requirements=1,
            max_requirements=2,
            topology=random.choice([PrecedenceTopology.PARALLEL, PrecedenceTopology.RANDOM_DAG]),
            precedence_density=0.1,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=random.randint(10, 16),  # Many breaks
            avg_break_length=random.randint(2, 4),       # Short breaks
            calendar_fragmentation=random.uniform(0.85, 0.98),  # High fragmentation
            horizon=120 + num_tasks * 6,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/special_calendar_{i:03d}.data",
            f"Special (Calendar Stress) - Instance {i}"
        )
    
    print(f"Generated {count} Special (Calendar Stress) instances in {output_dir}/")


def generate_special_mode_explosion(output_dir: str, count: int = 100, base_seed: int = 7000):
    """Generate mode explosion instances - many units per type, higher requirements."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        num_tasks = random.randint(10, 18)
        num_types = random.randint(2, 4)
        units = tuple(random.randint(5, 8) for _ in range(num_types))  # Many units
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=3,
            max_duration=10,
            min_requirements=1,
            max_requirements=4,  # Higher requirements -> more combinations
            requirement_probability=0.85,  # Most tasks need most types
            topology=random.choice([PrecedenceTopology.DIAMOND, PrecedenceTopology.RANDOM_DAG]),
            precedence_density=random.uniform(0.15, 0.25),
            calendar_pattern=CalendarPattern.STAGGERED,
            num_breaks_per_unit=random.randint(3, 5),
            avg_break_length=random.randint(4, 8),
            calendar_fragmentation=random.uniform(0.4, 0.6),
            horizon=100 + num_tasks * 5,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/special_modes_{i:03d}.data",
            f"Special (Mode Explosion) - Instance {i}"
        )
    
    print(f"Generated {count} Special (Mode Explosion) instances in {output_dir}/")


def generate_special_tight_windows(output_dir: str, count: int = 100, base_seed: int = 8000):
    """Generate tight windows instances - long breaks, clustered, sequential."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(count):
        seed = base_seed + i
        random.seed(seed)
        
        num_tasks = random.randint(12, 22)
        num_types = random.randint(2, 3)
        units = tuple(random.randint(2, 4) for _ in range(num_types))  # Fewer units
        
        config = BenchmarkConfig(
            num_tasks=num_tasks,
            num_resource_types=num_types,
            units_per_type=units,
            min_duration=4,
            max_duration=12,
            min_requirements=1,
            max_requirements=2,
            topology=random.choice([PrecedenceTopology.CHAIN, PrecedenceTopology.TREE]),
            precedence_density=0.1,
            calendar_pattern=CalendarPattern.CLUSTERED,
            num_breaks_per_unit=random.randint(4, 7),
            avg_break_length=random.randint(8, 15),  # Long breaks
            break_length_variance=0.2,
            calendar_fragmentation=random.uniform(0.2, 0.4),  # Low fragmentation = longer breaks
            horizon=150 + num_tasks * 8,
            seed=seed
        )
        
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(
            inst,
            f"{output_dir}/special_windows_{i:03d}.data",
            f"Special (Tight Windows) - Instance {i}"
        )
    
    print(f"Generated {count} Special (Tight Windows) instances in {output_dir}/")


def generate_all(base_dir: str = "./benchmark_suite", count_per_category: int = 100, master_seed: int = 42):
    """Generate all benchmark categories."""
    import time
    
    print("=" * 60)
    print(f"Generating {count_per_category} instances per category")
    print(f"Total: {count_per_category * 8} instances")
    print("=" * 60)
    
    start = time.time()
    
    # Set master seed for reproducibility
    random.seed(master_seed)
    
    generate_tier1_trivial(f"{base_dir}/tier1_trivial", count_per_category, base_seed=1000)
    generate_tier2_easy(f"{base_dir}/tier2_easy", count_per_category, base_seed=2000)
    generate_tier3_medium(f"{base_dir}/tier3_medium", count_per_category, base_seed=3000)
    generate_tier4_hard(f"{base_dir}/tier4_hard", count_per_category, base_seed=4000)
    generate_tier5_very_hard(f"{base_dir}/tier5_very_hard", count_per_category, base_seed=5000)
    generate_special_calendar_stress(f"{base_dir}/special_calendar_stress", count_per_category, base_seed=6000)
    generate_special_mode_explosion(f"{base_dir}/special_mode_explosion", count_per_category, base_seed=7000)
    generate_special_tight_windows(f"{base_dir}/special_tight_windows", count_per_category, base_seed=8000)
    
    elapsed = time.time() - start
    
    print("=" * 60)
    print(f"Done! Generated {count_per_category * 8} instances in {elapsed:.1f}s")
    print(f"Output directory: {base_dir}/")
    print("=" * 60)


if __name__ == "__main__":
    generate_all("./benchmark_suite", count_per_category=100, master_seed=42)
