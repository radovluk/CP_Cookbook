"""
Solver Module for RCPSP-AS CP-SAT Solver.

This module provides the Solver class, which wraps OR-Tools' CpSolver to solve
RCPSP-AS constraint models. It also defines data classes for representing
solutions and tracking solution progress during optimization.

Key components:
- SolvedActivity: Final scheduled state of a single activity
- Solution: Complete schedule with objective value and all activities
- Solver: Wrapper around CpSolver with solution tracking callback
- SolvedSolver: Solver after completion, holding the solution and timing info
"""

from dataclasses import dataclass
import sys
from typing import Callable, Self
from ortools.sat.python.cp_model import CpSolver, CpSolverSolutionCallback
from ortools.sat.sat_parameters_pb2 import SatParameters

from . import instance, model


@dataclass(frozen=True)
class SolvedActivity:
    """
    Represents the solved state of a single activity.
    
    After solving, each activity is either:
    - Not scheduled (is_scheduled=False): excluded from the final schedule
    - Scheduled (is_scheduled=True): has specific start_time and end_time
    
    Attributes:
        id: Activity ID (0-indexed internally)
        is_scheduled: Whether this activity was selected for scheduling
        resource_requirements: Demand for each resource type (from instance)
        start_time: When the activity starts (None if not scheduled)
        end_time: When the activity ends (None if not scheduled)
    """
    id: int
    is_scheduled: bool
    resource_requirements: list[int]
    start_time: int | None = None
    end_time: int | None = None

    @property
    def original_id(self) -> str:
        """Get the 1-indexed ID as used in benchmark files."""
        return str(self.id + 1)

    @classmethod
    def from_activity(cls, activity: model.Activity, solver: "Solver"):
        """Extract solved activity state from the solver's current solution."""
        start_time = solver.cp_solver.value(activity.start)
        end_time = start_time + activity.activity.duration

        return cls(
            id=activity.activity.id,
            is_scheduled=solver.cp_solver.value(activity.is_scheduled) != 0,
            start_time=start_time,
            end_time=end_time,
            resource_requirements=activity.activity.requirements,
        )

    def dump(self) -> str:
        """Serialize to string format for saving solutions."""
        match self.is_scheduled:
            case False: return "0"
            case True: return f"1 {self.start_time} {self.end_time}"

    @classmethod
    def from_dump(cls, id: int, activity: instance.Activity, line: str):
        """Deserialize from saved solution format."""
        make = lambda scheduled, start = None, end = None: cls(
            id=id,
            is_scheduled=scheduled,
            start_time=start,
            end_time=end,
            resource_requirements=activity.requirements,
        )

        nums = list(map(int, line.split()))
        match nums:
            case [0]: return make(False)
            case [1, start_time, end_time]: return make(True, start_time, end_time)
            case _: raise ValueError(f"Invalid SolvedActivity dump line: {line}")


@dataclass(frozen=True)
class Solution:
    """
    A complete solution to an RCPSP-AS instance.
    
    Contains the objective value and the scheduled state of all activities.
    For activities not scheduled (is_scheduled=False), start_time/end_time
    are available but meaningless.
    
    Attributes:
        objective: The objective function value (Cmax or wT)
        activities: List of solved activities in order
    """
    objective: int
    activities: list[SolvedActivity]

    def __getitem__(self, activity: instance.Activity | model.Activity):
        """Get the solved state for a specific activity."""
        if isinstance(activity, model.Activity):
            activity = activity.activity

        return self.activities[activity.id]

    def dump(self) -> str:
        """Serialize the entire solution to string format."""
        return '\n'.join([str(self.objective)] + [a.dump() for a in self.activities])

    @classmethod
    def from_solver(cls, solver: "Solver", model: model.Model) -> Self:
        """Extract the solution from a completed solver."""
        return cls(
            objective=int(solver.cp_solver.objective_value),
            activities=[
                SolvedActivity.from_activity(activity, solver)
                for activity in model.activities
            ],
        )

    @classmethod
    def from_dump(cls, dump: str, ins: instance.Instance) -> Self:
        """Deserialize a solution from saved format."""
        def parse_activities(objective: str, activity_lines: list[str]):
            err_message = lambda: f"expected {len(ins.activities)} lines, got {len(activity_lines)}"
            assert len(activity_lines) == len(ins.activities), err_message()

            return cls(
                objective=int(objective),
                activities=[
                    SolvedActivity.from_dump(id, activity, line)
                    for id, (activity, line) in enumerate(zip(ins.activities, activity_lines))
                ],
            )

        match dump.splitlines():
            case [objective, *activity_lines]: return parse_activities(objective, activity_lines)
            case _: raise ValueError("Invalid dump format")


