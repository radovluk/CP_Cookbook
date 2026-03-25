#!/usr/bin/env python3
"""
OptalCP Python Demo - Simple Scheduling Problem

This demo shows a basic job-shop scheduling problem using the OptalCP Python API.
Configured to run on the Kubernetes cluster.
"""

import optalcp as cp
import os
from pathlib import Path

# Configure solver to use Kubernetes cluster
# The optalcp-k8s script connects to the remote K8s cluster
SCRIPT_DIR = Path(__file__).parent
os.environ["OPTALCP_SOLVER"] = str(SCRIPT_DIR / "optalcp-k8s")

print(f"OPTALCP_SOLVER set to: {os.environ['OPTALCP_SOLVER']}")


def simple_scheduling_problem():
    """
    Simple Job-Shop Scheduling Problem:

    - 3 jobs, each with 2 tasks
    - 2 machines
    - Each task must run on a specific machine
    - Tasks within a job must be sequential
    - Tasks on the same machine cannot overlap
    - Goal: Minimize the makespan (total completion time)
    """
    model = cp.Model()

    # Job data: (machine, duration) for each task
    # Job 0: Task on machine 0 (duration 3), then task on machine 1 (duration 2)
    # Job 1: Task on machine 1 (duration 2), then task on machine 0 (duration 4)
    # Job 2: Task on machine 0 (duration 2), then task on machine 1 (duration 3)
    jobs = [
        [(0, 3), (1, 2)],  # Job 0
        [(1, 2), (0, 4)],  # Job 1
        [(0, 2), (1, 3)],  # Job 2
    ]

    num_machines = 2

    # Create interval variables for each task
    tasks = {}
    for job_id, job in enumerate(jobs):
        for task_id, (machine, duration) in enumerate(job):
            task_name = f"job{job_id}_task{task_id}"
            tasks[(job_id, task_id)] = model.interval_var(
                length=duration,
                name=task_name
            )

    # Constraint 1: Tasks within a job must be sequential
    for job_id, job in enumerate(jobs):
        for task_id in range(len(job) - 1):
            current_task = tasks[(job_id, task_id)]
            next_task = tasks[(job_id, task_id + 1)]
            # Current task must end before next task starts
            current_task.end_before_start(next_task)

    # Constraint 2: Tasks on the same machine cannot overlap
    for machine in range(num_machines):
        machine_tasks = []
        for job_id, job in enumerate(jobs):
            for task_id, (task_machine, _) in enumerate(job):
                if task_machine == machine:
                    machine_tasks.append(tasks[(job_id, task_id)])

        if machine_tasks:
            model.no_overlap(machine_tasks)

    # Objective: Minimize makespan (completion time of all jobs)
    # Get the last task of each job
    last_tasks = [tasks[(job_id, len(job) - 1)] for job_id, job in enumerate(jobs)]
    makespan = model.max([task.end() for task in last_tasks])
    model.minimize(makespan)

    # Solve the problem
    print("\n" + "=" * 60)
    print("Solving Simple Job-Shop Scheduling Problem")
    print("=" * 60)
    print(f"Jobs: {len(jobs)}")
    print(f"Machines: {num_machines}")
    print(f"Total tasks: {sum(len(job) for job in jobs)}")
    print("=" * 60 + "\n")

    result = model.solve()

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    if result.solution:
        print(f"Optimal makespan: {result}")
        print("\nSchedule:")
        print("-" * 40)

        for job_id, job in enumerate(jobs):
            print(f"\nJob {job_id}:")
            for task_id, (machine, duration) in enumerate(job):
                task = tasks[(job_id, task_id)]
                start = result.solution.get_start(task)
                end = result.solution.get_end(task)
                print(f"  Task {task_id}: Machine {machine}, "
                      f"Start: {start}, End: {end}, Duration: {duration}")
    else:
        print("No solution found!")
        print(f"Status: {result.solve_status}")

    return result


if __name__ == "__main__":
    simple_scheduling_problem()
