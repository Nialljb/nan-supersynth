# CLAUDE.md — nan-supersynth

## Project Overview

SuperSynth is a FreeSurfer deep-learning tool (`mri_super_synth`) that synthesizes multiple MRI contrasts (T1w, T2w, FLAIR) and a segmentation from a single input scan. Packaged as a Singularity container for HPC/SLURM environments.

See [docs/singularity-migration.md](docs/singularity-migration.md) for the original migration plan from Flywheel gear.

---

## Repo Structure

| File | Role |
|------|------|
| `run_supersynth.py` | CLI entry point — argparse, finds inputs, calls `mri_super_synth`, curates outputs |
| `start.sh` | Singularity entrypoint — sets FreeSurfer/CUDA env, exec's `run_supersynth.py` |
| `supersynth.def` | Singularity definition — bootstraps from `nialljb/fw-supersynth:latest` |
| `build_singularity.sh` | Build script (fakeroot + post-build test) |
| `build_docker_to_singularity.sh` | Alternative: Docker → Singularity conversion |
| `supersynth_config.json` | HPC scheduler metadata (image path, SLURM defaults) |
| `run_supersynth_slurm.sh` | SLURM job submission template |
| `utils/curate_supersynth_output.py` | Converts `.mgz` outputs → BIDS `.nii.gz` |
| `docs/changelog.md` | Version history |
| `docs/singularity-migration.md` | Migration plan reference |

---

## Processing Pipeline

1. `singularity exec --nv supersynth.sif` → runs `/start.sh`
2. `start.sh` sources FreeSurfer env → exec's `run_supersynth.py`
3. `run_supersynth.py` finds all `.nii`/`.nii.gz` under `--input`
4. Calls `mri_super_synth --i <files> --o <work_dir> --mode invivo`
5. `curate_outputs()` converts `.mgz` → `.nii.gz`, renames to BIDS

### Outputs (from `mri_super_synth`)

| File | Description |
|------|-------------|
| `SynthT1.mgz` | Synthetic T1w |
| `SynthT2.mgz` | Synthetic T2w |
| `SynthFLAIR.mgz` | Synthetic FLAIR |
| `segmentation.mgz` | Brain segmentation (FreeSurfer LUT indices) |
| `volumes.csv` | Volumetric measurements per structure |

---

## Build

```bash
# Recommended — requires fakeroot enabled for your user
./build_singularity.sh

# Alternative — convert existing Docker image
./build_docker_to_singularity.sh
```

Cache large Docker layers to scratch to avoid home quota limits:
```bash
SINGULARITY_CACHEDIR=/scratch/${USER}/.apptainer_cache ./build_singularity.sh
```

---

## Run

```bash
singularity exec --nv supersynth.sif \
    --input /data/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz \
    --output /results \
    --subject 01 \
    --session 01
```

### SLURM

```bash
# Edit paths in the USER CONFIGURATION section, then:
sbatch run_supersynth_slurm.sh
```

Key SLURM resources required: `--mem=64G --gres=gpu:1`

---

## Key Environment Variables (inside container)

```
FREESURFER_HOME=/usr/local/freesurfer/7-dev
CUDA_VISIBLE_DEVICES=0
```

## HPC Config Format

```json
{
  "hpc_config": {
    "image_path": "/home/{hpc_username}/cortex/modules/supersynth.sif",
    "command_template": "python /app/run_supersynth.py --input {input_file} --output {output_dir}",
    "default_cpus": 4,
    "default_mem": "64G",
    "default_gpus": 1,
    "default_time": "01:00:00"
  }
}
```

---

## Key Dependencies

| Tool | Purpose |
|------|---------|
| `mri_super_synth` | Core synthesis (FreeSurfer 7-dev) |
| `mri_convert` | `.mgz` → `.nii.gz` conversion |
| nibabel, numpy, pandas | Python I/O |

---

## Building on AWS EC2

The `build_singularity.sh` script is written for EC2. All cache and tmp paths default to `$HOME` and `/tmp` — both live on the EBS root volume, so no HPC-specific mounts need to exist.

**Recommended setup:** `g4dn.7xlarge` with a **300 GB EBS root volume**. The GPU is needed only for the post-build `%test` step; any instance with ≥50 GB free on `/tmp` can build the image.

### 1 — Instance and volume sizing

| Resource | Notes |
|----------|-------|
| Instance type | Any with ≥50 GB free on root; GPU instance for post-build `%test` |
| Root EBS volume | **300 GB** (Docker layer extraction needs ~40 GB in `/tmp` alone) |
| FreeSurfer license | **Embedded in `nialljb/fw-supersynth`** — no separate license file needed |

### 2 — Docker Hub rate limiting

AWS public IPs frequently hit Docker Hub anonymous pull limits (100 pulls / 6 h). Authenticate before building:

```bash
docker login   # credentials stored in ~/.docker/config.json; Apptainer reads them automatically
```

Or pre-pull to the local Docker daemon and convert (bypasses registry entirely):

```bash
docker pull nialljb/fw-supersynth:latest
singularity build supersynth.sif docker-daemon://nialljb/fw-supersynth:latest
```

### 3 — Pinning the base image

`supersynth.def` bootstraps from `nialljb/fw-supersynth:latest`. The `:latest` tag is a moving target. To make the build reproducible, pin to the current digest **before** building:

```bash
docker pull nialljb/fw-supersynth:latest
docker inspect --format='{{index .RepoDigests 0}}' nialljb/fw-supersynth:latest
# e.g. nialljb/fw-supersynth@sha256:<hex>
# Replace the From: line in supersynth.def with the sha256 reference
```

### 4 — Root vs fakeroot

`build_singularity.sh` automatically adds `--fakeroot` for non-root users. Enable fakeroot once after launching the instance:

```bash
sudo singularity config fakeroot --add $USER
```

Alternatively `sudo ./build_singularity.sh` builds as root (no fakeroot needed).

### 5 — Full command sequence

```bash
# On the EC2 instance (Apptainer must be installed)
git clone <repo-url>
cd nan-supersynth

# Enable fakeroot for the instance user (one-time)
sudo singularity config fakeroot --add $USER

# Authenticate to Docker Hub
docker login

# Build — cache lands in $HOME/.apptainer_cache, tmp in /tmp/.apptainer_tmp
./build_singularity.sh

# Verify
singularity exec --nv supersynth.sif bash /start.sh --help
```
