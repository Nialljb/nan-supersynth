#!/usr/bin/env python3
"""
SuperSynth main script for Singularity/SLURM execution.

Replaces the Flywheel-specific run.py with command-line argument parsing
suitable for HPC environments.
"""

import argparse
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
import subprocess

log = logging.getLogger(__name__)


def setup_logging(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def find_input_files(input_path):
    """
    Find all NIfTI files under input_path (file or directory).

    Returns:
        list[str]: Absolute paths to .nii / .nii.gz files.
    """
    p = Path(input_path)
    if p.is_file():
        if p.name.endswith('.nii') or p.name.endswith('.nii.gz'):
            return [str(p)]
        raise ValueError(f"Input file does not appear to be NIfTI: {input_path}")
    if p.is_dir():
        files = sorted(
            str(f) for f in p.rglob('*')
            if f.name.endswith('.nii') or f.name.endswith('.nii.gz')
        )
        if not files:
            raise RuntimeError(f"No NIfTI files found under: {input_path}")
        return files
    raise FileNotFoundError(f"Input path not found: {input_path}")


# Known BIDS entity keys used as delimiters when parsing values from filenames.
_BIDS_KEYS = (
    'sub', 'ses', 'task', 'acq', 'ce', 'run', 'echo', 'dir', 'part',
    'rec', 'space', 'res', 'den', 'label', 'desc', 'split', 'hemi', 'chunk',
)
_BIDS_KEY_PATTERN = '|'.join(_BIDS_KEYS)


def extract_subject_session(input_path):
    """
    Extract subject and session identifiers from a BIDS-like path.

    Checks directory components first (canonical BIDS layout), then falls back
    to parsing the filename itself for embedded sub-/ses- entities (e.g.
    filenames produced by Flywheel that encode subject/session in the name).

    Returns:
        tuple[str, str]: (subject_id, session_id), defaulting to 'unknown'.
    """
    subject_id = "unknown"
    session_id = "unknown"

    # 1. Walk directory parts — handles standard BIDS folder layout.
    for part in Path(input_path).parts:
        if part.startswith('sub-') and '.' not in part:
            subject_id = part[4:]
        elif part.startswith('ses-') and '.' not in part:
            session_id = part[4:]

    # 2. Fall back to parsing the filename stem when entities are embedded
    #    in the filename (e.g. sub-01_ses-01_T2w.nii.gz).
    if subject_id == "unknown" or session_id == "unknown":
        stem = Path(input_path).name
        for ext in ('.nii.gz', '.nii', '.mgz'):
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
                break
        # Values run from the entity key up to the next recognised key or end.
        _delim = rf'_(?:{_BIDS_KEY_PATTERN})-'
        if subject_id == "unknown":
            m = re.search(rf'(?:^|_)sub-(.+?)(?:{_delim}|$)', stem)
            if m:
                subject_id = m.group(1)
        if session_id == "unknown":
            m = re.search(rf'(?:^|_)ses-(.+?)(?:{_delim}|$)', stem)
            if m:
                session_id = m.group(1)

    return subject_id, session_id


def main():
    parser = argparse.ArgumentParser(
        description="SuperSynth: deep learning MRI contrast synthesis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  singularity exec --nv supersynth.sif python /app/run_supersynth.py \\
      --input /data/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz \\
      --output /results

  singularity exec --nv supersynth.sif python /app/run_supersynth.py \\
      --input /data/sub-01/ses-01/anat \\
      --output /results \\
      --subject 01 --session 01
        """
    )

    parser.add_argument(
        '--input',
        required=True,
        help='Input NIfTI file or directory containing NIfTI file(s)'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output directory for results'
    )
    parser.add_argument(
        '--work-dir',
        default='/tmp/supersynth_work',
        help='Working directory for intermediate files (default: /tmp/supersynth_work)'
    )
    parser.add_argument(
        '--subject',
        help='Subject identifier (auto-detected from BIDS path if not provided)'
    )
    parser.add_argument(
        '--session',
        help='Session identifier (auto-detected from BIDS path if not provided)'
    )
    parser.add_argument(
        '--mode',
        default='invivo',
        choices=['invivo', 'exvivo'],
        help='SuperSynth processing mode (default: invivo)'
    )
    parser.add_argument(
        '--no-test-time-flipping',
        action='store_true',
        dest='no_test_time_flipping',
        help='Disable test-time flipping in mri_super_synth. Reduces GPU memory '
             'usage by ~50%% at a small cost to accuracy. Use on GPUs with <16 GB '
             'VRAM when the default run fails with CUDA out-of-memory.'
    )
    parser.add_argument(
        '--tile-size',
        type=int,
        default=None,
        dest='tile_size',
        metavar='N',
        help='Override the GPU tile size used by inference.py (default: 160). '
             'Reducing this lowers peak GPU memory: try 128 (~51%% of 160³ memory) '
             'or 96 (~22%%). Use when CUDA OOM errors persist after --no-test-time-flipping.'
    )
    parser.add_argument(
        '--extra-args',
        nargs=argparse.REMAINDER,
        default=[],
        help='Extra arguments passed verbatim to inference.py (e.g. --threads 4)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()
    setup_logging(args.debug)

    log.info("Starting SuperSynth processing...")
    log.info(f"Input:    {args.input}")
    log.info(f"Output:   {args.output}")
    log.info(f"Work dir: {args.work_dir}")
    log.info(f"Mode:     {args.mode}")

    # Locate input files
    images = find_input_files(args.input)
    log.info(f"Found {len(images)} input image(s): {images}")

    # Resolve subject / session
    auto_subject, auto_session = extract_subject_session(args.input)
    subject = args.subject or auto_subject
    session = args.session or auto_session
    log.info(f"Subject: {subject}, Session: {session}")

    # Prepare directories
    work_dir = Path(args.work_dir)
    output_dir = Path(args.output)
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build the inference command.
    # We call inference.py via fspython directly rather than through the
    # mri_super_synth wrapper, because the wrapper unconditionally appends
    # --test_time_flipping with no way to suppress it.
    freesurfer_home = os.environ.get("FREESURFER_HOME", "/usr/local/freesurfer/7-dev")
    inference_script = Path(freesurfer_home) / "python/packages/SuperSynth/scripts/inference.py"
    model_file = Path(freesurfer_home) / "models/SuperSynth_August_2025.pth"

    if not inference_script.exists():
        log.error(f"SuperSynth inference script not found: {inference_script}")
        sys.exit(1)
    if not model_file.exists():
        log.error(f"SuperSynth model file not found: {model_file}")
        sys.exit(1)

    # Optionally patch tile_size in inference.py without modifying the container.
    # inference.py hardcodes `tile_size = 160` on GPU with no CLI knob.
    # We copy it to a tmpdir, sed-substitute the value, and run the copy.
    if args.tile_size is not None:
        src = inference_script.read_text()
        # Replace the GPU tile_size assignment (line: `        tile_size = 160`)
        patched = re.sub(
            r'(^\s*tile_size\s*=\s*)160(\s*$)',
            rf'\g<1>{args.tile_size}\2',
            src,
            flags=re.MULTILINE,
        )
        if patched == src:
            log.warning("Could not locate 'tile_size = 160' in inference.py — tile-size override ignored.")
        else:
            # inference.py resolves atlas via:
            #   os.path.dirname(os.path.abspath(__file__)) + '/../atlas/'
            # So we mirror the original package tree in a tmpdir:
            #   <tmpdir>/scripts/inference.py   ← patched script
            #   <tmpdir>/atlas                  ← symlink to real atlas dir
            tmp_base = Path(tempfile.mkdtemp(prefix='supersynth_'))
            tmp_scripts_dir = tmp_base / 'scripts'
            tmp_scripts_dir.mkdir()
            tmp_script = tmp_scripts_dir / 'inference.py'
            tmp_script.write_text(patched)
            real_atlas = Path(freesurfer_home) / 'python/packages/SuperSynth/atlas'
            (tmp_base / 'atlas').symlink_to(real_atlas)
            inference_script = tmp_script
            log.info(f"Tile size patched to {args.tile_size} (script: {inference_script})")

    cmd = [
        "fspython", str(inference_script),
        "--i", *images,
        "--o", str(work_dir),
        "--mode", args.mode,
        "--model_file", str(model_file),
    ]
    if not args.no_test_time_flipping:
        cmd.append("--test_time_flipping")
    else:
        log.info("Test-time flipping disabled — reduced GPU memory usage")
    if args.extra_args:
        cmd.extend(args.extra_args)
        log.info(f"Extra inference args: {args.extra_args}")
    log.info(f"Running: {' '.join(cmd)}")
    print("-" * 80)
    print("Running command:")
    print(' '.join(cmd))

    try:
        result = subprocess.run(cmd, check=True, text=True)
    except subprocess.CalledProcessError as e:
        log.error(f"mri_super_synth failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        log.error(f"Unexpected error running mri_super_synth: {e}")
        sys.exit(1)

    print("-" * 80)
    log.info("mri_super_synth completed successfully.")

    # Curate outputs
    log.info("Curating outputs to BIDS format...")
    sys.path.insert(0, str(Path(__file__).parent))
    from utils.curate_supersynth_output import curate_outputs

    try:
        success = curate_outputs(work_dir, output_dir, subject, session)
        if success:
            log.info("Output curation completed successfully.")
        else:
            log.warning("Output curation completed with warnings.")
    except Exception as e:
        log.error(f"Error during output curation: {e}")
        import traceback
        log.error(traceback.format_exc())
        log.warning("Continuing despite curation error.")

    log.info(f"Done. Results in: {output_dir}")


if __name__ == "__main__":
    main()
