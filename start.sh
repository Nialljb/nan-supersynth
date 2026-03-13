#!/bin/bash
#
# SuperSynth Singularity entrypoint.
# Sets FreeSurfer and CUDA environment then delegates to run_supersynth.py.
#

set -e

# FreeSurfer
export FREESURFER_HOME=/usr/local/freesurfer/7-dev
if [ -f "${FREESURFER_HOME}/SetUpFreeSurfer.sh" ]; then
    source "${FREESURFER_HOME}/SetUpFreeSurfer.sh"
fi

# CUDA
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

exec python3 /app/run_supersynth.py "$@"
