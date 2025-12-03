#!/bin/env bash 

# Ensure script is interpreted with bash
set -e  # Exit on error
set -u  # Exit on undefined variables

# Set FSL environment variable
FSLDIR=/opt/conda
export FSLDIR

# Log the current shell and environment
echo "Current shell: $SHELL"
echo "Current interpreter: $(readlink -f /proc/$$/exe)"
echo "FSLDIR set to: $FSLDIR"

# Add FSL to PATH if needed
export PATH=$FSLDIR/bin:$PATH

# Optional: Source FSL configuration
if [ -f "${FSLDIR}/etc/fslconf/fsl.sh" ]; then
    source "${FSLDIR}/etc/fslconf/fsl.sh"
fi

# Set CUDA device (if applicable)
export CUDA_VISIBLE_DEVICES=0

# printf "CUDA test:\n"
ls /dev/nvidia*
nvidia-smi

/opt/conda/bin/python -c "import torch; print(torch.version.cuda)"
# Run the gear
export PATH="/opt/conda/bin:$PATH"
export PYTHONPATH="/opt/conda/lib/python3.8/site-packages:$PYTHONPATH"

python /flywheel/v0/run.py
# exec /opt/conda/bin/python /flywheel/v0/run.py