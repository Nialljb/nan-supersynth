"""
Output curation module for SuperSynth.
Converts .mgz files to BIDS-compliant .nii.gz and organises outputs with
appropriate naming conventions.  No Flywheel SDK dependency.
"""

import json
import logging
import pathlib
import re
import subprocess
from datetime import datetime

import pandas as pd

log = logging.getLogger(__name__)


# FreeSurfer structure names aligned with FreeSurfer Color LUT indices
FREESURFER_STRUCTURE_NAMES = {
    0: "Unknown",
    1: "Left-Cerebral-Exterior",
    2: "Left-Cerebral-White-Matter",
    3: "Left-Cerebral-Cortex",
    4: "Left-Lateral-Ventricle",
    5: "Left-Inf-Lat-Vent",
    6: "Left-Cerebellum-Exterior",
    7: "Left-Cerebellum-White-Matter",
    8: "Left-Cerebellum-Cortex",
    9: "Left-Thalamus-unused",
    10: "Left-Thalamus",
    11: "Left-Caudate",
    12: "Left-Putamen",
    13: "Left-Pallidum",
    14: "3rd-Ventricle",
    15: "4th-Ventricle",
    16: "Brain-Stem",
    17: "Left-Hippocampus",
    18: "Left-Amygdala",
    19: "Left-Insula",
    20: "Left-Operculum",
    21: "Line-1",
    22: "Line-2",
    23: "Line-3",
    24: "CSF",
    25: "Left-Lesion",
    26: "Left-Accumbens-area",
    27: "Left-Substancia-Nigra",
    28: "Left-VentralDC",
    29: "Left-undetermined",
    30: "Left-vessel",
    31: "Left-choroid-plexus",
    32: "Left-F3orb",
    33: "Left-aOg",
    34: "Left-WMCrowns",
    35: "Left-mOg",
    36: "Left-pOg",
    37: "Left-Stellate",
    38: "Left-Porg",
    39: "Left-Aorg",
    40: "Right-Cerebral-Exterior",
    41: "Right-Cerebral-White-Matter",
    42: "Right-Cerebral-Cortex",
    43: "Right-Lateral-Ventricle",
    44: "Right-Inf-Lat-Vent",
    45: "Right-Cerebellum-Exterior",
    46: "Right-Cerebellum-White-Matter",
    47: "Right-Cerebellum-Cortex",
    48: "Right-Thalamus-unused",
    49: "Right-Thalamus",
    50: "Right-Caudate",
    51: "Right-Putamen",
    52: "Right-Pallidum",
    53: "Right-Hippocampus",
    54: "Right-Amygdala",
    55: "Right-Insula",
    56: "Right-Operculum",
    57: "Right-Lesion",
    58: "Right-Accumbens-area",
    59: "Right-Substancia-Nigra",
    60: "Right-VentralDC",
    61: "Right-undetermined",
    62: "Right-vessel",
    63: "Right-choroid-plexus",
    64: "Right-F3orb",
    65: "Right-lOg",
    66: "Right-WMCrowns",
    67: "Right-mOg",
    68: "Right-pOg",
    69: "Right-Stellate",
    70: "Right-Porg",
    71: "Right-Aorg",
    72: "5th-Ventricle",
    73: "Left-Interior",
    74: "Right-Interior",
    75: "Left-Locus-Coeruleus",
    76: "Right-Locus-Coeruleus",
    77: "WM-hypointensities",
    78: "Left-WM-hypointensities",
    79: "Right-WM-hypointensities",
    80: "non-WM-hypointensities",
    81: "Left-non-WM-hypointensities",
    82: "Right-non-WM-hypointensities",
    83: "Left-F1",
    84: "Right-F1",
    85: "Optic-Chiasm",
    819: "Left-HypoThal-noMB",
    820: "Right-HypoThal-noMB",
    821: "Left-Fornix",
    822: "Right-Fornix",
    843: "Left-MammillaryBody",
    844: "Right-MammillaryBody",
    853: "Mid-AntCom",
    865: "Left-Basal-Forebrain",
    866: "Right-Basal-Forebrain",
    869: "Left-SeptalNuc",
    870: "Right-SeptalNuc",
}


def convert_mgz_to_nii(mgz_file, output_file):
    """
    Convert an MGZ file to NIfTI format using mri_convert.

    Args:
        mgz_file (pathlib.Path): Path to input .mgz file.
        output_file (pathlib.Path): Path to output .nii.gz file.

    Returns:
        bool: True if conversion succeeded.
    """
    try:
        cmd = ["mri_convert", str(mgz_file), str(output_file)]
        log.info(f"Converting {mgz_file.name} -> {output_file.name}")
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"Conversion failed for {mgz_file.name}: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"Unexpected error converting {mgz_file.name}: {e}")
        return False


