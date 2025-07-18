#!/bin/bash
# This is the public-facing version.
set -ex

export LD_LIBRARY_PATH=$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')

uvx --from 'huggingface_hub[cli]' huggingface-cli login --token $HUGGING_FACE_HUB_TOKEN

# Install PyTorch with CUDA 12.8 support for RTX 5060 Ti (sm_120)
uv pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

CARGO_TARGET_DIR=/app/target cargo install --features cuda moshi-server@0.6.3

# Subtle detail here: We use the full path to `moshi-server` because there is a `moshi-server` binary
# from the `moshi` Python package. We'll fix this conflict soon.
/root/.cargo/bin/moshi-server $@