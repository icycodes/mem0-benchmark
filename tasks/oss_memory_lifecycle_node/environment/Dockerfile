FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/mem0-node-task && chmod 0755 /home/user/mem0-node-task

LABEL Author="generate-harbor-tasks"
LABEL Description="Mem0 OSS Node.js task environment with Node.js 24 and an empty project directory at /home/user/mem0-node-task."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v24 (provides `node` and `npm`) so the agent can install and run the `mem0ai` Node.js SDK
#   - /home/user/mem0-node-task: empty project directory the agent must populate with package.json and an ESM Node.js script
