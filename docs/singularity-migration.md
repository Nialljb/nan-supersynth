# Singularity Migration Plan

Refactor nan-supersynth from a Flywheel gear into a Singularity container for HPC/SLURM use, following the pattern established in `~/repos/mrr`.

---

## Current vs Target Architecture

```
CURRENT (Flywheel gear)            TARGET (Singularity / HPC)
──────────────────────────         ──────────────────────────────
run.py          ──────────────►    run_supersynth.py   (CLI entry, argparse)
start.sh        ──────────────►    app/supersynth-singularity.sh
Dockerfile      ──────────────►    supersynth.def  +  build_singularity.sh
manifest.json   (keep for FW)      supersynth_config.json  (HPC metadata)
                                   run_supersynth_slurm.sh
utils/curate_supersynth_output.py  (refactor — remove Flywheel dependency)
```

Flywheel files (`run.py`, `start.sh`, `Dockerfile`, `manifest.json`) are **kept intact** so the gear continues to work on the Flywheel platform.

---

## Step-by-Step Plan

### Step 1 — Create `run_supersynth.py`

New CLI entry point modelled on `run_mrr.py`. Replaces Flywheel-specific `run.py` for standalone use.

**Remove:**
- `GearToolkitContext` import
- Hardcoded `/flywheel/v0/` paths
- `config.json` loading

**Add:**
- `argparse` with the following arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | required | Input NIfTI file(s) or directory |
| `--output` | required | Output directory |
| `--work-dir` | `/tmp/supersynth_work` | Working directory |
| `--subject` | auto from path | Subject identifier |
| `--session` | auto from path | Session identifier |
| `--mode` | `invivo` | SuperSynth mode (`invivo` or `exvivo`) |
| `--debug` | flag | Enable debug logging |

**Logic:**
1. Find all `.nii` / `.nii.gz` files under `--input`
2. Create `work_dir` and `output_dir`
3. Call `mri_super_synth --i <files> --o <work_dir> --mode <mode>`
4. Call `curate_outputs(work_dir, output_dir, subject, session)`

---

### Step 2 — Create `app/supersynth-singularity.sh`

Thin shell wrapper that sets the FreeSurfer/FSL environment and delegates to `run_supersynth.py`. Mirrors `app/mrr-singularity.sh`.

```bash
#!/bin/bash
export FREESURFER_HOME=/usr/local/freesurfer/7-dev
source $FREESURFER_HOME/SetUpFreeSurfer.sh
export FSLDIR=/opt/conda
export PATH=$FSLDIR/bin:$PATH
export CUDA_VISIBLE_DEVICES=0

python /app/run_supersynth.py "$@"
```

---

### Step 3 — Refactor `utils/curate_supersynth_output.py`

The current implementation calls `demo(context)` from the Flywheel SDK to get subject/session labels. For Singularity use these come from CLI args.

**Changes:**
- Change `curate_outputs(context, work_dir, output_dir)` signature to
  `curate_outputs(work_dir, output_dir, subject_label, session_label)`
- Remove `FLYWHEEL_AVAILABLE` guard and `demo()` call
- Keep all MGZ → NIfTI conversion and BIDS naming logic unchanged
- Keep `volumes.csv` processing (column mapping via FreeSurfer LUT) unchanged
- Remove `dataset_description.json` container reference to Flywheel Docker tag; make it version-agnostic

The Flywheel `run.py` will need a small update to pass `subject_label` and `session_label` to the new signature instead of passing `context`.

---

### Step 4 — Create `supersynth.def`

Singularity definition file. Bootstrap from the existing Docker image so all FreeSurfer/CUDA dependencies are inherited.

```singularity
Bootstrap: docker
From: nialljb/fw-supersynth:latest

%help
    SuperSynth Singularity Image
    Synthesizes MRI contrasts using FreeSurfer mri_super_synth.

    Usage:
        singularity exec --nv supersynth.sif python /app/run_supersynth.py \
            --input <input> --output <output>

%labels
    Author Niall Bourke
    Version 0.1.0

%environment
    export HOME=/root
    export FREESURFER_HOME=/usr/local/freesurfer/7-dev
    export PATH="${FREESURFER_HOME}/bin:${PATH}"
    export FSLDIR=/opt/conda
    export PATH="${FSLDIR}/bin:${PATH}"
    export CUDA_VISIBLE_DEVICES=0
    export LANG="C.UTF-8"

%files
    ./ /app/

%post
    export DEBIAN_FRONTEND=noninteractive
    source /usr/local/freesurfer/7-dev/SetUpFreeSurfer.sh || true

    cd /app
    /opt/conda/bin/pip install --no-cache-dir nibabel numpy pandas

    chmod +rx /app/run_supersynth.py
    chmod +rx /app/app/supersynth-singularity.sh

    find /root/.cache -type f -delete 2>/dev/null || true

%runscript
    exec python3 /app/run_supersynth.py "$@"

%test
    echo "Testing FreeSurfer..."
    which mri_super_synth || exit 1
    which mri_convert || exit 1
    echo "Testing Python environment..."
    python3 -c "import nibabel, numpy, pandas; print('Python deps OK')"
    python3 /app/run_supersynth.py --help > /dev/null || exit 1
    echo "All tests passed!"
```

