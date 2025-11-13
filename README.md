# Constrained Programming Cookbook

This repository contains Jupyter notebooks for defining, learning and experimenting with scheduling problems using Constraint Programming with IBM’s CP Optimizer via the [`docplex.cp`](https://ibmdecisionoptimization.github.io/docplex-doc/cp/refman.html) Python API. 


---

## 📒 Notebooks

| Topic | Default objective | Notebook | Colab | Status |
|---|---|---|---|---|
| Job Shop Scheduling | Minimize project makespan | [Job Shop Scheduling](notebooks/jobshop.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/jobshop.ipynb) | ✅ Done |
| Resource-Constrained Project Scheduling | Minimize project makespan | [RCPSP](notebooks/rcpsp.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp.ipynb) | ✅ Done |
| Multi-Mode RCPSP | Minimize project makespan | [Multi-Mode RCPSP](notebooks/multimode_rcpsp.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/multimode_rcpsp.ipynb) | ✅ Done |
| RCPSP with Blocking Times | Minimize project makespan | [RCPSP with Blocking Times](notebooks/rcpsp_blocking.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp_blocking.ipynb) | ⚙️ Not implemented |
| Preemptive RCPSP | Minimize project makespan | [Preemptive RCPSP](notebooks/preemptive_rcpsp.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/preemptive_rcpsp.ipynb) | ⚙️ Not implemented |
| RCPSP with Sequence-Dependent Setup Times (Unary Resources) | Minimize project makespan | [RCPSP with Sequence-Dependent Setup Times (Unary Resources)](notebooks/rcpsp_setup.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp_setup.ipynb) | ✅ Done? |
| RCPSP with Transfer Times | Minimize project makespan | [RCPSP with Transfer Times](notebooks/rcpsptt.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsptt.ipynb) | ⏳ In progress |
| RCPSP with Alternative Process Plans | Minimize project makespan | [ RCPSP with Alternative Process Plans](notebooks/RCPSPAS/rcpspas.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/RCPSPAS/rcpspas.ipynb) | ✅ Done |





---

## 📂 Data

All input files for the notebooks are in the [`data/`](data/) folder.

---

## 📚 Additional Resources

- [IBM Tutorial: Getting started with Scheduling in CPLEX for Python](https://ibmdecisionoptimization.github.io/tutorials/html/Scheduling_Tutorial.html#:~:text=In%20the%20model%2C%20each%20task,the%20solution%20to%20the%20problem.)

- [ICAPS 2017: Video Tutorial – Philippe Laborie: Introduction to CP Optimizer for Scheduling](https://www.youtube.com/watch?v=-VY7QTnSAio), [Slides from the video](https://icaps17.icaps-conference.org/tutorials/T3-Introduction-to-CP-Optimizer-for-Scheduling.pdf)

- [IBM: CPLEX for scheduling](https://www.ibm.com/docs/en/icos/22.1.2?topic=scheduling-introduction)

- [IBM Decision Optimization DOcplex Examples Repository](https://github.com/IBMDecisionOptimization/docplex-examples) - contains sample models demonstrating how to use the DOcplex.
  
- [Designing Scheduling Models – IBM CP Documentation](https://www.ibm.com/docs/en/icos/22.1.1?topic=manual-designing-scheduling-models)  

- [Industrial project & machine scheduling with Constraint Programming](https://wimap.feld.cvut.cz/horde4/imp/attachment.php?id=6853ad12-efb4-475e-a898-60c19320d2a8&u=heinzvil) - *Philippe Laborie, IBM, 2021*.

- [Modeling and Solving Scheduling Problems with CP Optimizer](https://www.researchgate.net/publication/275634767_Modeling_and_Solving_Scheduling_Problems_with_CP_Optimizer)  

- [Fifty years of research on resource-constrained project scheduling explored from different perspectives](https://www.sciencedirect.com/science/article/pii/S0377221725002218)  
  *Christian Artigues, Sönke Hartmann, Mario Vanhoucke,*  
  *European Journal of Operational Research*, Volume 328, Issue 2, 2026, pp. 367–389.

- [PSPLIB datasets](https://www.om-db.wi.tum.de/psplib/data.html) - Standard benchmark library for project scheduling problems (JSSP, RCPSP, MRCPSP).

- [OR&S project database datasets](https://www.projectmanagement.ugent.be/research/data) 

---

## 🚀 How to run locally

Install dependencies via Conda:

```bash
conda env create -f environment.yml
conda activate scheduling
jupyter notebook
```
> **Note:** These notebooks use IBM **CP Optimizer** (part of CPLEX Optimization Studio).  
> Please make sure CP Optimizer is installed and available to `docplex.cp` before running:
> https://www.ibm.com/products/ilog-cplex-optimization-studio/cplex-cp-optimizer