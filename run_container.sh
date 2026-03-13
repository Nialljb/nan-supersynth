#!/usr/bin/env bash
set -euo pipefail

# Host-side launcher for the SuperSynth SIF.
# It auto-detects required bind mounts from --input and --output paths.

IMAGE="supersynth.sif"
USE_NV=1
INPUT=""
OUTPUT=""
PASSTHROUGH=()

usage() {
    cat <<'EOF'
Usage:
  ./run_container.sh --input <path> --output <path> [options] [-- extra run_supersynth args]

Options:
  --image <path>   Path to SIF image (default: supersynth.sif)
  --cpu            Disable --nv (GPU passthrough)
  -h, --help       Show this help

Examples:
  ./run_container.sh \
      --input /data/sub-01_ses-01_T2w.nii.gz \
      --output /data/output

  ./run_container.sh \
      --input /data/sub-01_ses-01_T2w.nii.gz \
      --output /data/output \
      -- --no-test-time-flipping --tile-size 128
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input)
            INPUT="${2:-}"
            shift 2
            ;;
        --output)
            OUTPUT="${2:-}"
            shift 2
            ;;
        --image)
            IMAGE="${2:-}"
            shift 2
            ;;
        --cpu)
            USE_NV=0
            shift
            ;;
        --)
            shift
            PASSTHROUGH=("$@")
            break
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$INPUT" || -z "$OUTPUT" ]]; then
    echo "Error: --input and --output are required." >&2
    usage >&2
    exit 2
fi

if [[ ! -e "$IMAGE" ]]; then
    echo "Error: image not found: $IMAGE" >&2
    exit 1
fi

if [[ ! -e "$INPUT" ]]; then
    echo "Error: input path not found on host: $INPUT" >&2
    exit 1
fi

# Normalize to absolute host paths.
INPUT_ABS="$(readlink -f "$INPUT")"
if [[ -d "$INPUT_ABS" ]]; then
    INPUT_BIND_SRC="$INPUT_ABS"
else
    INPUT_BIND_SRC="$(dirname "$INPUT_ABS")"
fi

mkdir -p "$OUTPUT"
OUTPUT_ABS="$(readlink -f "$OUTPUT")"
if [[ -d "$OUTPUT_ABS" ]]; then
    OUTPUT_BIND_SRC="$OUTPUT_ABS"
else
    OUTPUT_BIND_SRC="$(dirname "$OUTPUT_ABS")"
fi

# Build de-duplicated bind list.
BIND_CSV=""
add_bind() {
    local src="$1"
    local spec="${src}:${src}"
    if [[ -z "$BIND_CSV" ]]; then
        BIND_CSV="$spec"
    elif [[ ",$BIND_CSV," != *",$spec,"* ]]; then
        BIND_CSV+="${BIND_CSV:+,}$spec"
    fi
}

add_bind "$INPUT_BIND_SRC"
add_bind "$OUTPUT_BIND_SRC"

CMD=(singularity run)
if [[ "$USE_NV" -eq 1 ]]; then
    CMD+=(--nv)
fi
CMD+=(--bind "$BIND_CSV" "$IMAGE" --input "$INPUT_ABS" --output "$OUTPUT_ABS")
CMD+=("${PASSTHROUGH[@]}")

echo "Image:  $IMAGE"
echo "Input:  $INPUT_ABS"
echo "Output: $OUTPUT_ABS"
echo "Bind:   $BIND_CSV"
echo

exec "${CMD[@]}"
