FROM python:3.12-slim

# --- IBM CP Optimizer binary (CPLEX Studio 22.11) ---
COPY cpoptimizer /opt/cpoptimizer/bin/cpoptimizer
RUN chmod +x /opt/cpoptimizer/bin/cpoptimizer
ENV PATH="/opt/cpoptimizer/bin:${PATH}"

# --- OptalCP Python API (from local source) ---
COPY optalcp-py /tmp/optalcp-py
RUN pip install --no-cache-dir /tmp/optalcp-py && rm -rf /tmp/optalcp-py

# --- OptalCP solver binary (academic edition, copied from local install) ---
COPY optalcp_bin_academic /tmp/optalcp_bin_academic
RUN pip install --no-cache-dir /tmp/optalcp_bin_academic && rm -rf /tmp/optalcp_bin_academic

# --- docplex + OR-Tools ---
RUN pip install --no-cache-dir docplex ortools

# Default working directory for mounting cluster data
WORKDIR /workspace
