# Changelog

06/03/2026
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
