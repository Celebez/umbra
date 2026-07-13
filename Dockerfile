# syntax=docker/dockerfile:1
# Build stage: install Umbra + the Umbra engine in one image.
FROM python:3.11-slim AS build

# Install the Umbra engine (Rust + V8 CDP browser).
ARG UMBRA_ENGINE_VERSION=latest
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://github.com/Celebez/umbra/releases/${UMBRA_ENGINE_VERSION}/download/obscura-x86_64-linux.tar.gz" -o /tmp/obscura.tar.gz \
    && tar xzf /tmp/obscura.tar.gz -C /tmp \
    && install -m 0755 /tmp/obscura-x86_64-linux /usr/local/bin/obscura \
    && ln -sf /usr/local/bin/obscura /usr/local/bin/umbra-engine \
    && rm -f /tmp/obscura.tar.gz /tmp/obscura-x86_64-linux \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY umbra ./umbra
RUN pip install --no-cache-dir .

# Final stage: thin runtime.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/umbra-engine /usr/local/bin/umbra-engine
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["umbra"]
CMD ["--help"]
