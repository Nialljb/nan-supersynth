# SuperSynth — End-to-End AWS Guide

Build the Singularity image on an EC2 instance, run inference on input data, and retrieve outputs.

---

## Contents

1. [Instance setup](#1-instance-setup)
2. [Install Apptainer](#2-install-apptainer)
3. [Mount the NVMe instance store](#3-mount-the-nvme-instance-store)
4. [Clone the repo](#4-clone-the-repo)
5. [Authenticate to Docker Hub](#5-authenticate-to-docker-hub)
6. [Build the image](#6-build-the-image)
7. [Transfer input data](#7-transfer-input-data)
8. [Run inference](#8-run-inference)
9. [Retrieve outputs](#9-retrieve-outputs)
10. [Tear down](#10-tear-down)

---

## 1. Instance setup

### Recommended instance

| Property | Value |
|----------|-------|
| Instance type | `g4dn.xlarge` |
| vCPUs | **4** |
| RAM | 16 GB |
| GPU | 1× NVIDIA T4 (16 GB VRAM) |
| Instance store | 1× 125 GB NVMe SSD (ephemeral) |
| Root EBS | **300 GB** gp3 (set at launch — required) |

All `g4dn` variants carry the same NVIDIA T4 GPU. The T4 meets the 16 GB VRAM minimum and satisfies `--nv` CUDA passthrough. The xlarge uses 4 vCPUs — the minimum AWS G-instance quota — so it works within a default or minimally raised service limit.

> **vCPU quota:** AWS measures the "Running On-Demand G instances" limit in vCPUs. A quota of 4 allows exactly one `g4dn.xlarge`. If you need the limit raised, request an increase in Service Quotas (typically approved within minutes for small increases).

> The instance store on the xlarge is only 125 GB (vs 900 GB on the 7xlarge). The **300 GB EBS root volume is therefore essential** — all build tmp and cache land on `/tmp` which is on EBS. Do not skip the storage resize step.

### AMI

Use the official **Deep Learning Base AMI (Ubuntu 22.04)** — it ships with NVIDIA drivers, CUDA, Docker, and the aws-cli pre-installed.

Search in the AWS console: *AWS Marketplace → "Deep Learning Base AMI Ubuntu 22.04"*

### Root EBS volume

In the **Configure storage** step of the launch wizard, change the root volume from the default 8 GB to **300 GB** (gp3). This ensures `/tmp` has enough capacity for Docker layer extraction (~40 GB) and the final `.sif` image (~15–20 GB).

### Security group

Inbound: SSH (port 22) from your IP only. No other ports are needed.

### Key pair

Create or select an existing key pair. Download the `.pem` file.

---

## 2. Install Apptainer

The Deep Learning AMI does not include Apptainer. Run these commands after connecting via SSH.

```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libseccomp-dev \
    pkg-config \
    squashfs-tools \
    cryptsetup \
    curl wget git

# Install Go (Apptainer requires Go >= 1.21)
GO_VERSION=1.22.3
wget https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz
export PATH=/usr/local/go/bin:$PATH
echo 'export PATH=/usr/local/go/bin:$PATH' >> ~/.bashrc

# Download and install Apptainer
APPTAINER_VERSION=1.3.1
wget https://github.com/apptainer/apptainer/releases/download/v${APPTAINER_VERSION}/apptainer_${APPTAINER_VERSION}_amd64.deb
sudo apt-get install -y ./apptainer_${APPTAINER_VERSION}_amd64.deb

# Verify
apptainer --version

# Enable fakeroot for the current user (required when building as non-root)
sudo apptainer config fakeroot --add $USER
```

> Check the [Apptainer releases page](https://github.com/apptainer/apptainer/releases) for a newer version if needed.

---

## 3. Mount the NVMe instance store

The `g4dn.xlarge` includes a 125 GB NVMe instance store at `/dev/nvme1n1`. It is **not** mounted by default and is lost on stop/terminate. It can be used for working data during inference but is **not large enough on its own for the build** — the 300 GB EBS root handles build tmp and cache.

```bash
# Confirm the device exists
lsblk | grep nvme

# Format (only needed the first time — data will be erased)
sudo mkfs.ext4 /dev/nvme1n1

# Mount
sudo mkdir -p /data
sudo mount /dev/nvme1n1 /data
sudo chown $USER:$USER /data

# Verify
df -h /data   # should show ~880 GB available
```

> The instance store is **ephemeral** — its contents are lost when the instance stops or is terminated. Copy finished outputs to S3 before stopping.

---

## 4. Clone the repo

```bash
cd /data
git clone <repo-url> nan-supersynth
cd nan-supersynth
```

---

## 5. Authenticate to Docker Hub

The base image `nialljb/fw-supersynth:latest` (~10 GB) is pulled from Docker Hub. AWS public IPs hit the anonymous pull rate limit (100 pulls per 6 hours) frequently. Authenticating removes this limit.

```bash
docker login
# Enter your Docker Hub username and password / access token
```

Apptainer reads Docker credentials from `~/.docker/config.json` automatically.

> **Alternative — bypass Docker Hub entirely:** If you have Docker installed and have already pulled the image locally, Apptainer can convert it directly without a registry pull:
> ```bash
> docker pull nialljb/fw-supersynth:latest
> apptainer build supersynth.sif docker-daemon://nialljb/fw-supersynth:latest
> ```

---

## 6. Build the image

The build script handles cache/tmp placement, fakeroot detection, and post-build testing.

```bash
cd /data/nan-supersynth

# Optional: direct cache and tmp to the fast instance store
# (default is $HOME/.apptainer_cache and /tmp — both on the 300 GB EBS root)
# export APPTAINER_CACHEDIR=/data/.apptainer_cache
# export APPTAINER_TMPDIR=/data/.apptainer_tmp

./build_singularity.sh
```

**What happens:**
1. Checks Docker Hub credentials and available disk space (≥40 GB required in `/tmp`)
2. Pulls `nialljb/fw-supersynth:latest` from Docker Hub into the Apptainer layer cache
3. Extracts layers, runs `%post` (installs pip + Python deps), squashes into `supersynth.sif`
4. Runs `%test` — verifies `mri_super_synth`, `mri_convert`, and Python imports are present

**Expected duration:** 15–30 minutes depending on Docker Hub pull speed.

**Expected output image size:** ~15–20 GB.

```
Successfully built: supersynth.sif
Image size: 17G
...
All tests passed!
```

### Pinning the base image digest (optional but recommended)

`:latest` is a moving target. Pin to the exact digest to make future rebuilds reproducible:

```bash
# After pulling, get the digest
docker inspect --format='{{index .RepoDigests 0}}' nialljb/fw-supersynth:latest
# → nialljb/fw-supersynth@sha256:abc123...

# Edit supersynth.def — change:
#   From: nialljb/fw-supersynth:latest
# to:
#   From: nialljb/fw-supersynth@sha256:abc123...
```

---

## 7. Transfer input data

### From S3

```bash
# Copy a single subject
aws s3 cp s3://your-bucket/data/sub-01/ses-01/anat/ \
    /data/input/sub-01/ses-01/anat/ \
    --recursive

# Or sync an entire BIDS dataset
aws s3 sync s3://your-bucket/bids-dataset/ /data/input/
```

### From a local machine (scp)

```bash
scp -i your-key.pem \
    /local/path/sub-01_ses-01_T1w.nii.gz \
    ubuntu@<ec2-public-ip>:/data/input/
```

---

## 8. Run inference

```bash
# Single file
apptainer exec --nv /data/nan-supersynth/supersynth.sif bash /start.sh \
    --input  /data/input/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz \
    --output /data/output/sub-01/ses-01/supersynth \
    --subject 01 \
    --session 01

# Directory of NIfTI files (all .nii/.nii.gz under the directory will be processed)
apptainer exec --nv /data/nan-supersynth/supersynth.sif bash /start.sh \
    --input  /data/input/sub-01/ses-01/anat \
    --output /data/output/sub-01/ses-01/supersynth

# Check available options
apptainer exec --nv /data/nan-supersynth/supersynth.sif bash /start.sh --help
```

**CLI arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | required | NIfTI file or directory |
| `--output` | required | Output directory |
| `--work-dir` | `/tmp/supersynth_work` | Intermediate `.mgz` files |
| `--subject` | auto from path | Subject ID (used in BIDS filenames) |
| `--session` | auto from path | Session ID (used in BIDS filenames) |
| `--mode` | `invivo` | `invivo` or `exvivo` |
| `--debug` | flag | Verbose logging |

**Expected outputs in `--output`:**

| File | Description |
|------|-------------|
| `sub-01_ses-01_desc-synth_T1w.nii.gz` | Synthetic T1w |
| `sub-01_ses-01_desc-synth_T2w.nii.gz` | Synthetic T2w |
| `sub-01_ses-01_desc-synth_FLAIR.nii.gz` | Synthetic FLAIR |
| `sub-01_ses-01_desc-supersynth_dseg.nii.gz` | Brain segmentation |
| `sub-01_ses-01_desc-supersynth_volumes.csv` | Volumetric measurements |
| `dataset_description.json` | BIDS dataset metadata |

**Expected runtime:** 5–15 minutes per subject on a T4 GPU.

### Batch processing

```bash
for sub_dir in /data/input/sub-*/ses-*/anat; do
    sub=$(echo "$sub_dir" | grep -oP 'sub-\K[^/]+')
    ses=$(echo "$sub_dir" | grep -oP 'ses-\K[^/]+')
    out="/data/output/sub-${sub}/ses-${ses}/supersynth"
    echo "Processing sub-${sub} ses-${ses}..."
    apptainer exec --nv /data/nan-supersynth/supersynth.sif bash /start.sh \
        --input  "$sub_dir" \
        --output "$out" \
        --subject "$sub" \
        --session "$ses"
done
```

---

## 9. Retrieve outputs

### To S3

```bash
aws s3 sync /data/output/ s3://your-bucket/supersynth-outputs/
```

### To local machine (scp)

```bash
scp -i your-key.pem -r \
    ubuntu@<ec2-public-ip>:/data/output/ \
    /local/path/supersynth-outputs/
```

### Copy the `.sif` image to S3 for reuse

Avoid rebuilding on every instance launch by storing the finished image in S3:

```bash
aws s3 cp /data/nan-supersynth/supersynth.sif s3://your-bucket/containers/supersynth.sif
```

On the next instance:

```bash
aws s3 cp s3://your-bucket/containers/supersynth.sif /data/supersynth.sif
```

---

## 10. Tear down

> **Important:** The instance store (`/data`) is wiped when the instance stops. Ensure all outputs and the `.sif` are copied to S3 or downloaded before stopping.

```bash
# Final sync
aws s3 sync /data/output/ s3://your-bucket/supersynth-outputs/
aws s3 cp /data/nan-supersynth/supersynth.sif s3://your-bucket/containers/supersynth.sif

# Then stop or terminate the instance from the AWS console
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `429 Too Many Requests` during build | Docker Hub rate limit | Run `docker login` before building |
| `No space left on device` in build | `/tmp` too small | Use 300 GB EBS root or redirect `APPTAINER_TMPDIR` to `/data` |
| `mri_super_synth: not found` at runtime | `PATH` not set | Use `bash /start.sh` not `python3 /app/run_supersynth.py` directly |
| Build hangs at `mksquashfs` | Slow EBS I/O | Redirect tmp to the NVMe instance store (`APPTAINER_TMPDIR=/data/.tmp`) |
| `CUDA error: no kernel image` | Wrong CUDA version for T4 | Ensure the base image supports CUDA 11.x / 12.x (T4 is sm_75) |
| Output filenames missing `sub-`/`ses-` prefix | No BIDS path, no `--subject`/`--session` | Pass `--subject` and `--session` explicitly |
