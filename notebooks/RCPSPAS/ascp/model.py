"""
Model Module for RCPSP-AS CP-SAT Solver.

This module provides the Model class which wraps OR-Tools' CpModel to create
a Constraint Programming model for RCPSP-AS (Resource-Constrained Project
Scheduling Problem with Alternative Subgraphs).

The CP model uses:
- Boolean variables (x_i) for activity selection
- Integer variables (s_i) for start times
- Interval variables (int_i) for scheduling
- Boolean variables for branch selection

Constraints implemented:
1. Activity Selection: x_i ⟺ ⋁ (branch variables)
2. Subgraph Branch Selection: exactly one branch per active subgraph
3. Precedence: if both activities scheduled, successor starts after predecessor
4. Resources: cumulative constraint for renewable resource capacities

Objective functions:
- Cmax: minimize makespan (completion time of last activity)
- wT: minimize weighted tardiness (sum of weighted delays past due dates)
"""

import typing as tp
from dataclasses import dataclass, field

from ortools.sat.python.cp_model import CpModel, IntervalVar, IntVar, LinearExprT

from . import instance


@dataclass
class ModelConfig:
    """
    Configuration for the ASCP model.

    Attributes:
        tmin (int): The minimum time value (usually 0).
        tmax (int | None): The maximum time value. If None, computed as
            sum of all activity durations (upper bound H on makespan).
    """
    tmin: int = 0
    tmax: int | None = None


@dataclass
class Activity:
    """
    Wrapper holding CP-SAT variables for a single activity.
    
    For each activity i, the following CP-SAT variables are created:
    - is_scheduled (x_i): Boolean, whether activity is selected
    - start (s_i): Integer in [0, H], activity start time
    - interval (int_i): Optional fixed-size interval for scheduling constraints
    
    The interval's presence is tied to is_scheduled, making it "optional".
    """
    activity: instance.Activity
    is_scheduled: IntVar
    start: IntVar
    interval: IntervalVar

    @property
    def end(self) -> LinearExprT:
        """Get the end time expression (start + duration) for this activity."""
        return self.interval.end_expr()


