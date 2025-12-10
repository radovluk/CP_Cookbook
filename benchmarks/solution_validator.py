"""
Solution Validator for RCPSP with Time-Offs

Validates solutions for all 6 problem variants:
1. No Migration | No Delays
2. Migration | No Delays  
3. No Migration | Delays | Blocked
4. Migration | Delays
5. Multi-Resource Heterogeneous Policy
6. No Migration | Delays | Released

Each variant has specific constraints that must be verified.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Optional
from enum import Enum


class ProblemVariant(Enum):
    """The 6 problem variants."""
    NO_MIG_NO_DELAY = 1       # Tasks continuous, resources fixed
    MIG_NO_DELAY = 2          # Tasks continuous, resources can switch
    NO_MIG_DELAY_BLOCKED = 3  # Tasks can pause, resources blocked during pause
    MIG_DELAY = 4             # Tasks can pause, resources can switch
    HETEROGENEOUS = 5         # Mixed policy per resource type
    NO_MIG_DELAY_RELEASED = 6 # Tasks can pause, resources released during pause


@dataclass
class TaskAssignment:
    """Assignment of a task in a solution."""
    task_id: int
    segments: List[Tuple[int, int, Tuple[int, ...]]]  # [(start, end, (resource_ids...)), ...]
    
    @property
    def start(self) -> int:
        if not self.segments:
            return 0
        return min(s for s, e, r in self.segments)
    
    @property
    def end(self) -> int:
        if not self.segments:
            return 0
        return max(e for s, e, r in self.segments)
    
    @property
    def total_work(self) -> int:
        return sum(e - s for s, e, r in self.segments)
    
    @property
    def all_resources(self) -> Set[int]:
        return set(r for _, _, resources in self.segments for r in resources)
    
    @property  
    def is_dummy(self) -> bool:
        """Check if this is a dummy task (zero-duration, possibly empty segments)."""
        if not self.segments:
            return True
        return all(s == e for s, e, _ in self.segments)


@dataclass
class Solution:
    """Complete solution to an RCPSP instance."""
    assignments: Dict[int, TaskAssignment]  # task_id -> assignment
    makespan: int
    
    @classmethod
    def from_dict(cls, data: Dict[int, List[Tuple[int, int, Tuple[int, ...]]]]) -> 'Solution':
        """Create solution from dictionary format."""
        assignments = {tid: TaskAssignment(tid, segs) for tid, segs in data.items()}
        makespan = max((a.end for a in assignments.values()), default=0)
        return cls(assignments, makespan)


@dataclass  
class ValidationResult:
    """Result of validating a solution."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    computed_makespan: int
    
    def __str__(self):
        if self.is_valid:
            return f"✓ Valid (makespan={self.computed_makespan})"
        else:
            return f"✗ Invalid:\n  " + "\n  ".join(self.errors)


