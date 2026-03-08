#!/usr/bin/env python3
"""
SuperSynth main script for Singularity/SLURM execution.

Replaces the Flywheel-specific run.py with command-line argument parsing
suitable for HPC environments.
"""

import argparse
import logging
import os
import sys
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
        if p.suffix in ('.nii', '.gz'):
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


def extract_subject_session(input_path):
    """
    Extract subject and session identifiers from a BIDS-like path.

    Returns:
        tuple[str, str]: (subject_id, session_id), defaulting to 'unknown'.
    """
    subject_id = "unknown"
    session_id = "unknown"
    for part in Path(input_path).parts:
        if part.startswith('sub-'):
            subject_id = part[4:]
        elif part.startswith('ses-'):
            session_id = part[4:]
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

    # Run mri_super_synth
    cmd = ["mri_super_synth", "--i", *images, "--o", str(work_dir), "--mode", args.mode]
    log.info(f"Running: {' '.join(cmd)}")
    print("-" * 80)

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