def get_bids_filename(subject_label, session_label, file_type, suffix):
    """
    Generate a BIDS-compliant filename.

    Args:
        subject_label (str): Subject identifier.
        session_label (str): Session identifier.
        file_type (str): BIDS suffix (e.g. 'T1w', 'dseg').
        suffix (str): desc- value (e.g. 'synth').

    Returns:
        str: BIDS-formatted filename ending in .nii.gz
    """
    sub_clean = re.sub(r'[^a-zA-Z0-9]', '', subject_label)
    ses_clean = re.sub(r'[^a-zA-Z0-9]', '', session_label)
    parts = [f"sub-{sub_clean}", f"ses-{ses_clean}"]
    if suffix:
        parts.append(f"desc-{re.sub(r'[^a-zA-Z0-9]', '', suffix)}")
    parts.append(file_type)
    return "_".join(parts) + ".nii.gz"


def curate_outputs(work_dir, output_dir, subject_label="unknown", session_label="unknown"):
    """
    Curate SuperSynth outputs: convert .mgz to .nii.gz with BIDS naming.

    Args:
        work_dir (pathlib.Path): Directory containing mri_super_synth .mgz outputs.
        output_dir (pathlib.Path): Destination directory for curated files.
        subject_label (str): Subject identifier (used in BIDS filenames).
        session_label (str): Session identifier (used in BIDS filenames).

    Returns:
        bool: True if curation succeeded.
    """
    try:
        log.info("Starting output curation...")
        output_dir.mkdir(parents=True, exist_ok=True)

        use_bids_naming = (subject_label != "unknown" and session_label != "unknown")
        if not use_bids_naming:
            log.warning("Subject/session unknown — outputs will not be BIDS-renamed.")

        file_mappings = {
            "SynthT1.mgz":               ("T1w",   "synth"),
            "SynthT2.mgz":               ("T2w",   "synth"),
            "SynthFLAIR.mgz":            ("FLAIR",  "synth"),
            "segmentation.mgz":          ("dseg",   "supersynth"),
            "input_resampled.mgz":       ("T1w",   "resampled"),
            "mni_coordinates.mgz":       ("T1w",   "mnicoordinates"),
            "mni_deformed_affine.mgz":   ("T1w",   "mnideformedaffine"),
            "mni_deformed_demons.mgz":   ("T1w",   "mnideformeddemons"),
            "mni_deformed_direct.mgz":   ("T1w",   "mnideformeddirect"),
            "fakeCortex.mgz":            ("T1w",   "fakecortex"),
        }

        converted_files = []

        for source_name, (bids_type, desc_suffix) in file_mappings.items():
            source_file = work_dir / source_name
            if not source_file.exists():
                log.warning(f"Source file not found: {source_name}")
                continue

            if use_bids_naming:
                output_file = output_dir / get_bids_filename(
                    subject_label, session_label, bids_type, desc_suffix
                )
            else:
                output_file = output_dir / source_name.replace('.mgz', '.nii.gz')

            if convert_mgz_to_nii(source_file, output_file):
                converted_files.append(output_file.name)
            else:
                log.warning(f"Failed to convert: {source_name}")

        # Process volumes.csv
        volumes_csv = work_dir / "volumes.csv"
        if volumes_csv.exists():
            try:
                volumes_data = pd.read_csv(volumes_csv)
                log.info(f"Original CSV columns: {list(volumes_data.columns)}")

                new_columns = []
                for col in volumes_data.columns:
                    try:
                        lut_index = int(col)
                        new_columns.append(
                            FREESURFER_STRUCTURE_NAMES.get(lut_index, str(col))
                        )
                    except ValueError:
                        new_columns.append(str(col))
                volumes_data.columns = new_columns

                if use_bids_naming:
                    csv_filename = get_bids_filename(
                        subject_label, session_label, "volumes", "supersynth"
                    ).replace(".nii.gz", ".csv")
                else:
                    csv_filename = "volumes.csv"

                output_csv = output_dir / csv_filename
                volumes_data.to_csv(output_csv, index=False)
                converted_files.append(csv_filename)
                log.info(f"Saved volumes CSV: {csv_filename}")

            except Exception as e:
                log.error(f"Error processing volumes.csv: {e}")
                import traceback
                log.error(traceback.format_exc())

        # dataset_description.json
        dataset_desc = {
            "Name": "SuperSynth Outputs",
            "BIDSVersion": "1.6.0",
            "DatasetType": "derivative",
            "GeneratedBy": [{"Name": "SuperSynth"}],
            "HowToAcknowledge": "Please cite the SuperSynth paper when using these outputs.",
            "SourceDatasets": [{"Version": datetime.now().isoformat()}],
        }
        with open(output_dir / "dataset_description.json", 'w') as f:
            json.dump(dataset_desc, f, indent=2)
        log.info("Created dataset_description.json")

        log.info(f"Curation complete. {len(converted_files)} file(s) saved to: {output_dir}")
        return True

    except Exception as e:
        log.error(f"Error during output curation: {e}")
        import traceback
        log.error(traceback.format_exc())
        return False
