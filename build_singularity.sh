#!/bin/bash
#
# Build script for SuperSynth Singularity image
# Targets an AWS EC2 instance with a large EBS root volume (>=50 GB free).
# Run from the repository root as the normal instance user (ec2-user / ubuntu).
#

set -e

IMAGE_NAME="supersynth.sif"
DEF_FILE="supersynth.def"

# ---------------------------------------------------------------------------
# Docker Hub authentication check
# The base image (~10 GB) is pulled from Docker Hub. Anonymous pulls from
# AWS public IPs frequently hit the rate limit (100 pulls / 6 h). Log in
# first to avoid a mid-build failure.
# ---------------------------------------------------------------------------
if ! docker info &>/dev/null; then
    echo "Warning: Docker daemon not running — Apptainer will pull directly from registry."
    echo "         If the pull fails with '429 Too Many Requests', run: docker login"
else
    if ! grep -q 'auth' "${HOME}/.docker/config.json" 2>/dev/null; then
        echo "Warning: No Docker Hub credentials found in ~/.docker/config.json"
        echo "         Rate-limit errors are likely. Run 'docker login' before building."
    fi
fi

# ---------------------------------------------------------------------------
# Apptainer cache + tmp directories
# On an EC2 instance with a large EBS volume everything lives under the root
# filesystem. HOME and /tmp both have plenty of space — no need to probe
# HPC-specific mounts (/scratch, /data/project, etc.).
# Override either variable on the command line if needed:
#   APPTAINER_CACHEDIR=/data/.cache APPTAINER_TMPDIR=/data/.tmp ./build_singularity.sh
# ---------------------------------------------------------------------------
export APPTAINER_CACHEDIR="${APPTAINER_CACHEDIR:-${HOME}/.apptainer_cache}"
export SINGULARITY_CACHEDIR="${SINGULARITY_CACHEDIR:-${APPTAINER_CACHEDIR}}"
export APPTAINER_TMPDIR="${APPTAINER_TMPDIR:-/tmp/.apptainer_tmp}"
export SINGULARITY_TMPDIR="${SINGULARITY_TMPDIR:-${APPTAINER_TMPDIR}}"
export TMPDIR="${TMPDIR:-${APPTAINER_TMPDIR}}"

mkdir -p "${APPTAINER_CACHEDIR}" "${APPTAINER_TMPDIR}"

echo "Building SuperSynth Singularity image..."
echo "Definition file:    ${DEF_FILE}"
echo "Output image:       ${IMAGE_NAME}"
echo "APPTAINER_CACHEDIR: ${APPTAINER_CACHEDIR}"
echo "APPTAINER_TMPDIR:   ${APPTAINER_TMPDIR}"

# Sanity-check free space (need ~40 GB for Docker layer extraction)
FREE_GB=$(df -BG "${APPTAINER_TMPDIR}" | awk 'NR==2 {gsub(/G/,"",$4); print $4}')
if [[ -n "${FREE_GB}" && "${FREE_GB}" -lt 40 ]]; then
    echo "Error: only ${FREE_GB}G free in ${APPTAINER_TMPDIR}. Need at least 40 GB."
    echo "       Override: APPTAINER_TMPDIR=/path/to/large/fs ./build_singularity.sh"
    exit 1
fi

# Check if Apptainer or Singularity is available
if command -v apptainer &> /dev/null; then
    CONTAINER_CMD="apptainer"
elif command -v singularity &> /dev/null; then
    CONTAINER_CMD="singularity"
else
    echo "Error: neither apptainer nor singularity is installed or in PATH"
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

# Determine whether to use --fakeroot (required when not running as root)
BUILD_FLAGS=()
if [[ "$(id -u)" -ne 0 ]]; then
    echo "Not running as root — enabling --fakeroot (must be configured by admin)"
    BUILD_FLAGS+=(--fakeroot)
fi

# Build the image
echo "Building Singularity image (this may take a while)..."
"$CONTAINER_CMD" build "${BUILD_FLAGS[@]}" "$IMAGE_NAME" "$DEF_FILE"

if [[ $? -eq 0 ]]; then
    echo "Successfully built: $IMAGE_NAME"
    echo "Image size: $(du -h "$IMAGE_NAME" | cut -f1)"

    echo "Testing the image..."
    "$CONTAINER_CMD" test "$IMAGE_NAME"

    if [[ $? -eq 0 ]]; then
        echo "Image test passed!"
        echo ""
        echo "You can now use the image with:"
        echo "  ${CONTAINER_CMD} exec --nv $IMAGE_NAME python /app/run_supersynth.py --help"
    else
        echo "Warning: Image test failed"
    fi
else
    echo "Error: Failed to build Singularity image"
    exit 1
fi
