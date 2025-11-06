# Constrained Programming Cookbook

This repository contains Jupyter notebooks for defining, learning and experimenting with scheduling problems using Constraint Programming with IBM’s CP Optimizer via the [`docplex.cp`](https://ibmdecisionoptimization.github.io/docplex-doc/cp/refman.html) Python API. 


---

## 📒 Notebooks

| Topic | Default objective | Notebook | Colab |
|---|---|---|---|
| **Job Shop Scheduling** | Minimize project makespan | [Job Shop Scheduling](notebooks/jobshop.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/jobshop.ipynb) |
| **Resource-Constrained Project Scheduling** | Minimize project makespan | [RCPSP](notebooks/rcpsp.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp.ipynb) |
| **Multi-Mode Resource-Constrained Project Scheduling** | Minimize project makespan with mode selection | [Multi-Mode RCPSP](notebooks/multimode_rcpsp.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/multimode_rcpsp.ipynb) |
| **Resource-Constrained Project Scheduling with Blocking Time** | Minimize makespan under blocking/preemption | [RCPSP with Blocking/Preemption](notebooks/rcpsp_blocking_preemption.ipynb) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/radovluk/CP_Cookbook/blob/main/notebooks/rcpsp_blocking_preemption.ipynb) |



---

## 📂 Data

All input files for the notebooks are in the [`data/`](data/) folder.

---

## 📚 Additional Resources

- [PSPLIB datasets](https://www.om-db.wi.tum.de/psplib/data.html) - Standard benchmark library for project scheduling problems (JSSP, RCPSP, MRCPSP).

- [Fifty years of research on resource-constrained project scheduling explored from different perspectives](https://www.sciencedirect.com/science/article/pii/S0377221725002218)  
  *Christian Artigues, Sönke Hartmann, Mario Vanhoucke,*  
  *European Journal of Operational Research*, Volume 328, Issue 2, 2026, pp. 367–389.

- [IBM Decision Optimization DOcplex Examples Repository](https://github.com/IBMDecisionOptimization/docplex-examples) - contains sample models demonstrating how to use the **DOcplex** library for both:  
  - `docplex.mp` — mathematical programming (linear/integer models)  
  - `docplex.cp` — constraint programming (CP Optimizer models)

- [Industrial project & machine scheduling with Constraint Programming](https://wimap.feld.cvut.cz/horde4/imp/attachment.php?id=6853ad12-efb4-475e-a898-60c19320d2a8&u=heinzvil) - *Philippe Laborie, IBM, 2021*.

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