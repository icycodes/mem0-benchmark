FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        mem0ai && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/mem0-async-task && chmod 0755 /home/user/mem0-async-task

LABEL Author="generate-harbor-tasks"
LABEL Description="Mem0 Platform AsyncMemoryClient Python task environment with mem0ai installed."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - mem0ai (Mem0 Platform / OSS Python SDK) installed via pip3
#   - /home/user/mem0-async-task: empty project directory created up-front
