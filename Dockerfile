# syntax=docker/dockerfile:1
# Build stage: install Umbra + the Obscura engine in one image.
FROM python:3.11-slim AS build

# Install the Obscura Rust headless browser (CDP core).
ARG OBSCURA_VERSION=v0.1.10
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://github.com/h4ckf0r0day/obscura/releases/download/${OBSCURA_VERSION}/obscura-x86_64-linux.tar.gz" -o /tmp/obscura.tar.gz \
    && tar xzf /tmp/obscura.tar.gz -C /usr/local/bin \
    && chmod +x /usr/local/bin/obscura /usr/local/bin/obscura-worker \
    && rm -f /tmp/obscura.tar.gz \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY umbra ./umbra
RUN pip install --no-cache-dir .

# Final stage: thin runtime.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/obscura /usr/local/bin/obscura
COPY --from=build /usr/local/bin/obscura-worker /usr/local/bin/obscura-worker
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["umbra"]
CMD ["--help"]
