#!/bin/bash
#SBATCH --job-name=supersynth
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err

set -euo pipefail

# User config
PROJECT_DIR="/home/k2252514/repos/nan-supersynth"
SIF_IMAGE="${PROJECT_DIR}/supersynth_v0.1.0-cuda.sif"
INPUT_FILE="${PROJECT_DIR}/data/sub-HYPE00_ses-HFC_acq-axi_T2w.nii.gz_ses-HFC_rec-mrr_T2.nii.gz"
OUTPUT_DIR="${PROJECT_DIR}/data/results"

mkdir -p "${OUTPUT_DIR}"

# Use Apptainer if available; otherwise fall back to Singularity.
if command -v apptainer >/dev/null 2>&1; then
    CONTAINER_RUNTIME="apptainer"
else
    CONTAINER_RUNTIME="singularity"
fi

echo "Running on host: $(hostname)"
echo "SLURM job ID: ${SLURM_JOB_ID:-N/A}"
echo "Container runtime: ${CONTAINER_RUNTIME}"

"${CONTAINER_RUNTIME}" exec --nv \
    --bind "${PROJECT_DIR}/data:/data" \
    "${SIF_IMAGE}" \
    python3 /app/run_supersynth.py \
    --input "${INPUT_FILE}" \
    --output "${OUTPUT_DIR}" \
    --no-test-time-flipping \
    --tile-size 128