class Model:
    """
    A CP-SAT model for the RCPSP-AS problem.
    
    This class wraps OR-Tools' CpModel and creates all necessary variables
    and constraints for solving RCPSP-AS instances. It supports two objective
    functions: Cmax (makespan) and wT (weighted tardiness).
    
    The model construction follows these steps:
    1. Create activity variables (x_i, s_i, int_i for each activity)
    2. Create branch selection variables (one boolean per branch)
    3. Set up the objective function (Cmax or wT)
    4. Add activity selection constraints (link activities to branches)
    5. Add one-of-subgraph constraints (exactly one branch per subgraph)
    6. Add precedence constraints (conditional on both activities being scheduled)
    7. Add resource constraints (cumulative constraint for each resource type)
    """

    @dataclass
    class __ResolvedConfig:
        """Internal config with computed tmax."""
        tmin: int
        tmax: int

    def __init__(self,
        problem_instance: instance.Instance,
        objective: tp.Literal["cmax", "wt"] | None = None,
        config: ModelConfig = ModelConfig(),
    ):
        """
        Build a CP-SAT model for the given RCPSP-AS instance.
        
        Args:
            problem_instance: The RCPSP-AS instance to solve
            objective: "cmax" or "wt", auto-detected from instance type if None
            config: Model configuration (time bounds)
        """
        # Auto-detect objective from instance type
        if objective is None:
            objective = "wt" if isinstance(problem_instance, instance.WtInstance) else "cmax"

        self.__instance = problem_instance
        self.__objective = objective
        self.__model = CpModel()
        self.__model.name = "ASCP"

        # Compute upper bound H = Σ d_i if not specified
        self.__config = Model.__ResolvedConfig(
            tmin=config.tmin,
            tmax=config.tmax or sum(a.duration for a in problem_instance.activities)
        )

        # Build the model
        self.__create_activity_variables()
        self.__create_subgraph_variables()

        match objective:
            case "cmax": self.__make_cmax()
            case "wt": self.__make_wt()
            case _: raise ValueError(f"Invalid objective: {objective}")

        self.__create_activity_scheduled_constraints()
        self.__create_one_of_subgraph_constraints()
        self.__create_successor_constraints()
        self.__create_resource_constraints()

    @property
    def cp_model(self):
        """Get the underlying OR-Tools CpModel."""
        return self.__model

    @property
    def objective_type(self):
        """Get the objective type ('cmax' or 'wt')."""
        return self.__objective

    @property
    def instance(self) -> instance.Instance:
        """Get the problem instance this model was built for."""
        return self.__instance

    @property
    def objective(self) -> IntVar:
        """Get the objective variable (cmax or wt depending on objective type)."""
        match self.__objective:
            case "cmax": return self.__cmax
            case "wt": return self.__wt
            case _: raise ValueError(f"Invalid objective: {self.__objective}")

    def __new_int_var(self, name: str, *, lb: int | None = None, ub: int | None = None) -> IntVar:
        """Create an integer variable with default bounds [tmin, tmax]."""
        lb = lb or self.__config.tmin
        ub = ub or self.__config.tmax
        return self.__model.new_int_var(lb, ub, name)

    def __create_activity_variables(self):
        """
        Create CP-SAT variables for all activities (Algorithm 4.1).
        
        For each activity i:
        - x_i: Boolean variable for whether activity is scheduled
        - s_i: Integer variable for start time in [0, H]
        - int_i: Optional interval tied to x_i for scheduling constraints
        """
        def create_activity(activity: instance.Activity) -> Activity:
            # x_i: is the activity scheduled?
            is_scheduled = self.__model.new_bool_var(f"activity_{activity.id}_is_scheduled")
            # s_i: when does it start?
            start = self.__new_int_var(f"activity_{activity.id}_start")
            # int_i: optional interval (exists only if x_i is true)
            interval = self.__model.new_optional_fixed_size_interval_var(
                start,
                activity.duration,
                is_present=is_scheduled,
                name=f"activity_{activity.id}_interval"
            )

            return Activity(activity, is_scheduled, start, interval)

        self.activities = [create_activity(a) for a in self.__instance.activities]

    def __create_subgraph_variables(self):
        """
        Create CP-SAT variables for branch selection.
        
        Branch 0 (root) is always selected (constant True).
        Other branches are boolean decision variables.
        """
        # Root branch (branch 0) is always selected
        root_branch = self.__model.new_constant(True)
        # Other branches are decision variables
        other_branches = [
            self.__model.new_bool_var(f"subgraph_{subgraph.id}_branch_{branch}")
            for subgraph in self.__instance.subgraphs
            for branch in subgraph.branches
        ]

        self.branches = [root_branch, *other_branches]

    def __make_cmax(self):
        """
        Create Cmax (makespan) objective (Algorithm 4.6).
        
        min Z_Cmax = max(end_i for all scheduled activities)
        
        Implemented as: Cmax >= end_i for all scheduled i, minimize Cmax.
        """
        self.__cmax = self.__new_int_var("cmax")

        # Cmax must be >= end time of every scheduled activity
        for activity in self.activities: (
            self.__model
                .add(activity.end <= self.__cmax)
                .only_enforce_if(activity.is_scheduled)
        )

        self.__model.minimize(self.__cmax)

    def __make_wt(self):
        """
        Create weighted tardiness (wT) objective.
        
        min Z_wT = Σ w_i * max(0, C_i - d_i)
        
        For each monitored activity:
        - tardiness_i = max(0, end_i - due_date_i)
        - wT = Σ weight_i * tardiness_i
        """
        err_message = lambda: "wt objective can only be used with WtInstance instances"
        assert isinstance(self.__instance, instance.WtInstance), err_message()

        tardinesses = []
        for act_id, due_date in self.__instance.due_dates.items():
            tardiness_var = self.__new_int_var(f"tardiness_{act_id}")
            delay = self.activities[act_id].end - due_date.due_date
            # tardiness = max(delay, 0) - can't be negative
            self.__model.add_max_equality(tardiness_var, [delay, 0])
            tardinesses.append(tardiness_var * due_date.weight)

        # Upper bound on wT for domain
        wt_domain = sum(dd.weight * self.__config.tmax for dd in self.__instance.due_dates.values())
        self.__wt = self.__new_int_var("wt", ub=wt_domain)
        self.__model.add(self.__wt == sum(tardinesses))
        self.__model.minimize(self.__wt)

    def __create_activity_scheduled_constraints(self):
        """
        Create activity selection constraints (Algorithm 4.2, eq. 4.8-4.9).
        
        x_i ⟺ ⋁_{k ∈ B_i} x_{b_k}
        
        An activity is scheduled iff at least one of its branches is selected.
        Implemented using max_equality (OR in boolean context).
        """
        for activity in self.activities:
            self.__model.add_max_equality(
                activity.is_scheduled,
                [self.branches[branch] for branch in activity.activity.branches],
            )

    def __create_one_of_subgraph_constraints(self):
        """
        Create subgraph branch selection constraints (Algorithm 4.3, eq. 4.10).
        
        Σ_{k ∈ K_{p_l}} x_{b_k} = x_{p_l}
        
        Exactly one branch of a subgraph is selected iff the principal
        activity is scheduled. Since branches are boolean (0 or 1),
        sum == 1 means exactly one is selected.
        """
        for subgraph in self.__instance.subgraphs:
            self.__model.add(
                sum(self.branches[bi] for bi in subgraph.branches)
                == self.activities[subgraph.principal_activity].is_scheduled
            )

    def __create_successor_constraints(self):
        """
        Create precedence constraints (Algorithm 4.4, eq. 4.11).
        
        (x_i ∧ x_j) ⟹ (s_i + d_i ≤ s_j)
        
        If both activities are scheduled, the successor must start after
        the predecessor finishes. Uses only_enforce_if for conditional.
        """
        for activity in self.activities:
            for successor_idx in activity.activity.successors:
                successor = self.activities[successor_idx]
                (self.__model
                    .add(activity.interval.end_expr() <= successor.start)
                    .only_enforce_if(activity.is_scheduled, successor.is_scheduled)
                )

    def __create_resource_constraints(self):
        """
        Create resource capacity constraints (Algorithm 4.5, eq. 4.12).
        
        Σ_{i ∈ S_t} r_{i,v} ≤ a_v  for all t, v
        
        Uses OR-Tools' high-level add_cumulative constraint which internally
        ensures that at any time t, the sum of demands of activities
        running at time t doesn't exceed the resource capacity.
        """
        @dataclass
        class Resource:
            """Helper to collect intervals and demands per resource."""
            capacity: int
            intervals: tp.List[IntervalVar] = field(default_factory=list)
            demands: tp.List[int] = field(default_factory=list)

        resources = [Resource(cap) for cap in self.__instance.resources]

        # Collect interval variables and demands for each resource
        for activity in self.activities:
            for resource_idx, demand in enumerate(activity.activity.requirements):
                resources[resource_idx].intervals.append(activity.interval)
                resources[resource_idx].demands.append(demand)

        # Add cumulative constraint for each resource
        for resource in resources:
            self.__model.add_cumulative(
                intervals=resource.intervals,
                demands=resource.demands,
                capacity=resource.capacity
            )

