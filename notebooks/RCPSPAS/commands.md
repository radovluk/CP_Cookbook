# Copy image to cluster (159MB)
rsync -avP -e 'ssh -p 2229' \
  ~/Desktop/CIIRC/CP_Cookbook/docker/optalcp-solver.tar.gz \
  radovluk@rtime.ciirc.cvut.cz:~/

# On the cluster, load the image
docker load < ~/optalcp-solver.tar.gz

# Log into the cluster
ssh -p 2228 radovluk@rtime.ciirc.cvut.cz krocan
ssh -p 2229 radovluk@rtime.ciirc.cvut.cz kruta

# Run the docker
docker run --rm -it -v ~/rcpspas:/workspace optalcp-solver:latest bash

# Run the solver
python solve_rcpspas.py -d ASLIB/ASLIB0/ -t 5 --start 0 --end 1000 --solver optalcp -f original -w 32 -q -o optalcp_original.csv

# Tmux
tmux new -s rcpspas

Detach from tmux: Ctrl+B, then D

Reconnect later:
tmux attach -t rcpspas

# Push python skript to Krocan
rsync -avP -e 'ssh -p 2228' \
  ~/Desktop/CIIRC/CP_Cookbook/notebooks/RCPSPAS/solve_rcpspas.py \
  radovluk@rtime.ciirc.cvut.cz:~/rcpspas/

# Retrieve results from krocan:
rsync -avP -e 'ssh -p 2228' \
  radovluk@rtime.ciirc.cvut.cz:~/rcpspas/results.csv \
  ~/Desktop/CIIRC/RCPSPAS/

# Push the scripts
rsync -avP -e 'ssh -p 2228' \
  ~/Desktop/CIIRC/CP_Cookbook/notebooks/RCPSPAS/solve_rcpspas.py \
  ~/Desktop/CIIRC/CP_Cookbook/notebooks/RCPSPAS/run_all.sh \
  radovluk@rtime.ciirc.cvut.cz:~/rcpspas/

bash run_all.sh

# Count occurences:

grep -c "Optimal" optalcp_original_ASLIB0.csv
