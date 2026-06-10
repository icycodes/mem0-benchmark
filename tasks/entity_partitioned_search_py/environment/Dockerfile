FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep && \
    pip3 install --break-system-packages pytest-json-ctrf mem0ai && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/mem0-task && chmod 0755 /home/user/mem0-task

LABEL Author="generate-harbor-tasks"
LABEL Description="Mem0 Platform Python SDK task environment for entity-partitioned ingestion and v2 filtered search."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - mem0ai Python SDK for Mem0 Platform (MemoryClient) used by both the task and verifier
#   - /home/user/mem0-task: empty project directory where the executor will create the script and artifacts
