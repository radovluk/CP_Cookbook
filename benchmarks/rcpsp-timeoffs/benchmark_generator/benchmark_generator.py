"""
Benchmark Generator for RCPSP with Time-Offs

Generates instances with controllable difficulty across multiple dimensions:
1. Size: tasks, resource types, units
2. Structure: precedence graph topology
3. Scarcity: resource requirements vs. availability
4. Calendar complexity: time-off patterns and fragmentation
"""

import random
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from enum import Enum
import math


class PrecedenceTopology(Enum):
    """Precedence graph structure types."""
    CHAIN = "chain"           # Linear sequence
    PARALLEL = "parallel"     # All tasks in parallel (only start/end deps)
    TREE = "tree"            # Tree structure (one predecessor per task)
    DIAMOND = "diamond"       # Diamond patterns with convergence
    RANDOM_DAG = "random_dag" # Random DAG with density parameter
    GRID = "grid"            # Grid-like structure


class CalendarPattern(Enum):
    """Calendar/time-off patterns."""
    UNIFORM = "uniform"       # Regular breaks at fixed intervals
    STAGGERED = "staggered"  # Breaks offset between units
    CLUSTERED = "clustered"  # All units have breaks at similar times
    RANDOM = "random"        # Random break patterns
    HEAVY_START = "heavy_start"  # More breaks at beginning
    HEAVY_END = "heavy_end"      # More breaks at end


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark generation."""
    # Size parameters
    num_tasks: int = 10                    # Number of actual work tasks (excludes dummy start/end)
    num_resource_types: int = 2            # Number of different resource types
    units_per_type: Tuple[int, ...] = (3, 3)  # Units per resource type
    
    # Task parameters
    min_duration: int = 2
    max_duration: int = 10
    min_requirements: int = 1              # Minimum units required per type
    max_requirements: int = 2              # Maximum units required per type
    requirement_probability: float = 0.7   # Probability a task requires each type
    
    # Precedence parameters
    topology: PrecedenceTopology = PrecedenceTopology.RANDOM_DAG
    precedence_density: float = 0.3        # For RANDOM_DAG: edge probability
    
    # Calendar parameters
    horizon: int = 100                     # Time horizon
    calendar_pattern: CalendarPattern = CalendarPattern.STAGGERED
    num_breaks_per_unit: int = 3           # Average number of unavailability periods
    avg_break_length: int = 5              # Average length of breaks
    break_length_variance: float = 0.3     # Variance in break length (0-1)
    
    # Difficulty modifiers
    scarcity_factor: float = 1.0           # <1 = easy (excess capacity), >1 = hard (tight)
    calendar_fragmentation: float = 0.5    # 0 = few long breaks, 1 = many short breaks
    
    # Random seed for reproducibility
    seed: Optional[int] = None
    
    def __post_init__(self):
        if len(self.units_per_type) != self.num_resource_types:
            raise ValueError("units_per_type must match num_resource_types")


@dataclass
class Instance:
    """Generated instance data."""
    num_tasks: int
    num_types: int
    num_units: int
    tasks: List[Tuple[int, int, List[Tuple[int, int]]]]  # (id, duration, [(type, qty)])
    types: List[Tuple[int, List[int]]]                   # (type_id, [unit_ids])
    units: List[Tuple[int, List[Tuple[int, int]]]]       # (unit_id, [(time, value)])
    precedences: List[Tuple[int, int]]                   # (pred, succ)
    config: BenchmarkConfig = field(repr=False)


class BenchmarkGenerator:
    """Generates RCPSP-TimeOffs benchmark instances."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        if config.seed is not None:
            random.seed(config.seed)
    
    def generate(self) -> Instance:
        """Generate a complete instance."""
        # Build resource structure
        types, units = self._generate_resources()
        
        # Generate tasks
        tasks = self._generate_tasks()
        
        # Generate precedences
        precedences = self._generate_precedences(len(tasks))
        
        # Generate calendars
        calendars = self._generate_calendars(units)
        
        # Combine unit IDs with their calendars
        units_with_calendars = [(uid, calendars[uid]) for uid, _ in units]
        
        return Instance(
            num_tasks=len(tasks),
            num_types=len(types),
            num_units=len(units),
            tasks=tasks,
            types=types,
            units=units_with_calendars,
            precedences=precedences,
            config=self.config
        )
    
    def _generate_resources(self) -> Tuple[List, List]:
        """Generate resource types and units."""
        types = []
        units = []
        unit_id = 0
        
        for type_id, num_units in enumerate(self.config.units_per_type):
            type_units = list(range(unit_id, unit_id + num_units))
            types.append((type_id, type_units))
            
            for uid in type_units:
                units.append((uid, type_id))  # (unit_id, type_id)
            
            unit_id += num_units
        
        return types, units
    
    def _generate_tasks(self) -> List[Tuple[int, int, List[Tuple[int, int]]]]:
        """Generate tasks with requirements."""
        tasks = []
        
        # Dummy start task (id=0)
        start_reqs = [(t, 0) for t in range(self.config.num_resource_types)]
        tasks.append((0, 0, start_reqs))
        
        # Work tasks
        for task_id in range(1, self.config.num_tasks + 1):
            duration = random.randint(self.config.min_duration, self.config.max_duration)
            
            requirements = []
            for type_id in range(self.config.num_resource_types):
                if random.random() < self.config.requirement_probability:
                    max_avail = self.config.units_per_type[type_id]
                    max_req = min(self.config.max_requirements, max_avail)
                    qty = random.randint(self.config.min_requirements, max_req)
                    
                    # Apply scarcity factor
                    if self.config.scarcity_factor > 1:
                        # Higher scarcity = more likely to require more units
                        qty = min(max_avail, int(qty * (1 + (self.config.scarcity_factor - 1) * 0.3)))
                else:
                    qty = 0
                requirements.append((type_id, qty))
            
            # Ensure at least one requirement
            if all(q == 0 for _, q in requirements):
                type_id = random.randint(0, self.config.num_resource_types - 1)
                requirements[type_id] = (type_id, 1)
            
            tasks.append((task_id, duration, requirements))
        
        # Dummy end task
        end_id = self.config.num_tasks + 1
        end_reqs = [(t, 0) for t in range(self.config.num_resource_types)]
        tasks.append((end_id, 0, end_reqs))
        
        return tasks
    
    def _generate_precedences(self, num_tasks: int) -> List[Tuple[int, int]]:
        """Generate precedence constraints based on topology."""
        start_id = 0
        end_id = num_tasks - 1
        work_tasks = list(range(1, end_id))
        
        precedences = []
        
        if self.config.topology == PrecedenceTopology.CHAIN:
            # Linear chain: start -> 1 -> 2 -> ... -> end
            for i in range(num_tasks - 1):
                precedences.append((i, i + 1))
        
        elif self.config.topology == PrecedenceTopology.PARALLEL:
            # All work tasks in parallel: start -> all, all -> end
            for t in work_tasks:
                precedences.append((start_id, t))
                precedences.append((t, end_id))
        
        elif self.config.topology == PrecedenceTopology.TREE:
            # Tree structure with branching
            branch_factor = max(2, len(work_tasks) // 4)
            levels = []
            remaining = work_tasks.copy()
            
            # First level connects to start
            first_level = remaining[:branch_factor]
            remaining = remaining[branch_factor:]
            for t in first_level:
                precedences.append((start_id, t))
            levels.append(first_level)
            
            # Build tree levels
            while remaining:
                next_level = remaining[:branch_factor * len(levels[-1])]
                remaining = remaining[len(next_level):]
                
                for i, t in enumerate(next_level):
                    parent = levels[-1][i % len(levels[-1])]
                    precedences.append((parent, t))
                levels.append(next_level)
            
            # Connect last level to end
            for t in levels[-1]:
                precedences.append((t, end_id))
        
        elif self.config.topology == PrecedenceTopology.DIAMOND:
            # Diamond patterns
            if len(work_tasks) >= 4:
                group_size = max(2, len(work_tasks) // 4)
                groups = [work_tasks[i:i+group_size] for i in range(0, len(work_tasks), group_size)]
                
                for g in groups:
                    precedences.append((start_id, g[0]))
                    if len(g) > 2:
                        # Fan out
                        for t in g[1:-1]:
                            precedences.append((g[0], t))
                            precedences.append((t, g[-1]))
                    elif len(g) == 2:
                        precedences.append((g[0], g[1]))
                    precedences.append((g[-1], end_id))
            else:
                # Fall back to parallel
                for t in work_tasks:
                    precedences.append((start_id, t))
                    precedences.append((t, end_id))
        
        elif self.config.topology == PrecedenceTopology.RANDOM_DAG:
            # Random DAG with density parameter
            for t in work_tasks:
                precedences.append((start_id, t))
                precedences.append((t, end_id))
            
            # Add random edges between work tasks
            for i in range(len(work_tasks)):
                for j in range(i + 1, len(work_tasks)):
                    if random.random() < self.config.precedence_density:
                        precedences.append((work_tasks[i], work_tasks[j]))
        
        elif self.config.topology == PrecedenceTopology.GRID:
            # Grid-like structure
            side = int(math.sqrt(len(work_tasks)))
            if side * side < len(work_tasks):
                side += 1
            
            grid = [[None] * side for _ in range(side)]
            idx = 0
            for i in range(side):
                for j in range(side):
                    if idx < len(work_tasks):
                        grid[i][j] = work_tasks[idx]
                        idx += 1
            
            # Connect start to first row
            for j in range(side):
                if grid[0][j] is not None:
                    precedences.append((start_id, grid[0][j]))
            
            # Grid edges
            for i in range(side):
                for j in range(side):
                    if grid[i][j] is not None:
                        # Right neighbor
                        if j + 1 < side and grid[i][j+1] is not None:
                            precedences.append((grid[i][j], grid[i][j+1]))
                        # Down neighbor
                        if i + 1 < side and grid[i+1][j] is not None:
                            precedences.append((grid[i][j], grid[i+1][j]))
            
            # Connect last row to end
            for j in range(side):
                if grid[side-1][j] is not None:
                    precedences.append((grid[side-1][j], end_id))
        
        return list(set(precedences))  # Remove duplicates
    
    def _generate_calendars(self, units: List[Tuple[int, int]]) -> Dict[int, List[Tuple[int, int]]]:
        """Generate availability calendars for all units."""
        calendars = {}
        horizon = self.config.horizon
        
        for i, (unit_id, type_id) in enumerate(units):
            if self.config.calendar_pattern == CalendarPattern.UNIFORM:
                calendar = self._uniform_calendar(horizon)
            elif self.config.calendar_pattern == CalendarPattern.STAGGERED:
                offset = i * (horizon // (len(units) + 1))
                calendar = self._staggered_calendar(horizon, offset)
            elif self.config.calendar_pattern == CalendarPattern.CLUSTERED:
                calendar = self._clustered_calendar(horizon)
            elif self.config.calendar_pattern == CalendarPattern.RANDOM:
                calendar = self._random_calendar(horizon)
            elif self.config.calendar_pattern == CalendarPattern.HEAVY_START:
                calendar = self._weighted_calendar(horizon, weight_start=True)
            elif self.config.calendar_pattern == CalendarPattern.HEAVY_END:
                calendar = self._weighted_calendar(horizon, weight_start=False)
            else:
                calendar = self._random_calendar(horizon)
            
            calendars[unit_id] = calendar
        
        return calendars
    
    def _uniform_calendar(self, horizon: int) -> List[Tuple[int, int]]:
        """Generate uniform break pattern."""
        steps = [(0, 100)]
        num_breaks = self.config.num_breaks_per_unit
        
        if num_breaks > 0:
            interval = horizon // (num_breaks + 1)
            for i in range(1, num_breaks + 1):
                break_start = i * interval
                break_len = self._vary_break_length()
                if break_start + break_len < horizon:
                    steps.append((break_start, 0))
                    steps.append((break_start + break_len, 100))
        
        return self._normalize_calendar(steps, horizon)
    
    def _staggered_calendar(self, horizon: int, offset: int) -> List[Tuple[int, int]]:
        """Generate staggered break pattern with offset."""
        steps = [(0, 100)]
        num_breaks = self.config.num_breaks_per_unit
        
        if num_breaks > 0:
            interval = horizon // (num_breaks + 1)
            for i in range(1, num_breaks + 1):
                break_start = (i * interval + offset) % horizon
                break_len = self._vary_break_length()
                if break_start + break_len < horizon:
                    steps.append((break_start, 0))
                    steps.append((break_start + break_len, 100))
        
        return self._normalize_calendar(steps, horizon)
    
    def _clustered_calendar(self, horizon: int) -> List[Tuple[int, int]]:
        """Generate clustered breaks (all units similar)."""
        # Use a fixed seed offset to ensure clustering
        base_offset = horizon // 4
        steps = [(0, 100)]
        num_breaks = self.config.num_breaks_per_unit
        
        if num_breaks > 0:
            for i in range(num_breaks):
                # Cluster around multiples of horizon / num_breaks
                cluster_center = base_offset + i * (horizon // (num_breaks + 1))
                break_start = cluster_center + random.randint(-2, 2)
                break_start = max(0, min(break_start, horizon - 5))
                break_len = self._vary_break_length()
                
                if break_start + break_len < horizon:
                    steps.append((break_start, 0))
                    steps.append((break_start + break_len, 100))
        
        return self._normalize_calendar(steps, horizon)
    
    def _random_calendar(self, horizon: int) -> List[Tuple[int, int]]:
        """Generate random break pattern."""
        steps = [(0, 100)]
        
        # Adjust number of breaks based on fragmentation
        num_breaks = int(self.config.num_breaks_per_unit * 
                        (0.5 + self.config.calendar_fragmentation))
        
        breaks = []
        for _ in range(num_breaks):
            break_start = random.randint(1, horizon - 5)
            break_len = self._vary_break_length()
            breaks.append((break_start, break_len))
        
        # Sort and add breaks
        breaks.sort()
        for start, length in breaks:
            if start + length < horizon:
                steps.append((start, 0))
                steps.append((start + length, 100))
        
        return self._normalize_calendar(steps, horizon)
    
    def _weighted_calendar(self, horizon: int, weight_start: bool) -> List[Tuple[int, int]]:
        """Generate calendar with breaks weighted toward start or end."""
        steps = [(0, 100)]
        num_breaks = self.config.num_breaks_per_unit
        
        for _ in range(num_breaks):
            if weight_start:
                # Exponential distribution favoring start
                t = int(horizon * (1 - random.random() ** 2))
                t = horizon - t  # Flip to favor start
            else:
                # Exponential distribution favoring end
                t = int(horizon * (1 - random.random() ** 2))
            
            break_start = max(1, min(t, horizon - 5))
            break_len = self._vary_break_length()
            
            if break_start + break_len < horizon:
                steps.append((break_start, 0))
                steps.append((break_start + break_len, 100))
        
        return self._normalize_calendar(steps, horizon)
    
    def _vary_break_length(self) -> int:
        """Generate break length with variance."""
        base = self.config.avg_break_length
        variance = self.config.break_length_variance
        
        # Apply fragmentation: high fragmentation = shorter breaks
        base = int(base * (1.5 - self.config.calendar_fragmentation))
        
        min_len = max(1, int(base * (1 - variance)))
        max_len = max(min_len + 1, int(base * (1 + variance)))
        
        return random.randint(min_len, max_len)
    
    def _normalize_calendar(self, steps: List[Tuple[int, int]], horizon: int) -> List[Tuple[int, int]]:
        """Normalize calendar: merge overlaps, ensure proper format."""
        if not steps:
            return [(0, 100), (horizon, 0)]
        
        # Sort by time
        steps.sort(key=lambda x: x[0])
        
        # Build timeline
        events = {}
        for t, v in steps:
            events[t] = v
        
        # Process into non-overlapping intervals
        times = sorted(events.keys())
        result = []
        current_value = 100
        
        for t in times:
            if events[t] != current_value:
                result.append((t, events[t]))
                current_value = events[t]
        
        # Ensure starts with time 0
        if not result or result[0][0] != 0:
            result.insert(0, (0, 100))
        
        # Ensure ends with unavailable
        result.append((horizon, 0))
        
        return result


def save_instance(instance: Instance, filename: str, description: str = ""):
    """Save instance to file in the expected format."""
    with open(filename, 'w') as f:
        if description:
            f.write(f"# {description}\n")
        f.write(f"# Generated with config: N={instance.config.num_tasks}, "
                f"K={instance.config.num_resource_types}, "
                f"topology={instance.config.topology.value}, "
                f"calendar={instance.config.calendar_pattern.value}\n\n")
        
        # Header
        f.write(f"# HEADER: <num_tasks> <num_types> <num_units>\n")
        f.write(f"{instance.num_tasks} {instance.num_types} {instance.num_units}\n\n")
        
        # Resource types
        f.write("# RESOURCE TYPES\n")
        f.write("# Format: <type_id> <num_units> <unit_id1> <unit_id2> ...\n")
        for type_id, unit_ids in instance.types:
            f.write(f"{type_id} {len(unit_ids)} {' '.join(map(str, unit_ids))}\n")
        f.write("\n")
        
        # Resource units with calendars
        f.write("# RESOURCE UNITS (Calendars)\n")
        f.write("# Format: <unit_id> <num_steps> <t1> <v1> <t2> <v2> ...\n")
        for unit_id, calendar in instance.units:
            steps_flat = [str(x) for t, v in calendar for x in (t, v)]
            f.write(f"{unit_id} {len(calendar)} {' '.join(steps_flat)}\n")
        f.write("\n")
        
        # Tasks
        f.write("# TASKS\n")
        f.write("# Format: <task_id> <size> <num_reqs>\n")
        f.write("# Then for each requirement: <type_id> <qty>\n")
        for task_id, duration, requirements in instance.tasks:
            f.write(f"{task_id} {duration} {len(requirements)}\n")
            for type_id, qty in requirements:
                f.write(f" {type_id} {qty}\n")
        f.write("\n")
        
        # Precedences
        f.write("# PRECEDENCES\n")
        f.write(f"{len(instance.precedences)}\n")
        for pred, succ in instance.precedences:
            f.write(f"{pred} {succ}\n")


def generate_benchmark_suite(output_dir: str, seed: int = 42):
    """Generate a complete benchmark suite with progressive difficulty."""
    os.makedirs(output_dir, exist_ok=True)
    
    random.seed(seed)
    instance_id = 0
    
    # ============================================
    # TIER 1: TRIVIAL (warm-up instances)
    # ============================================
    tier1_configs = [
        # Minimal instance
        BenchmarkConfig(
            num_tasks=3,
            num_resource_types=1,
            units_per_type=(2,),
            min_duration=2, max_duration=4,
            topology=PrecedenceTopology.CHAIN,
            calendar_pattern=CalendarPattern.UNIFORM,
            num_breaks_per_unit=1,
            horizon=30,
            seed=seed + instance_id
        ),
        # Small parallel
        BenchmarkConfig(
            num_tasks=4,
            num_resource_types=1,
            units_per_type=(3,),
            min_duration=2, max_duration=5,
            topology=PrecedenceTopology.PARALLEL,
            calendar_pattern=CalendarPattern.STAGGERED,
            num_breaks_per_unit=2,
            horizon=40,
            seed=seed + instance_id + 1
        ),
    ]
    
    for i, config in enumerate(tier1_configs):
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(inst, f"{output_dir}/tier1_{i:02d}_trivial.data",
                     f"Tier 1 (Trivial) - Instance {i}")
        instance_id += 1
    
    # ============================================
    # TIER 2: EASY (small but nontrivial)
    # ============================================
    tier2_configs = [
        BenchmarkConfig(
            num_tasks=6,
            num_resource_types=2,
            units_per_type=(2, 2),
            min_duration=3, max_duration=6,
            topology=PrecedenceTopology.TREE,
            calendar_pattern=CalendarPattern.STAGGERED,
            num_breaks_per_unit=2,
            horizon=50,
            seed=seed + instance_id
        ),
        BenchmarkConfig(
            num_tasks=8,
            num_resource_types=2,
            units_per_type=(3, 2),
            min_duration=2, max_duration=8,
            topology=PrecedenceTopology.DIAMOND,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=3,
            horizon=60,
            seed=seed + instance_id + 1
        ),
        BenchmarkConfig(
            num_tasks=10,
            num_resource_types=1,
            units_per_type=(4,),
            min_duration=3, max_duration=7,
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=0.15,
            calendar_pattern=CalendarPattern.UNIFORM,
            num_breaks_per_unit=3,
            horizon=70,
            seed=seed + instance_id + 2
        ),
    ]
    
    for i, config in enumerate(tier2_configs):
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(inst, f"{output_dir}/tier2_{i:02d}_easy.data",
                     f"Tier 2 (Easy) - Instance {i}")
        instance_id += 1
    
    # ============================================
    # TIER 3: MEDIUM (standard difficulty)
    # ============================================
    tier3_configs = [
        BenchmarkConfig(
            num_tasks=15,
            num_resource_types=2,
            units_per_type=(4, 3),
            min_duration=3, max_duration=10,
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=0.2,
            calendar_pattern=CalendarPattern.STAGGERED,
            num_breaks_per_unit=4,
            horizon=100,
            seed=seed + instance_id
        ),
        BenchmarkConfig(
            num_tasks=20,
            num_resource_types=3,
            units_per_type=(3, 3, 2),
            min_duration=2, max_duration=8,
            topology=PrecedenceTopology.GRID,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=4,
            horizon=120,
            seed=seed + instance_id + 1
        ),
        # Higher scarcity
        BenchmarkConfig(
            num_tasks=12,
            num_resource_types=2,
            units_per_type=(3, 2),
            min_duration=4, max_duration=12,
            max_requirements=2,
            topology=PrecedenceTopology.DIAMOND,
            calendar_pattern=CalendarPattern.CLUSTERED,
            num_breaks_per_unit=5,
            scarcity_factor=1.2,
            horizon=100,
            seed=seed + instance_id + 2
        ),
    ]
    
    for i, config in enumerate(tier3_configs):
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(inst, f"{output_dir}/tier3_{i:02d}_medium.data",
                     f"Tier 3 (Medium) - Instance {i}")
        instance_id += 1
    
    # ============================================
    # TIER 4: HARD (challenging instances)
    # ============================================
    tier4_configs = [
        # Many tasks, complex precedences
        BenchmarkConfig(
            num_tasks=30,
            num_resource_types=3,
            units_per_type=(4, 4, 3),
            min_duration=3, max_duration=12,
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=0.25,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=6,
            horizon=200,
            seed=seed + instance_id
        ),
        # High fragmentation
        BenchmarkConfig(
            num_tasks=25,
            num_resource_types=2,
            units_per_type=(5, 4),
            min_duration=2, max_duration=8,
            topology=PrecedenceTopology.GRID,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=8,
            calendar_fragmentation=0.8,
            horizon=150,
            seed=seed + instance_id + 1
        ),
        # High scarcity
        BenchmarkConfig(
            num_tasks=20,
            num_resource_types=3,
            units_per_type=(3, 2, 2),
            min_duration=5, max_duration=15,
            max_requirements=2,
            topology=PrecedenceTopology.DIAMOND,
            calendar_pattern=CalendarPattern.HEAVY_START,
            num_breaks_per_unit=5,
            scarcity_factor=1.4,
            horizon=180,
            seed=seed + instance_id + 2
        ),
    ]
    
    for i, config in enumerate(tier4_configs):
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(inst, f"{output_dir}/tier4_{i:02d}_hard.data",
                     f"Tier 4 (Hard) - Instance {i}")
        instance_id += 1
    
    # ============================================
    # TIER 5: VERY HARD (stress test)
    # ============================================
    tier5_configs = [
        # Large scale
        BenchmarkConfig(
            num_tasks=50,
            num_resource_types=4,
            units_per_type=(5, 5, 4, 3),
            min_duration=3, max_duration=15,
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=0.2,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=8,
            calendar_fragmentation=0.7,
            horizon=300,
            seed=seed + instance_id
        ),
        # Dense precedences + fragmentation
        BenchmarkConfig(
            num_tasks=40,
            num_resource_types=3,
            units_per_type=(6, 5, 4),
            min_duration=2, max_duration=10,
            topology=PrecedenceTopology.RANDOM_DAG,
            precedence_density=0.35,
            calendar_pattern=CalendarPattern.STAGGERED,
            num_breaks_per_unit=10,
            calendar_fragmentation=0.9,
            horizon=250,
            seed=seed + instance_id + 1
        ),
    ]
    
    for i, config in enumerate(tier5_configs):
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        save_instance(inst, f"{output_dir}/tier5_{i:02d}_very_hard.data",
                     f"Tier 5 (Very Hard) - Instance {i}")
        instance_id += 1
    
    # ============================================
    # SPECIAL: Variant-specific challenges
    # ============================================
    special_configs = [
        # Calendar nightmare (many small gaps - tests No Migration)
        BenchmarkConfig(
            num_tasks=15,
            num_resource_types=2,
            units_per_type=(4, 3),
            min_duration=8, max_duration=15,  # Long tasks
            topology=PrecedenceTopology.PARALLEL,
            calendar_pattern=CalendarPattern.RANDOM,
            num_breaks_per_unit=12,
            avg_break_length=2,  # Short breaks
            calendar_fragmentation=0.95,
            horizon=150,
            seed=seed + instance_id
        ),
        # Mode explosion (tests Blocked variant with many combinations)
        BenchmarkConfig(
            num_tasks=12,
            num_resource_types=3,
            units_per_type=(5, 5, 4),  # Many units per type
            min_duration=3, max_duration=8,
            min_requirements=1,
            max_requirements=3,  # Higher requirements
            topology=PrecedenceTopology.DIAMOND,
            calendar_pattern=CalendarPattern.STAGGERED,
            num_breaks_per_unit=4,
            horizon=100,
            seed=seed + instance_id + 1
        ),
        # Tight windows (tests Released variant - few valid segments)
        BenchmarkConfig(
            num_tasks=18,
            num_resource_types=2,
            units_per_type=(3, 3),
            min_duration=4, max_duration=10,
            topology=PrecedenceTopology.CHAIN,  # Sequential
            calendar_pattern=CalendarPattern.CLUSTERED,
            num_breaks_per_unit=6,
            avg_break_length=8,  # Long breaks
            horizon=200,
            seed=seed + instance_id + 2
        ),
    ]
    
    for i, config in enumerate(special_configs):
        gen = BenchmarkGenerator(config)
        inst = gen.generate()
        labels = ["calendar_stress", "mode_explosion", "tight_windows"]
        save_instance(inst, f"{output_dir}/special_{labels[i]}.data",
                     f"Special Challenge - {labels[i]}")
        instance_id += 1
    
    print(f"Generated {instance_id} benchmark instances in '{output_dir}/'")
    return instance_id


if __name__ == "__main__":
    generate_benchmark_suite("./benchmarks", seed=42)
