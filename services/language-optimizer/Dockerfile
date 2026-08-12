# ═══════════════════════════════════════════════════════════════════════════
# Stage 1: Build React UI
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# Single stage: Python runtime
# UI is pre-built locally (run: cd ui && npm install && npm run build)
# ═══════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim

WORKDIR /app

# Install Node, Clang (for compile validation), curl, Rust, Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    clang gcc g++ make curl \
    ca-certificates gnupg lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (for Rust compile validation)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:$PATH"
# Prevent transformers/huggingface_hub from making network calls at runtime
# (model is already local — no need to check huggingface.co for updates)
ENV TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1

# Copy all source files including pre-built ui/build
COPY . .

# Install CPU-only torch — try PyPI first (has cpu wheels), fallback to pytorch CDN
RUN pip install --no-cache-dir torch \
    || pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
