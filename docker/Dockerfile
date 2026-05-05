# Sandbox image used by the Validation Agent.
# Build with:  docker build -t forge-sandbox:latest -f docker/Dockerfile .
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        make \
        clang \
        clang-tidy \
        cppcheck \
        libc6-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user inside the sandbox.
RUN useradd -m -s /bin/bash forge
USER forge
WORKDIR /work

CMD ["bash"]
