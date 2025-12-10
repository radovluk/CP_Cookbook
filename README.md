# Constrained Programming Cookbook

This repository contains Jupyter notebooks for defining, learning and experimenting with scheduling problems using Constraint Programming with IBM’s CP Optimizer via the [docplex.cp](https://ibmdecisionoptimization.github.io/docplex-doc/cp/refman.html) Python API, and subsequently solving the problems in [OptalCP](https://optalcp.com/) via the OptalCP [Python API](https://github.com/ScheduleOpt/optalcp-py).


---

## 📒 Notebooks

| Topic | Default objective | Notebook | Colab | Status |
|---|---|---|---|---|
| Job Shop Scheduling | Minimize project makespan | [Job Shop Scheduling](notebooks/jobshop.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/jobshop.ipynb) | ✅ Done |
| Resource-Constrained Project Scheduling | Minimize project makespan | [RCPSP](notebooks/rcpsp.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp.ipynb) | ✅ Done |
| Multi-Mode RCPSP | Minimize project makespan | [Multi-Mode RCPSP](notebooks/multimode_rcpsp.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/multimode_rcpsp.ipynb) | ✅ Done |
| RCPSP with Timeoffs | Minimize project makespan | [RCPSP with Timeoffs](notebooks/rcpsp_timeoffs.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp_timeoffs.ipynb) | ✅ Done |
| RCPSP with Sequence-Dependent Setup Times (Unary Resources) | Minimize project makespan | [RCPSP with Sequence-Dependent Setup Times (Unary Resources)](notebooks/rcpsp_setup.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp_setup.ipynb) | ✅ Done |
| RCPSP with Transfer Times | Minimize project makespan | [RCPSP with Transfer Times](notebooks/rcpsptt.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsptt.ipynb) | ✅ Done |
| RCPSP with Alternative Process Plans | Minimize project makespan | [ RCPSP with Alternative Process Plans](notebooks/RCPSPAS/rcpspas.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/RCPSPAS/rcpspas.ipynb) | ✅ Done |



---

## 📂 Data

All input files for the notebooks are in the [`data/`](data/) folder.


[`benchmarks/`](benchmarks/) - Runner, generator, and validator for comparing OptalCP vs CP Optimizer across RCPSP variants. Run with `python run.py <problem> --compare` inside the benchmarks folder.

---

## 📚 Additional Resources

### IBM CP Optimizer

- [IBM Tutorial: Getting started with Scheduling in CPLEX for Python](https://ibmdecisionoptimization.github.io/tutorials/html/Scheduling_Tutorial.html#:~:text=In%20the%20model%2C%20each%20task,the%20solution%20to%20the%20problem.)

- [Examples and guidelines for modeling and solving combinatorial optimization problems with IBM ILOG CP Optimizer](https://github.com/plaborie/cpoptimizer-examples/tree/main) - Github repo of Philippe Laborie with resources 

- [ICAPS 2017: Video Tutorial – Philippe Laborie: Introduction to CP Optimizer for Scheduling](https://www.youtube.com/watch?v=-VY7QTnSAio), [Slides from the video](https://icaps17.icaps-conference.org/tutorials/T3-Introduction-to-CP-Optimizer-for-Scheduling.pdf)

- [IBM: CPLEX for scheduling](https://www.ibm.com/docs/en/icos/22.1.2?topic=scheduling-introduction)

- [IBM Decision Optimization DOcplex Examples Repository](https://github.com/IBMDecisionOptimization/docplex-examples) - contains sample models demonstrating how to use the DOcplex.
  
- [Designing Scheduling Models – IBM CP Documentation](https://www.ibm.com/docs/en/icos/22.1.1?topic=manual-designing-scheduling-models)  

- [Industrial project & machine scheduling with Constraint Programming](https://wimap.feld.cvut.cz/horde4/imp/attachment.php?id=6853ad12-efb4-475e-a898-60c19320d2a8&u=heinzvil) - *Philippe Laborie, IBM, 2021*.

- [Modeling and Solving Scheduling Problems with CP Optimizer](https://www.researchgate.net/publication/275634767_Modeling_and_Solving_Scheduling_Problems_with_CP_Optimizer)  

- [Fifty years of research on resource-constrained project scheduling explored from different perspectives](https://www.sciencedirect.com/science/article/pii/S0377221725002218)  
  *Christian Artigues, Sönke Hartmann, Mario Vanhoucke,*  
  *European Journal of Operational Research*, Volume 328, Issue 2, 2026, pp. 367–389.

### Optal CP

- [Getting started with OptalCP Python API](notebooks/optalcp_python.ipynb) - Jupyter notebook with basic overview

- [OptalCP docs](https://optalcp.com/docs/api/)

- [OptalCP Benchmarks](https://github.com/ScheduleOpt/optalcp-benchmarks/tree/main), 
  
- [Benchmarks against IBM ILOG CP Optimizer](https://optalcp.com/docs/benchmarks/)

### Datasets

- [PSPLIB datasets](https://www.om-db.wi.tum.de/psplib/data.html) - Standard benchmark library for project scheduling problems (JSSP, RCPSP, MRCPSP).

- [OR&S project database datasets (ASLIB)](https://www.projectmanagement.ugent.be/research/data) 
---

> **Note:** These notebooks use two constraint programming solvers. You need to install both solver binaries and both Python libraries to run the notebooks.
>
> **IBM CP Optimizer** (part of CPLEX Optimization Studio)  
> - Download: https://www.ibm.com/products/ilog-cplex-optimization-studio/cplex-cp-optimizer  
> - Students/academics: Install the [full version](https://community.ibm.com/community/user/blogs/xavier-nodet1/2020/07/09/cplex-free-for-students?CommunityKey=ab7de0fd-6f43-47a9-8261-33578a231bb7&tab=) (the non-academic version has model size limits). First go to https://academic.ibm.com/ and sign in using your academic credentials, then head to [Software Download](https://www-50.ibm.com/isc/esd/dswdown/home?ticket=Xa.2%2FXb.Z7LJBh8BR1y_8GJfWb7o2cPx%2FXc.%2FXd.%2FXf.%2FXg.13644878%2FXi.%2FXY.scholars%2FXZ.-kBhtbT2hb6gvZkPbx3wu8EkYQLEXkiw&partNumber=G0798ML) page, pick download method HTTP and select binary for your OS. The website is absolutely terrible so be prepared. 
> - Python API: `pip install docplex` ([PyPI](https://pypi.org/project/docplex/))
>
> **OptalCP**  
> - Website: https://optalcp.com/  
> - Students/academics: Install the [academic version](https://github.com/ScheduleOpt/optalcp-py-bin-academic) (the standard version doesn't show concrete variable assignments)  
> - Python API: ([GitHub](https://github.com/ScheduleOpt/optalcp-py))