class Solver:
    """
    Wrapper around OR-Tools' CpSolver for solving RCPSP-AS models.
    
    Provides default solver settings (logging, timeout) and tracks solution
    progress via a callback that records when each improving solution is found.
    
    Default settings:
    - log_search_progress=True: Print solver progress to stdout
    - max_time_in_seconds=60: 1-minute timeout
    """
    
    class __SolutionCallback(CpSolverSolutionCallback):
        """Internal callback to track solution improvements during solving."""
        def __init__(self, cb: Callable[[CpSolverSolutionCallback], None]):
            CpSolverSolutionCallback.__init__(self)
            self.__cb = cb

        def on_solution_callback(self):
            """Called by OR-Tools whenever a new solution is found."""
            self.__cb(self)

    @dataclass(frozen=True)
    class SolutionSnapshot:
        """
        Record of a solution found during optimization.
        
        Attributes:
            objective: The objective value at this point
            deterministic_time: Solver's internal deterministic time
            user_time: CPU user time when solution was found
            wall_time: Wall clock time when solution was found
        """
        objective: int
        deterministic_time: float
        user_time: float
        wall_time: float

    def __init__(self, solver: CpSolver | None = None):
        """
        Create a Solver with the given or default CpSolver.
        
        Args:
            solver: Optional CpSolver to use. If None, creates a new solver
                    with default settings (logging, 60s timeout).
        """
        self.cp_solver = solver or Solver.__new_solver()

    @staticmethod
    def __new_solver() -> CpSolver:
        """Create a new CpSolver with default settings."""
        solver = CpSolver()
        solver.parameters = SatParameters(log_search_progress=True, max_time_in_seconds=60)
        return solver

    @property
    def params(self) -> SatParameters:
        """Get the solver's parameter settings for modification."""
        return self.cp_solver.parameters

    def solve(self, model: model.Model) -> "SolvedSolver":
        """
        Solve the given RCPSP-AS model.
        
        Runs the CP-SAT solver on the model, tracking all improving solutions
        found during the search. Returns a SolvedSolver containing the final
        solution and timing information.
        
        Args:
            model: The RCPSP-AS model to solve
            
        Returns:
            SolvedSolver with the solution and solution history
        """
        # Track when each improving solution is found
        solution_times: list[Solver.SolutionSnapshot] = []
        def on_solution(cb: CpSolverSolutionCallback):
            objective = cb.value(model.objective)
            # Only record if objective improved (avoid duplicates)
            if not solution_times or solution_times[-1].objective != objective:
                solution_times.append(Solver.SolutionSnapshot(
                    objective=cb.value(model.objective),
                    deterministic_time=cb.deterministic_time,
                    user_time=cb.user_time,
                    wall_time=cb.wall_time,
                ))

        # Flush stdout before/after solving for clean log output
        sys.stdout.flush()
        self.cp_solver.solve(model.cp_model, Solver.__SolutionCallback(on_solution))
        sys.stdout.flush()
        
        # Extract the final solution
        solution = Solution.from_solver(self, model)
        return SolvedSolver(self.cp_solver, solution, model, solution_times)


class SolvedSolver(Solver):
    """
    A Solver after completing the solve process.
    
    Extends Solver to hold the final solution and timing information.
    This separation allows inspecting results while keeping the Solver
    interface clean.
    
    Attributes:
        solution: The final Solution object
        model: The Model that was solved
        solution_times: List of SolutionSnapshots tracking solution progress
    """
    
    def __init__(self,
        solver: CpSolver,
        solution: Solution,
        model: model.Model,
        solution_times: list[Solver.SolutionSnapshot],
    ):
        super().__init__(solver)
        self.solution = solution
        self.model = model
        self.solution_times = solution_times


    @property
    def status_str(self):
        """Get a human-readable summary of the solve result."""
        def solution_time():
            if not self.solution_times: return None
            return f"solution time: {self.solution_times[-1].wall_time:.2f} seconds"

        return '\n'.join(x for x in [
            f"solver status: {self.cp_solver.status_name()}",
            f"objective value: {self.cp_solver.objective_value}",
            solution_time(),
        ] if x)