class SolutionValidator:
    """Validates solutions against instance constraints."""
    
    def __init__(self, 
                 tasks: List[Tuple[int, int, List[Tuple[int, int]]]],
                 types: List[Tuple[int, List[int]]],
                 units: List[Tuple[int, List[Tuple[int, int]]]],
                 precedences: List[Tuple[int, int]],
                 fixed_types: Optional[Set[int]] = None,
                 migration_types: Optional[Set[int]] = None):
        """
        Initialize validator with instance data.
        
        Args:
            tasks: [(task_id, duration, [(type_id, qty), ...]), ...]
            types: [(type_id, [unit_ids]), ...]
            units: [(unit_id, [(time, value), ...]), ...]
            precedences: [(pred_task, succ_task), ...]
            fixed_types: Set of type IDs that require fixed assignment (for HETEROGENEOUS)
            migration_types: Set of type IDs that allow migration (for HETEROGENEOUS)
        """
        self.tasks = {t[0]: (t[1], t[2]) for t in tasks}  # id -> (duration, requirements)
        self.type_map = {t[0]: set(t[1]) for t in types}  # type_id -> {unit_ids}
        self.unit_calendar = {u[0]: u[1] for u in units}  # unit_id -> [(time, value), ...]
        self.precedences = precedences
        
        # Build reverse mapping: unit_id -> type_id
        self.unit_to_type = {}
        for type_id, unit_ids in types:
            for uid in unit_ids:
                self.unit_to_type[uid] = type_id
        
        # For heterogeneous policy
        self.fixed_types = fixed_types or set()
        self.migration_types = migration_types or set()
    
    def get_availability(self, unit_id: int, time: int) -> bool:
        """Check if a unit is available at a specific time."""
        calendar = self.unit_calendar.get(unit_id, [(0, 100)])
        value = 0
        for t, v in calendar:
            if time >= t:
                value = v
            else:
                break
        return value > 0
    
    def get_available_intervals(self, unit_id: int, horizon: int = 100000) -> List[Tuple[int, int]]:
        """Get all availability windows for a unit."""
        calendar = self.unit_calendar.get(unit_id, [(0, 100)])
        intervals = []
        current_start = None
        
        for i, (t, v) in enumerate(calendar):
            if v > 0 and current_start is None:
                current_start = t
            elif v == 0 and current_start is not None:
                intervals.append((current_start, t))
                current_start = None
        
        if current_start is not None:
            intervals.append((current_start, horizon))
        
        return intervals
    
    def validate(self, solution: Solution, variant: ProblemVariant) -> ValidationResult:
        """
        Validate a solution for a specific problem variant.
        
        Returns ValidationResult with is_valid, errors, warnings.
        """
        errors = []
        warnings = []
        
        # Common validations for all variants
        errors.extend(self._check_task_completeness(solution))
        errors.extend(self._check_precedences(solution))
        errors.extend(self._check_resource_conflicts(solution))
        
        # Variant-specific validations
        if variant == ProblemVariant.NO_MIG_NO_DELAY:
            errors.extend(self._check_no_migration(solution))
            errors.extend(self._check_no_delays(solution))
            errors.extend(self._check_calendar_continuous(solution))
            
        elif variant == ProblemVariant.MIG_NO_DELAY:
            errors.extend(self._check_no_delays(solution))
            errors.extend(self._check_aggregate_capacity(solution))
            
        elif variant == ProblemVariant.NO_MIG_DELAY_BLOCKED:
            errors.extend(self._check_no_migration(solution))
            errors.extend(self._check_blocked_resources(solution))
            errors.extend(self._check_work_during_availability(solution))
            
        elif variant == ProblemVariant.MIG_DELAY:
            errors.extend(self._check_aggregate_capacity(solution))
            # Segments can be placed anywhere within capacity windows
            
        elif variant == ProblemVariant.HETEROGENEOUS:
            errors.extend(self._check_heterogeneous_policy(solution))
            
        elif variant == ProblemVariant.NO_MIG_DELAY_RELEASED:
            errors.extend(self._check_no_migration(solution))
            errors.extend(self._check_segments_in_availability(solution))
            # Resources NOT blocked during unavailability (this is the difference from BLOCKED)
        
        # Check work amounts
        work_errors = self._check_work_amounts(solution)
        errors.extend(work_errors)
        
        computed_makespan = max((a.end for a in solution.assignments.values()), default=0)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            computed_makespan=computed_makespan
        )
    
    def _check_task_completeness(self, solution: Solution) -> List[str]:
        """Check all tasks are in the solution."""
        errors = []
        for task_id in self.tasks:
            if task_id not in solution.assignments:
                errors.append(f"Task {task_id} is missing from solution")
        return errors
    
    def _check_work_amounts(self, solution: Solution) -> List[str]:
        """Check each task has the correct amount of work done."""
        errors = []
        for task_id, (duration, reqs) in self.tasks.items():
            if task_id not in solution.assignments:
                continue
            assignment = solution.assignments[task_id]
            
            # Dummy tasks (duration=0) can have empty segments
            if duration == 0:
                continue
            
            actual_work = assignment.total_work
            if actual_work != duration:
                errors.append(
                    f"Task {task_id}: work done ({actual_work}) != required duration ({duration})"
                )
        return errors
    
    def _check_precedences(self, solution: Solution) -> List[str]:
        """Check all precedence constraints are satisfied."""
        errors = []
        for pred, succ in self.precedences:
            if pred not in solution.assignments or succ not in solution.assignments:
                continue
            
            pred_assign = solution.assignments[pred]
            succ_assign = solution.assignments[succ]
            
            # Handle dummy tasks (zero duration)
            pred_dur = self.tasks.get(pred, (0, []))[0]
            succ_dur = self.tasks.get(succ, (0, []))[0]
            
            pred_end = pred_assign.end
            succ_start = succ_assign.start
            
            # For dummy tasks with no segments, they're at time 0 by default
            # which is fine for start dummies, but end dummies should be after all preds
            if pred_dur == 0 and not pred_assign.segments:
                # Dummy predecessor with no placement - skip this check
                # (it's effectively at t=0 which is always valid as a start)
                continue
            if succ_dur == 0 and not succ_assign.segments:
                # Dummy successor with no placement - skip
                continue
            
            if pred_end > succ_start:
                errors.append(
                    f"Precedence violated: Task {pred} ends at {pred_end}, "
                    f"Task {succ} starts at {succ_start}"
                )
        return errors
    
    def _check_resource_conflicts(self, solution: Solution) -> List[str]:
        """Check no resource is used by multiple tasks at the same time."""
        errors = []
        
        # Build resource usage timeline
        resource_usage: Dict[int, List[Tuple[int, int, int]]] = {}  # unit_id -> [(start, end, task)]
        
        for task_id, assignment in solution.assignments.items():
            for start, end, resources in assignment.segments:
                for r in resources:
                    if r not in resource_usage:
                        resource_usage[r] = []
                    resource_usage[r].append((start, end, task_id))
        
        # Check for overlaps
        for unit_id, usages in resource_usage.items():
            usages.sort()
            for i in range(len(usages)):
                for j in range(i + 1, len(usages)):
                    s1, e1, t1 = usages[i]
                    s2, e2, t2 = usages[j]
                    # Check overlap
                    if s1 < e2 and s2 < e1:
                        errors.append(
                            f"Resource {unit_id} conflict: Task {t1} [{s1},{e1}) "
                            f"overlaps Task {t2} [{s2},{e2})"
                        )
        
        return errors
    
    def _check_no_migration(self, solution: Solution) -> List[str]:
        """Check that each task uses the same resources throughout."""
        errors = []
        for task_id, assignment in solution.assignments.items():
            if not assignment.segments:
                continue
            
            first_resources = set(assignment.segments[0][2])
            for start, end, resources in assignment.segments[1:]:
                if set(resources) != first_resources:
                    errors.append(
                        f"Task {task_id}: Migration detected - resources changed from "
                        f"{first_resources} to {set(resources)}"
                    )
                    break
        return errors
    
    def _check_no_delays(self, solution: Solution) -> List[str]:
        """Check tasks execute continuously without interruption."""
        errors = []
        for task_id, assignment in solution.assignments.items():
            if len(assignment.segments) > 1:
                # Check segments are contiguous
                for i in range(len(assignment.segments) - 1):
                    _, end1, _ = assignment.segments[i]
                    start2, _, _ = assignment.segments[i + 1]
                    if end1 != start2:
                        errors.append(
                            f"Task {task_id}: Gap detected between [{end1}] and [{start2}]"
                        )
        return errors
    
    def _check_calendar_continuous(self, solution: Solution) -> List[str]:
        """Check all assigned resources are available throughout task execution."""
        errors = []
        for task_id, assignment in solution.assignments.items():
            for start, end, resources in assignment.segments:
                for r in resources:
                    # Check availability at every time point
                    for t in range(start, end):
                        if not self.get_availability(r, t):
                            errors.append(
                                f"Task {task_id}: Resource {r} unavailable at time {t} "
                                f"during execution [{start},{end})"
                            )
                            break  # One error per resource is enough
        return errors
    
    def _check_aggregate_capacity(self, solution: Solution) -> List[str]:
        """Check aggregate capacity constraints for migration variants."""
        errors = []
        
        # For each type, compute capacity timeline
        # Then check all tasks fit within capacity
        
        # Build demand by type at each time point
        time_points = set([0])
        for assignment in solution.assignments.values():
            for start, end, _ in assignment.segments:
                time_points.add(start)
                time_points.add(end)
        
        for calendar in self.unit_calendar.values():
            for t, _ in calendar:
                time_points.add(t)
        
        time_points = sorted(time_points)
        
        for type_id, units in self.type_map.items():
            for i in range(len(time_points) - 1):
                t = time_points[i]
                
                # Capacity at time t
                capacity = sum(1 for u in units if self.get_availability(u, t))
                
                # Demand at time t
                demand = 0
                for task_id, (duration, reqs) in self.tasks.items():
                    if task_id not in solution.assignments:
                        continue
                    assignment = solution.assignments[task_id]
                    
                    # Check if task is active at time t
                    for start, end, resources in assignment.segments:
                        if start <= t < end:
                            # Find requirement for this type
                            for req_type, qty in reqs:
                                if req_type == type_id:
                                    demand += qty
                                    break
                
                if demand > capacity:
                    errors.append(
                        f"Type {type_id} over capacity at time {t}: "
                        f"demand={demand}, capacity={capacity}"
                    )
        
        return errors
    
    def _check_blocked_resources(self, solution: Solution) -> List[str]:
        """
        For BLOCKED variant: resources remain blocked during task span,
        but work only accumulates during joint availability.
        """
        errors = []
        
        for task_id, assignment in solution.assignments.items():
            if not assignment.segments:
                continue
            
            # Get all resources and span
            resources = assignment.all_resources
            span_start = assignment.start
            span_end = assignment.end
            
            # Check no other task uses these resources during span
            for other_id, other_assignment in solution.assignments.items():
                if other_id == task_id:
                    continue
                
                for start, end, other_resources in other_assignment.segments:
                    overlap_start = max(span_start, start)
                    overlap_end = min(span_end, end)
                    
                    if overlap_start < overlap_end:
                        shared = resources & set(other_resources)
                        if shared:
                            errors.append(
                                f"Task {task_id} blocks resources {shared} during "
                                f"[{span_start},{span_end}), but Task {other_id} uses "
                                f"them at [{start},{end})"
                            )
        
        return errors
    
    def _check_work_during_availability(self, solution: Solution) -> List[str]:
        """Check work only accumulates during joint availability."""
        errors = []
        
        for task_id, assignment in solution.assignments.items():
            for start, end, resources in assignment.segments:
                if not resources:
                    continue
                
                for t in range(start, end):
                    # All resources must be available for work to count
                    if not all(self.get_availability(r, t) for r in resources):
                        errors.append(
                            f"Task {task_id}: Work claimed at time {t} but not all "
                            f"resources {resources} are available"
                        )
                        break
        
        return errors
    
    def _check_segments_in_availability(self, solution: Solution) -> List[str]:
        """Check each segment is within availability windows of its resources."""
        errors = []
        
        for task_id, assignment in solution.assignments.items():
            for start, end, resources in assignment.segments:
                for r in resources:
                    intervals = self.get_available_intervals(r)
                    
                    # Check segment [start, end) is within some interval
                    contained = any(
                        istart <= start and end <= iend 
                        for istart, iend in intervals
                    )
                    
                    if not contained:
                        errors.append(
                            f"Task {task_id} segment [{start},{end}) with resource {r} "
                            f"not contained in any availability window"
                        )
        
        return errors
    
    def _check_heterogeneous_policy(self, solution: Solution) -> List[str]:
        """Check heterogeneous policy: fixed types no migration, migration types aggregate."""
        errors = []
        
        for task_id, assignment in solution.assignments.items():
            if not assignment.segments:
                continue
            
            # Separate resources by policy type
            fixed_resources = set()
            migration_resources = set()
            
            for _, _, resources in assignment.segments:
                for r in resources:
                    type_id = self.unit_to_type.get(r)
                    if type_id in self.fixed_types:
                        fixed_resources.add(r)
                    elif type_id in self.migration_types:
                        migration_resources.add(r)
            
            # Fixed resources must be the same in all segments
            for i, (start, end, resources) in enumerate(assignment.segments):
                segment_fixed = {r for r in resources if self.unit_to_type.get(r) in self.fixed_types}
                if i == 0:
                    expected_fixed = segment_fixed
                elif segment_fixed != expected_fixed:
                    errors.append(
                        f"Task {task_id}: Fixed-type resources changed from "
                        f"{expected_fixed} to {segment_fixed}"
                    )
            
            # Check fixed resources are available throughout continuous execution
            if fixed_resources and assignment.segments:
                start = assignment.start
                end = assignment.end
                for r in fixed_resources:
                    for t in range(start, end):
                        if not self.get_availability(r, t):
                            errors.append(
                                f"Task {task_id}: Fixed resource {r} unavailable at "
                                f"time {t} during execution"
                            )
                            break
        
        # Check aggregate capacity for migration types
        errors.extend(self._check_aggregate_capacity_for_types(solution, self.migration_types))
        
        return errors
    
    def _check_aggregate_capacity_for_types(self, solution: Solution, type_ids: Set[int]) -> List[str]:
        """Check aggregate capacity for specific types only."""
        errors = []
        
        time_points = set([0])
        for assignment in solution.assignments.values():
            for start, end, _ in assignment.segments:
                time_points.update([start, end])
        
        for calendar in self.unit_calendar.values():
            for t, _ in calendar:
                time_points.add(t)
        
        time_points = sorted(time_points)
        
        for type_id in type_ids:
            if type_id not in self.type_map:
                continue
            units = self.type_map[type_id]
            
            for i in range(len(time_points) - 1):
                t = time_points[i]
                capacity = sum(1 for u in units if self.get_availability(u, t))
                
                demand = 0
                for task_id, (duration, reqs) in self.tasks.items():
                    if task_id not in solution.assignments:
                        continue
                    
                    for start, end, resources in solution.assignments[task_id].segments:
                        if start <= t < end:
                            for req_type, qty in reqs:
                                if req_type == type_id:
                                    demand += qty
                                    break
                
                if demand > capacity:
                    errors.append(
                        f"Type {type_id} (migration) over capacity at time {t}: "
                        f"demand={demand}, capacity={capacity}"
                    )
        
        return errors


