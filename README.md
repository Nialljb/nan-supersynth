# SuperSynth Flywheel Gear

A Flywheel gear for running FreeSurfer's SuperSynth tool, which generates synthetic MRI contrasts from structural brain images.

## Overview

SuperSynth uses deep learning to synthesize multiple MRI contrasts from a single input scan, enabling enhanced brain imaging analysis when multiple sequences are not available.

## Requirements

### ⚠️ CRITICAL: GPU Configuration

**When running this gear on Flywheel, you MUST add the `gpuplus` tag to ensure sufficient GPU memory allocation.**

Without the `gpuplus` tag, the job will fail with exit code 137 (killed due to insufficient memory). The gear requires approximately 16GB+ of GPU memory to run successfully.

## Inputs

- **input**: NIfTI image file (`.nii` or `.nii.gz`) - typically a T1-weighted MRI scan or an isotropic reconstruction from a multi-contrast acquisition.

## Configuration

- **mode**: Processing mode (default: `invivo`)

## Outputs

The gear generates synthetic MRI contrasts in BIDS format, curated with appropriate metadata from the source acquisition.

## Usage Notes

- Requires CUDA-compatible GPU with sufficient VRAM
- Processing time varies based on input image size (typically 1-3 minutes)
- Output files are automatically organized in BIDS structure

