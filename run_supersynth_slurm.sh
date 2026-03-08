#!/bin/bash
#SBATCH --job-name=supersynth
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --time=01:00:00
#SBATCH --output=supersynth_%j.log
#SBATCH --error=supersynth_%j.err

# =============================================================================
# SuperSynth SLURM submission template
#
# Edit the variables in the USER CONFIGURATION section below, then submit with:
#   sbatch run_supersynth_slurm.sh
# =============================================================================

# --- USER CONFIGURATION ------------------------------------------------------
IMAGE=/home/${USER}/repos/nan-supersynth/supersynth.sif
INPUT=/home/${USER}/repos/nan-supersynth/data/sub-HYPE00_ses-HFC_acq-axi_T2w.nii.gz_ses-HFC_rec-mrr_T2.nii.gz
OUTPUT=/home/${USER}/repos/nan-supersynth/data/results/
SUBJECT=01
SESSION=01
MODE=invivo
# If the image was built with --pull (no fakeroot), also bind-mount the app:
#   APP_DIR=/path/to/nan-supersynth   (uncomment APP_DIR and add -B $APP_DIR:/app below)
# -----------------------------------------------------------------------------

echo "Job ID:   $SLURM_JOB_ID"
echo "Node:     $SLURMD_NODENAME"
echo "Image:    $IMAGE"
echo "Input:    $INPUT"
echo "Output:   $OUTPUT"
echo "Subject:  $SUBJECT"
echo "Session:  $SESSION"

module load singularity 2>/dev/null || true

singularity exec --nv \
    -B "$(dirname "$INPUT")":"$(dirname "$INPUT")" \
    -B "$OUTPUT":"$OUTPUT" \
    "$IMAGE" \
    bash /start.sh \
        --input    "$INPUT" \
        --output   "$OUTPUT" \
        --subject  "$SUBJECT" \
        --session  "$SESSION" \
        --mode     "$MODE"

echo "SuperSynth job complete."
