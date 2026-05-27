FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep jq && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        mem0ai && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/bulk-import && chmod 0755 /home/user/bulk-import

LABEL Author="generate-harbor-tasks"
LABEL Description="Mem0 Platform CLI task environment: Ubuntu 24.04 with Node.js v24, Python 3, jq, and the mem0ai Python SDK pre-installed for the verifier. The executor installs the mem0 CLI (mem0-cli or @mem0/cli) during the task."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: jq (for parsing mem0 CLI JSON output during task execution)
#   - Node.js v24 (provides `npm` so the executor can `npm install -g @mem0/cli`)
#   - always required pip3 packages: pytest-json-ctrf
#   - mem0ai Python SDK pre-installed so the verifier can talk to the Mem0 Platform
#   - /home/user/bulk-import: empty project directory; the executor must create the log file
