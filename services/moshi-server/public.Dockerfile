# This is the public-facing version.
FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04 AS base

# Argument de build conditionnel pour appliquer le patch FORCE_FLOAT_16
ARG FORCE_FLOAT_16=false

# Set environment variables to avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    ca-certificates \
    libssl-dev \
    git \
    pkg-config \
    cmake \
    wget \
    openssh-client \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /uvx /bin/

WORKDIR /app

# When starting the container for the first time, we need to compile and download
# everything, so disregarding healthcheck failure for 10 minutes is fine.
# We have a volume storing the build cache, so subsequent starts will be faster.
HEALTHCHECK --start-period=10m \
    CMD curl --fail http://localhost:8080/api/build_info || exit 1

EXPOSE 8080
ENV RUST_BACKTRACE=1

# Télécharger les fichiers de base
RUN wget https://raw.githubusercontent.com/kyutai-labs/moshi/a40c5612ade3496f4e4aa47273964404ba287168/rust/moshi-server/pyproject.toml
RUN wget https://raw.githubusercontent.com/kyutai-labs/moshi/a40c5612ade3496f4e4aa47273964404ba287168/rust/moshi-server/uv.lock

# Cloner le repo complet pour pouvoir patcher
RUN git clone https://github.com/kyutai-labs/moshi.git /tmp/moshi && \
    cd /tmp/moshi && \
    git checkout a40c5612ade3496f4e4aa47273964404ba287168

# Copier les patches depuis le contexte de build
COPY patches/ /tmp/patches/

# Appliquer le patch SEULEMENT si FORCE_FLOAT_16=true
RUN if [ "$FORCE_FLOAT_16" = "true" ]; then \
        echo "Applying FORCE_FLOAT_16 patch..." && \
        cd /tmp/moshi && \
        patch -p1 < /tmp/patches/moshi-server-force_f16.patch; \
    else \
        echo "Skipping FORCE_FLOAT_16 patch"; \
    fi

# Copier les sources (patchées ou non)
RUN cp -r /tmp/moshi/rust/moshi-server ./moshi-server

COPY . .

ENTRYPOINT ["uv", "run", "--locked", "--project", "./moshi-server", "./start_moshi_server_public.sh"]