> **Note:** The `.def` bootstraps from Docker so Miniconda, FSL, PyTorch, and CUDA layers from the `Dockerfile` are already baked in. No need to reinstall them in `%post`.

---

### Step 5 — Create `build_singularity.sh`

Direct copy of mrr's `build_singularity.sh` with names updated:

```bash
#!/bin/bash
set -e
IMAGE_NAME="supersynth.sif"
DEF_FILE="supersynth.def"
# fakeroot first, sudo fallback
if ! singularity build --fakeroot --ignore-fakeroot-command "$IMAGE_NAME" "$DEF_FILE"; then
    sudo singularity build "$IMAGE_NAME" "$DEF_FILE"
fi
singularity test "$IMAGE_NAME"
```

---

### Step 6 — Create `build_docker_to_singularity.sh`

```bash
#!/bin/bash
set -e
IMAGE_NAME="supersynth"
IMAGE_TAG="0.1.0"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
singularity build supersynth_from_docker.sif "docker-daemon://${IMAGE_NAME}:${IMAGE_TAG}"
```

---

### Step 7 — Create `supersynth_config.json`

HPC scheduler metadata (mirrors `mrr_config.json`):

```json
{
  "name": "supersynth",
  "version": "0.1.0",
  "description": "SuperSynth: deep learning MRI contrast synthesis via FreeSurfer",
  "author": "Niall Bourke",
  "maintainer": "Niall Bourke <niall.bourke@kcl.ac.uk>",
  "license": "MIT",
  "config": {
    "mode": {
      "default": "invivo",
      "description": "SuperSynth processing mode",
      "type": "string",
      "choices": ["invivo", "exvivo"]
    }
  },
  "container_info": {
    "type": "singularity",
    "base_image": "nialljb/fw-supersynth:latest",
    "entry_point": "python3 /app/run_supersynth.py",
    "requires_gpu": true
  },
  "hpc_config": {
    "image_path": "/home/{hpc_username}/images/supersynth.sif",
    "command_template": "python /app/run_supersynth.py --input {input_file} --output {output_dir}",
    "input_type": "acquisition",
    "input_pattern": ".*\\.nii(\\.gz)?$",
    "input_subdir": "anat",
    "requires_derivative": null,
    "output_name": "supersynth",
    "default_cpus": 4,
    "default_mem": "32G",
    "default_gpus": 1,
    "default_time": "01:00:00",
    "description": "Synthetic MRI contrast generation"
  }
}
```

---

### Step 8 — Create `run_supersynth_slurm.sh`

SLURM submission template. Key difference from mrr: requires `--gres=gpu:1` and `--nv` flag.

```bash
#!/bin/bash
#SBATCH --job-name=supersynth
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --time=01:00:00
#SBATCH --output=supersynth_%j.log

# --- Edit these ---
IMAGE=/home/${USER}/images/supersynth.sif
INPUT=/data/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz
OUTPUT=/results/sub-01/ses-01/supersynth
SUBJECT=01
SESSION=01
# ------------------

module load singularity

singularity exec --nv \
    -B /data:/data \
    -B /results:/results \
    "$IMAGE" python /app/run_supersynth.py \
        --input "$INPUT" \
        --output "$OUTPUT" \
        --subject "$SUBJECT" \
        --session "$SESSION"
```

---

## File Changes Summary

| Action | File |
|--------|------|
| **Create** | `run_supersynth.py` |
| **Create** | `app/supersynth-singularity.sh` |
| **Create** | `supersynth.def` |
| **Create** | `build_singularity.sh` |
| **Create** | `build_docker_to_singularity.sh` |
| **Create** | `supersynth_config.json` |
| **Create** | `run_supersynth_slurm.sh` |
| **Refactor** | `utils/curate_supersynth_output.py` (remove Flywheel dep) |
| **Minor update** | `run.py` (pass subject/session to new curate_outputs signature) |
| **Keep** | `Dockerfile`, `start.sh`, `manifest.json` (Flywheel compatibility) |
| **Keep** | `shared/utils/` (Flywheel path only) |

---

## Validation Checklist

- [ ] `singularity test supersynth.sif` passes
- [ ] `--help` runs without GPU
- [ ] `mri_super_synth` is on PATH inside container
- [ ] `mri_convert` is available for `.mgz` → `.nii.gz`
- [ ] Outputs are BIDS-named when `--subject` / `--session` are provided
- [ ] Outputs fall back to raw `.nii.gz` names when subject/session are unknown
- [ ] SLURM script runs end-to-end on a test subject
- [ ] Flywheel `run.py` still works (backward compatibility)