def validate_solution_dict(
    solution_dict: Dict[int, List[Tuple[int, int, Tuple[int, ...]]]],
    tasks: List[Tuple[int, int, List[Tuple[int, int]]]],
    types: List[Tuple[int, List[int]]],
    units: List[Tuple[int, List[Tuple[int, int]]]],
    precedences: List[Tuple[int, int]],
    variant: ProblemVariant,
    fixed_types: Optional[Set[int]] = None,
    migration_types: Optional[Set[int]] = None
) -> ValidationResult:
    """
    Convenience function to validate a solution dictionary.
    
    Args:
        solution_dict: {task_id: [(start, end, (resources...)), ...]}
        tasks, types, units, precedences: Instance data
        variant: Which problem variant to validate against
        fixed_types, migration_types: For HETEROGENEOUS variant
    
    Returns:
        ValidationResult
    """
    solution = Solution.from_dict(solution_dict)
    validator = SolutionValidator(tasks, types, units, precedences, fixed_types, migration_types)
    return validator.validate(solution, variant)


# ============================================
# Integration with CP Optimizer solutions
# ============================================

def validate_extracted_solution(
    assignments: Dict[int, List[Tuple[int, int, Tuple[int, ...]]]],
    N: int, K: int, R: int,
    TASKS: List[Tuple[int, int, List[Tuple[int, int]]]],
    TYPES: List[Tuple[int, List[int]]],
    UNITS: List[Tuple[int, List[Tuple[int, int]]]],
    PRECEDENCES: List[Tuple[int, int]],
    variant: int,  # 1-6
    fixed_types: Optional[Set[int]] = None,
    migration_types: Optional[Set[int]] = None
) -> ValidationResult:
    """
    Validate solution extracted from CP Optimizer using the helper functions
    from the provided code.
    
    Args:
        assignments: Output from extract_modes, greedy_assign, extract_segments, etc.
        N, K, R, TASKS, TYPES, UNITS, PRECEDENCES: Instance data from load_instance
        variant: Problem variant number (1-6)
        fixed_types, migration_types: For variant 5 (HETEROGENEOUS)
    
    Returns:
        ValidationResult
    """
    variant_map = {
        1: ProblemVariant.NO_MIG_NO_DELAY,
        2: ProblemVariant.MIG_NO_DELAY,
        3: ProblemVariant.NO_MIG_DELAY_BLOCKED,
        4: ProblemVariant.MIG_DELAY,
        5: ProblemVariant.HETEROGENEOUS,
        6: ProblemVariant.NO_MIG_DELAY_RELEASED
    }
    
    return validate_solution_dict(
        assignments, TASKS, TYPES, UNITS, PRECEDENCES,
        variant_map[variant], fixed_types, migration_types
    )


