#!/bin/bash
# This is the public-facing version.
set -ex

export FORCE_FLOAT_16=${FORCE_FLOAT_16:-true}

export LD_LIBRARY_PATH=$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')

uvx --from 'huggingface_hub[cli]' huggingface-cli login --token $HUGGING_FACE_HUB_TOKEN

# Install PyTorch with CUDA 12.8 support for RTX 5060 Ti (sm_120)
uv pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

rm -rf /root/.cargo/registry/src/index.crates.io-*/pin-utils-*
# Copier le workspace complet
cp -r /tmp/moshi/rust /tmp/workspace-patched
cd /tmp/workspace-patched/moshi-server

if [ "${FORCE_FLOAT_16:-false}" == "true" ]; then
    echo "FORCE_FLOAT_16=true - Application du patch F16"
    # Ajouter l'import DType à lm.rs SEULEMENT s'il n'existe pas déjà
    if ! grep -q "use candle::DType;" src/lm.rs; then
        sed -i '3a use candle::DType;' src/lm.rs
    fi
    # Remplacer bf16_default_to_f32 par DType::F32 dans tous les fichiers
    sed -i 's/dev\.bf16_default_to_f32()/DType::F16/g' src/asr.rs src/batched_asr.rs src/lm.rs src/tts.rs
else
    echo "FORCE_FLOAT_16=false - BF16 natif utilisé, pas de patch appliqué"
fi
# Compiler
cd /tmp/workspace-patched && CARGO_TARGET_DIR=/app/target cargo build --package moshi-server --features cuda --release
cp /app/target/release/moshi-server /root/.cargo/bin/moshi-server
cd /app

# Subtle detail here: We use the full path to `moshi-server` because there is a `moshi-server` binary
# from the `moshi` Python package. We'll fix this conflict soon.
/root/.cargo/bin/moshi-server $@
