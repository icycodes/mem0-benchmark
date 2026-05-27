FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        build-essential && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        mem0ai \
        chromadb \
        openai && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/myproject && chmod 0755 /home/user/myproject

LABEL Author="generate-harbor-tasks"
LABEL Description="Mem0 OSS Python environment with Chroma vector store dependencies pre-installed for the oss_chroma_vector_store_py task."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - mem0ai (Python SDK) installed via pip3 for Mem0 OSS usage
#   - chromadb installed via pip3 for the Chroma vector store backend
#   - openai installed via pip3 to satisfy Mem0 OSS's default LLM/embedder providers
#   - build-essential to compile any native deps required by chromadb / mem0
#   - /home/user/myproject: empty project directory the executor must populate