# ============================================
# Example usage and self-test
# ============================================

def _self_test():
    """Run self-test with a small example."""
    # Example from 00.data
    tasks = [
        (0, 0, [(0, 0)]),  # Dummy start
        (1, 4, [(0, 1)]),  # Work A
        (2, 2, [(0, 2)]),  # Work B
        (3, 0, [(0, 0)]),  # Dummy end
    ]
    
    types = [(0, [0, 1])]
    
    units = [
        (0, [(0, 100), (2, 0), (3, 100), (5, 0), (6, 100), (12, 0)]),
        (1, [(0, 0), (2, 100), (3, 0), (6, 100), (7, 0), (8, 100), (12, 0)]),
    ]
    
    precedences = [(0, 1), (0, 2), (1, 3), (2, 3)]
    
    # Example valid solution for variant 1 (No Migration | No Delays)
    solution_v1 = {
        0: [],
        1: [(3, 5, (0,)), (6, 8, (0,))],  # Task 1 on unit 0, but with gap - INVALID
        2: [(6, 8, (0, 1))],              # Task 2 needs 2 units
        3: [],
    }
    
    print("Testing invalid solution (has gap):")
    result = validate_solution_dict(solution_v1, tasks, types, units, precedences, 
                                    ProblemVariant.NO_MIG_NO_DELAY)
    print(result)
    print()
    
    # Valid solution
    solution_v1_valid = {
        0: [],
        1: [(6, 10, (0,))],   # Task 1 duration 4, on unit 0 starting at 6
        2: [(6, 8, (0, 1))],  # Overlaps with task 1 on unit 0! INVALID
        3: [],
    }
    
    print("Testing solution with resource conflict:")
    result = validate_solution_dict(solution_v1_valid, tasks, types, units, precedences,
                                    ProblemVariant.NO_MIG_NO_DELAY)
    print(result)


if __name__ == "__main__":
    _self_test()
