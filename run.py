#!/usr/bin/env python3
import json
import subprocess
import pathlib
import sys
import logging

# Add utils to path for imports
sys.path.append('/flywheel/v0')
sys.path.append('/flywheel/v0/shared/utils')

from flywheel_gear_toolkit import GearToolkitContext
from utils.curate_supersynth_output import curate_outputs

INPUT_DIR = pathlib.Path("/flywheel/v0/input")
OUTPUT_DIR = pathlib.Path("/flywheel/v0/output")
WORK_DIR = pathlib.Path("/flywheel/v0/work")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

def main():

    # ------------------------------------------------------------------
    # 1. Load Flywheel gear config
    # ------------------------------------------------------------------
    config_file = pathlib.Path("/flywheel/v0/config.json")
    if not config_file.exists():
        raise RuntimeError("No config.json found in /flywheel/v0")

    with open(config_file, "r") as f:
        config = json.load(f)

    # Initialize Flywheel context for demographics
    log.info("Initializing Flywheel gear context...")
    try:
        context = GearToolkitContext()
        log.info(f"Context initialized successfully")
        log.info(f"Context client: {hasattr(context, 'client')}")
        log.info(f"Context destination: {getattr(context, 'destination', None)}")
    except Exception as e:
        log.warning(f"Could not initialize full context: {e}")
        import traceback
        log.warning(traceback.format_exc())
        context = None

    # ------------------------------------------------------------------
    # 2. Identify all input images
    # ------------------------------------------------------------------
    images = sorted([str(p) for p in INPUT_DIR.glob("**/*.nii*")])
    if not images:
        raise RuntimeError("No NIfTI images found in /flywheel/v0/input")
    log.info(f"Found {len(images)} input image(s): {images}")
    
    # ------------------------------------------------------------------
    # 3. Ensure output directory exists
    # ------------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 4. Call SuperSynth
    # ------------------------------------------------------------------
    log.info("Executing SuperSynth...")
    
    # Define the command
    cmd = [
        "mri_super_synth",
        "--i", *images,
        "--o", str(WORK_DIR),
        "--mode", "invivo"
    ]
    
    log.info(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        print("-" * 80)
        log.info("SuperSynth command completed successfully!")

    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr, file=sys.stderr)
        log.error(f"SuperSynth failed with exit code {e.returncode}")
        return e.returncode

    except Exception as e:
        log.error(f"Unexpected error running SuperSynth: {e}")
        return 1

    # ------------------------------------------------------------------
    # 5. Curate outputs to BIDS format
    # ------------------------------------------------------------------
    log.info("Curating outputs to BIDS format...")
    
    try:
        if context:
            success = curate_outputs(context, WORK_DIR, OUTPUT_DIR)
            if success:
                log.info("Output curation completed successfully!")
            else:
                log.warning("Output curation completed with warnings")
        else:
            log.warning("Skipping output curation - no Flywheel context available")
            log.info("Copying raw outputs to output directory...")
            # Fallback: just copy the files without BIDS structure
            import shutil
            for file in WORK_DIR.glob("*"):
                if file.is_file():
                    shutil.copy2(file, OUTPUT_DIR / file.name)
                    
    except Exception as e:
        log.error(f"Error during output curation: {e}")
        import traceback
        log.error(traceback.format_exc())
        # Don't fail the gear if curation fails
        log.warning("Continuing despite curation error...")
    
    return 0

    
if __name__ == "__main__":
    main()
