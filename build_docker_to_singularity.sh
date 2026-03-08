#!/bin/bash
#
# Build SuperSynth Docker image then convert to Singularity.
# Use this path when building from Dockerfile is more reliable than
# a direct Singularity definition-file build.
#

set -e

IMAGE_NAME="supersynth"
IMAGE_TAG="0.1.0"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
SIF_NAME="supersynth_from_docker.sif"

echo "Building SuperSynth Docker image: $FULL_IMAGE_NAME"
docker build -t "$FULL_IMAGE_NAME" .

echo "Converting to Singularity: $SIF_NAME"
singularity build "$SIF_NAME" "docker-daemon://${FULL_IMAGE_NAME}"

echo "Successfully converted to Singularity: $SIF_NAME"
echo "Image size: $(du -h "$SIF_NAME" | cut -f1)"
echo ""
echo "Usage:"
echo "  singularity exec --nv $SIF_NAME python /app/run_supersynth.py --help"
