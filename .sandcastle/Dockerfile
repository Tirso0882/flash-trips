FROM node:22-bookworm

# Docker Desktop routes this workstation through an enterprise TLS proxy.
# Keep the host trust bundle local and copy it to a container-native path so
# every tool, including the Cursor Agent CLI, validates intercepted TLS.
COPY --chown=root:root .sandcastle/host-ca.pem /etc/ssl/certs/host-ca.pem
ENV SSL_CERT_FILE=/etc/ssl/certs/host-ca.pem

# Install system dependencies
RUN apt-get update && apt-get install -y \
  git \
  curl \
  jq \
  && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && apt-get update && apt-get install -y gh \
  && rm -rf /var/lib/apt/lists/*

# Install just (task runner) and uv (Python toolchain) so the sandbox can run
# `just install`, `just verify`, and `just check` the same way the host does.
RUN curl -fsSL https://just.systems/install.sh | bash -s -- --to /usr/local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# pnpm is the package manager for this workspace. Corepack reads the pinned
# version from the "packageManager" field in package.json, so there is no
# version to duplicate here.
RUN corepack enable
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0

# Build-args for UID/GID alignment: sandcastle docker build-image
# defaults these to the host user's UID/GID so image-built files
# and bind-mounted files share an owner without runtime chown.
ARG AGENT_UID=1000
ARG AGENT_GID=1000

# Rename the base image's "node" user to "agent" and align UID/GID.
RUN groupmod -o -g $AGENT_GID node && usermod -o -u $AGENT_UID -g $AGENT_GID -d /home/agent -m -l agent node
USER ${AGENT_UID}:${AGENT_GID}

# Install Cursor Agent CLI
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl https://cursor.com/install -fsS | bash \
  && test -x /home/agent/.local/bin/agent \
  && /home/agent/.local/bin/agent --version

# Add Cursor CLI to PATH
ENV PATH="/home/agent/.local/bin:$PATH"

WORKDIR /home/agent

# In worktree sandbox mode, Sandcastle bind-mounts the git worktree at /home/agent/workspace
# and overrides the working directory to /home/agent/workspace at container start.
# Structure your Dockerfile so that /home/agent/workspace can serve as the project root.
ENTRYPOINT ["sleep", "infinity"]
