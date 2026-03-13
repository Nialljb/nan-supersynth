# Changelog

13/03/2026
Version 0.1.1 — Build hardening (AWS migration)

**`supersynth.def`**
- `%files`: replaced `./ /app/` glob with explicit file list — prevents `.git/` and build artefacts being copied into the image
- `%environment`: `CUDA_VISIBLE_DEVICES` now uses `${CUDA_VISIBLE_DEVICES:-0}` — preserves SLURM GPU assignment instead of overwriting it
- `%post`: added `export PIP_BREAK_SYSTEM_PACKAGES=1` + `pip install --upgrade pip` — fixes PEP 668 failure on Python 3.11+ / Debian Bookworm
- `%post`: pinned Python dependency versions (`nibabel>=3.2,<6`, `numpy>=1.21,<2`, `pandas>=1.3,<3`) — prevents numpy 2.x breaking changes

**`build_singularity.sh`**
- Removed all HPC-specific path logic (`/data/project/pipeline`, `/scratch`, etc.); cache defaults to `$HOME/.apptainer_cache`, tmp to `/tmp/.apptainer_tmp` — both live on the EC2 EBS root volume
- Replaced dynamic tmp-base candidate probing with simple fixed defaults; both are overrideable via env vars
- Added Docker Hub credential check — warns before build if unauthenticated (prevents mid-build 429 rate-limit failure on AWS public IPs)
- Removed echo of undefined `$BUILD_BASE`
- Added automatic `--fakeroot` for non-root users

**`run_supersynth.py`**
- Fixed single-file NIfTI extension check: `p.suffix in ('.nii', '.gz')` → `p.name.endswith('.nii') or p.name.endswith('.nii.gz')`

**`README.md`**
- Corrected FreeSurfer license note: license is embedded in `nialljb/fw-supersynth` — no bind-mount needed
- Replaced HPC-first build section with AWS-first instructions

**`setup.md`**
- Replaced multi-candidate AWS build guide with simplified 5-step sequence matching the script
- Removed incorrect FreeSurfer license bind-mount step

Version 0.1.0 — Singularity / HPC migration
- Added `run_supersynth.py`: argparse-based CLI entry point for standalone/HPC use
- Added `start.sh`: Singularity entrypoint — sets FreeSurfer and CUDA environment, delegates to `run_supersynth.py`
- Added `supersynth.def`: Singularity definition file; bootstraps from `nialljb/fw-supersynth:latest` Docker image
- Added `build_singularity.sh`: build script with fakeroot and post-build test
- Added `build_docker_to_singularity.sh`: alternative build path via Docker daemon conversion
- Added `supersynth_config.json`: HPC scheduler metadata (image path, command template, SLURM defaults)
- Added `run_supersynth_slurm.sh`: SLURM job submission template with GPU allocation (`--gres=gpu:1`, `--nv` passthrough)
- Added `utils/curate_supersynth_output.py`: BIDS output curation with no Flywheel dependency
- Added `CLAUDE.md`: project context and architecture reference for Claude Code
- Added `docs/singularity-migration.md`: step-by-step migration plan
- Removed all Flywheel-specific files (`run.py`, `Dockerfile`, `manifest.json`, `start.sh` legacy, `shared/`, `utils/context.py`, `utils/metadata.py`, `interactive-run.sh`)

19/06/2024
Version 1.0.0 — original Flywheel gear
- Age parsed from session_info, dicom header
- Sex parsed from session_info
- Software version included in the final output
- Input gear version (mrr/gambas) included in the final output
