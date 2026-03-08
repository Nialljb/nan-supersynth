#!/bin/bash
#
# Build script for SuperSynth Singularity image
#

set -e

IMAGE_NAME="/data/project/pipeline/supersynth.sif"
DEF_FILE="supersynth.def"

# Force all Apptainer I/O to local disk to avoid NFS quota limits
export APPTAINER_CACHEDIR="/tmp/${USER}_apptainer_cache"
export SINGULARITY_CACHEDIR="/tmp/${USER}_apptainer_cache"
export APPTAINER_TMPDIR="/tmp"
mkdir -p "${APPTAINER_CACHEDIR}"

echo "Building SuperSynth Singularity image..."
echo "Definition file: $DEF_FILE"
echo "Output image: $IMAGE_NAME"

# Check if Singularity is available
if ! command -v singularity &> /dev/null; then
    echo "Error: Singularity is not installed or not in PATH"
    exit 1
fi

# Check if definition file exists
if [[ ! -f "$DEF_FILE" ]]; then
    echo "Error: Definition file '$DEF_FILE' not found"
    exit 1
fi

# Remove existing image if it exists
if [[ -f "$IMAGE_NAME" ]]; then
    echo "Removing existing image: $IMAGE_NAME"
    rm "$IMAGE_NAME"
fi

# Build the image
echo "Building Singularity image (this may take a while)..."
singularity build --fakeroot --ignore-fakeroot-command "$IMAGE_NAME" "$DEF_FILE"

if [[ $? -eq 0 ]]; then
    echo "Successfully built: $IMAGE_NAME"
    echo "Image size: $(du -h "$IMAGE_NAME" | cut -f1)"

    echo "Testing the image..."
    singularity test "$IMAGE_NAME"

    if [[ $? -eq 0 ]]; then
        echo "Image test passed!"
        echo ""
        echo "You can now use the image with:"
        echo "  singularity exec --nv $IMAGE_NAME python /app/run_supersynth.py --help"
    else
        echo "Warning: Image test failed"
    fi
else
    echo "Error: Failed to build Singularity image"
    exit 1
fi
