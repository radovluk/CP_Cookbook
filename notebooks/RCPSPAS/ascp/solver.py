from dataclasses import dataclass
import sys
from typing import Callable, Self
from ortools.sat.python.cp_model import CpSolver, CpSolverSolutionCallback
from ortools.sat.sat_parameters_pb2 import SatParameters

from . import instance, model


@dataclass(frozen=True)
class SolvedActivity:
    id: int
    is_scheduled: bool
    resource_requirements: list[int]
    start_time: int | None = None
    end_time: int | None = None

    @property
    def original_id(self) -> str:
        return str(self.id + 1)

    @classmethod
    def from_activity(cls, activity: model.Activity, solver: "Solver"):
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
        match self.is_scheduled:
            case False: return "0"
            case True: return f"1 {self.start_time} {self.end_time}"

    @classmethod
    def from_dump(cls, id: int, activity: instance.Activity, line: str):
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
    objective: int
    activities: list[SolvedActivity]

    def __getitem__(self, activity: instance.Activity | model.Activity):
        if isinstance(activity, model.Activity):
            activity = activity.activity

        return self.activities[activity.id]

    def dump(self) -> str:
        return '\n'.join([str(self.objective)] + [a.dump() for a in self.activities])

    @classmethod
    def from_solver(cls, solver: "Solver", model: model.Model) -> Self:
        return cls(
            objective=int(solver.cp_solver.objective_value),
            activities=[
                SolvedActivity.from_activity(activity, solver)
                for activity in model.activities
            ],
        )

    @classmethod
    def from_dump(cls, dump: str, ins: instance.Instance) -> Self:
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
    class __SolutionCallback(CpSolverSolutionCallback):
        def __init__(self, cb: Callable[[CpSolverSolutionCallback], None]):
            CpSolverSolutionCallback.__init__(self)
            self.__cb = cb

        def on_solution_callback(self):
            self.__cb(self)

    @dataclass(frozen=True)
    class SolutionSnapshot:
        objective: int
        deterministic_time: float
        user_time: float
        wall_time: float

    def __init__(self, solver: CpSolver | None = None):
        self.cp_solver = solver or Solver.__new_solver()

    @staticmethod
    def __new_solver() -> CpSolver:
        solver = CpSolver()
        solver.parameters = SatParameters(log_search_progress=True, max_time_in_seconds=60)
        return solver

    @property
    def params(self) -> SatParameters:
        return self.cp_solver.parameters

    def solve(self, model: model.Model) -> "SolvedSolver":
        solution_times: list[Solver.SolutionSnapshot] = []
        def on_solution(cb: CpSolverSolutionCallback):
            objective = cb.value(model.objective)
            if not solution_times or solution_times[-1].objective != objective:
                solution_times.append(Solver.SolutionSnapshot(
                    objective=cb.value(model.objective),
                    deterministic_time=cb.deterministic_time,
                    user_time=cb.user_time,
                    wall_time=cb.wall_time,
                ))

        sys.stdout.flush()
        self.cp_solver.solve(model.cp_model, Solver.__SolutionCallback(on_solution))
        sys.stdout.flush()
        solution = Solution.from_solver(self, model)
        return SolvedSolver(self.cp_solver, solution, model, solution_times)


class SolvedSolver(Solver):
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
        def solution_time():
            if not self.solution_times: return None
            return f"solution time: {self.solution_times[-1].wall_time:.2f} seconds"

        return '\n'.join(x for x in [
            f"solver status: {self.cp_solver.status_name()}",
            f"objective value: {self.cp_solver.objective_value}",
            solution_time(),
        ] if x)
