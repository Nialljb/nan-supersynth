# SuperSynth

Singularity container for FreeSurfer's `mri_super_synth` — synthesizes T1w, T2w, and FLAIR contrasts plus a brain segmentation from a single input scan. Designed for HPC/SLURM environments.

---

## Overview

SuperSynth uses deep learning to generate multiple MRI contrasts from a single structural input, enabling enhanced brain imaging analysis when multiple sequences are not available.

**Outputs:**

| File | Description |
|------|-------------|
| `*_desc-synth_T1w.nii.gz` | Synthetic T1w |
| `*_desc-synth_T2w.nii.gz` | Synthetic T2w |
| `*_desc-synth_FLAIR.nii.gz` | Synthetic FLAIR |
| `*_desc-supersynth_dseg.nii.gz` | Brain segmentation (FreeSurfer LUT) |
| `*_desc-supersynth_volumes.csv` | Volumetric measurements per structure |

---

## Requirements

- Singularity / Apptainer
- CUDA-compatible GPU with 16 GB+ VRAM (`--nv` flag required)
- 64 GB system RAM (tool peaks above 32 GB)

> The FreeSurfer license is embedded in the `nialljb/fw-supersynth` base image — no separate license file is needed.

---

## Building the Image

### On AWS EC2 (recommended)

See the full end-to-end guide: [docs/aws-guide.md](docs/aws-guide.md)

**Quick start** (`g4dn.7xlarge`, 300 GB EBS root, Deep Learning Base AMI):

```bash
# Authenticate to Docker Hub — avoids 429 rate-limit errors on AWS public IPs
docker login

# Clone and build
git clone <repo-url> && cd nan-supersynth
./build_singularity.sh
```

### On HPC (fakeroot required)

Requires fakeroot to be enabled by a system admin:

```bash
sudo singularity config fakeroot --add <username>
```

Redirect cache to scratch to avoid home directory quota limits:

```bash
SINGULARITY_CACHEDIR=/scratch/${USER}/.apptainer_cache ./build_singularity.sh
```

### Alternative — convert from local Docker daemon

```bash
docker pull nialljb/fw-supersynth:latest
singularity build supersynth.sif docker-daemon://nialljb/fw-supersynth:latest
```

---

## Usage

### Basic

```bash
singularity exec --nv supersynth.sif bash /start.sh \
    --input /data/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz \
    --output /results/sub-01/ses-01/supersynth
```

### Full options

```bash
singularity exec --nv supersynth.sif bash /start.sh --help
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | required | Input NIfTI file or directory |
| `--output` | required | Output directory |
| `--work-dir` | `/tmp/supersynth_work` | Intermediate working directory |
| `--subject` | auto from path | Subject identifier |
| `--session` | auto from path | Session identifier |
| `--mode` | `invivo` | `invivo` or `exvivo` |
| `--debug` | flag | Verbose logging |

---

## SLURM

Edit the user configuration section of `run_supersynth_slurm.sh` then submit:

```bash
sbatch run_supersynth_slurm.sh
```

Key resource requirements:

```bash
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
```

> **Note:** The tool requires 16 GB+ GPU VRAM. On Flywheel this was the `gpuplus` profile. On SLURM, request a node with a suitable GPU (e.g. A100, V100 32 GB).

---

## File Structure

```
├── start.sh                      # Singularity entrypoint (FreeSurfer env + run_supersynth.py)
├── run_supersynth.py             # CLI entry point (argparse)
├── supersynth.def                # Singularity build definition
├── build_singularity.sh          # Build script
├── build_docker_to_singularity.sh
├── supersynth_config.json        # HPC scheduler metadata
├── run_supersynth_slurm.sh       # SLURM submission template
├── utils/
│   └── curate_supersynth_output.py
└── docs/
    ├── changelog.md
    └── singularity-migration.md
```

---

## Container Internals

Call chain inside the container:

```
singularity exec --nv supersynth.sif bash /start.sh
  └── start.sh        (sources FreeSurfer env)
        └── /app/run_supersynth.py  (finds inputs, calls mri_super_synth, curates outputs)
              └── utils/curate_supersynth_output.py  (MGZ → BIDS NIfTI)
```

`start.sh` is placed at `/start.sh`; all other repo files land under `/app/`.
