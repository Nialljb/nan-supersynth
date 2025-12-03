"""
Output curation module for SuperSynth gear.
Handles conversion of .mgz files to BIDS-compliant .nii.gz format
and organizes outputs with proper naming conventions.
"""

import json
import logging
import os
import pathlib
import re
import subprocess
import pandas as pd
import sys
from datetime import datetime

# Add shared utilities to path
sys.path.insert(0, '/flywheel/v0/shared/utils')

try:
    import flywheel
    from dateutil import parser
    # Import demographics function from shared utilities
    from curate_output import demo, get_age
    FLYWHEEL_AVAILABLE = True
except ImportError:
    FLYWHEEL_AVAILABLE = False
    logging.warning("Flywheel SDK not available. Demographics will be skipped.")

log = logging.getLogger(__name__)


# FreeSurfer structure names aligned with FreeSurfer Color LUT indices
# Based on FreeSurferColorLUT.txt mapping
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
    Convert MGZ file to NIfTI format using mri_convert.
    
    Args:
        mgz_file (pathlib.Path): Path to input .mgz file
        output_file (pathlib.Path): Path to output .nii.gz file
        
    Returns:
        bool: True if conversion successful, False otherwise
    """
    try:
        cmd = ["mri_convert", str(mgz_file), str(output_file)]
        log.info(f"Converting {mgz_file.name} to {output_file.name}")
        
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            log.info(f"Successfully converted {mgz_file.name}")
            return True
        else:
            log.error(f"Conversion failed for {mgz_file.name}: {result.stderr}")
            return False
            
    except subprocess.CalledProcessError as e:
        log.error(f"Error converting {mgz_file.name}: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"Unexpected error converting {mgz_file.name}: {e}")
        return False


def get_bids_filename(subject_label, session_label, file_type, suffix):
    """
    Generate BIDS-compliant filename.
    
    Args:
        subject_label (str): Subject identifier
        session_label (str): Session identifier
        file_type (str): Type descriptor (e.g., 'T1w', 'T2w', 'FLAIR', 'dseg')
        suffix (str): Additional suffix/descriptor
        
    Returns:
        str: BIDS-formatted filename
    """
    # Clean labels to remove special characters
    sub_clean = re.sub(r'[^a-zA-Z0-9]', '', subject_label)
    ses_clean = re.sub(r'[^a-zA-Z0-9]', '', session_label)
    
    # Build filename components
    filename_parts = [f"sub-{sub_clean}", f"ses-{ses_clean}"]
    
    if suffix:
        suffix_clean = re.sub(r'[^a-zA-Z0-9]', '', suffix)
        filename_parts.append(f"desc-{suffix_clean}")
    
    filename_parts.append(file_type)
    
    return "_".join(filename_parts) + ".nii.gz"


def curate_outputs(context, work_dir, output_dir):
    """
    Curate SuperSynth outputs by converting to BIDS format.
    
    Args:
        context: Flywheel gear context (can be None for testing)
        work_dir (pathlib.Path): Working directory with .mgz outputs
        output_dir (pathlib.Path): Output directory for BIDS-formatted files
        
    Returns:
        bool: True if curation successful, False otherwise
    """
    try:
        log.info("Starting output curation...")
        
        # Get demographics from Flywheel if available
        subject_label = "unknown"
        session_label = "unknown"
        demographics = None
        
        if context and FLYWHEEL_AVAILABLE:
            try:
                log.info("Retrieving demographics from Flywheel...")
                log.info(f"Context type: {type(context)}")
                log.info(f"Context has client: {hasattr(context, 'client')}")
                log.info(f"Context has destination: {hasattr(context, 'destination')}")
                
                # Try to get simple subject/session info first
                if hasattr(context, 'destination') and context.destination:
                    log.info(f"Destination: {context.destination}")
                    
                    # Try simple approach - get from input file path
                    try:
                        input_dir = pathlib.Path('/flywheel/v0/input/input')
                        if input_dir.exists():
                            input_files = list(input_dir.iterdir())
                            log.info(f"Found {len(input_files)} input files")
                    except Exception as e:
                        log.warning(f"Could not list input files: {e}")
                
                # Now try full demographics
                demographics = demo(context)
                subject_label = demographics['subject'].values[0]
                session_label = demographics['session'].values[0]
                log.info(f"Successfully retrieved demographics - Subject: {subject_label}, Session: {session_label}")
                
            except Exception as e:
                log.error(f"Error retrieving demographics: {e}")
                import traceback
                log.error(traceback.format_exc())
                
                # Fallback: try to get from config.json
                try:
                    config_file = pathlib.Path('/flywheel/v0/config.json')
                    if config_file.exists():
                        with open(config_file) as f:
                            config = json.load(f)
                            log.info(f"Config destination: {config.get('destination', {})}")
                except Exception as e2:
                    log.warning(f"Could not read config: {e2}")
                
                log.warning("Using default subject/session labels")
        else:
            log.info("No context available - using default subject/session labels")
        
        # Output files directly to output_dir (flat structure)
        output_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"Saving outputs to: {output_dir}")
        
        # Define file mappings: work_dir filename -> (BIDS type, suffix)
        file_mappings = {
            "SynthT1.mgz": ("T1w", "synth"),
            "SynthT2.mgz": ("T2w", "synth"),
            "SynthFLAIR.mgz": ("FLAIR", "synth"),
            "segmentation.mgz": ("dseg", "supersynth"),
            "input_resampled.mgz": ("T1w", "resampled"),
            "mni_coordinates.mgz": ("T1w", "mnicoordinates"),
            "mni_deformed_affine.mgz": ("T1w", "mnideformedaffine"),
            "mni_deformed_demons.mgz": ("T1w", "mnideformeddemons"),
            "mni_deformed_direct.mgz": ("T1w", "mnideformeddirect"),
            "fakeCortex.mgz": ("T1w", "fakecortex"),
        }
        
        converted_files = []
        
        # Check if we have valid subject/session info
        use_bids_naming = (subject_label != "unknown" and session_label != "unknown")
        
        if not use_bids_naming:
            log.warning("Subject/session are 'unknown' - copying files as-is without BIDS renaming")
        
        # Convert and rename .mgz files
        for source_name, (bids_type, desc_suffix) in file_mappings.items():
            source_file = work_dir / source_name
            
            if source_file.exists():
                if use_bids_naming:
                    # Generate BIDS-compliant filename
                    bids_filename = get_bids_filename(
                        subject_label, 
                        session_label, 
                        bids_type, 
                        desc_suffix
                    )
                    output_file = output_dir / bids_filename
                else:
                    # Just convert to .nii.gz with original name
                    output_file = output_dir / source_name.replace('.mgz', '.nii.gz')
                
                # Convert mgz to nii.gz
                if convert_mgz_to_nii(source_file, output_file):
                    converted_files.append(output_file.name)
                    log.info(f"Converted and saved: {output_file.name}")
                else:
                    log.warning(f"Failed to convert: {source_name}")
            else:
                log.warning(f"Source file not found: {source_name}")
        
        # Copy volumes.csv if it exists
        volumes_csv = work_dir / "volumes.csv"
        if volumes_csv.exists():
            # Read the CSV and process it
            try:
                volumes_data = pd.read_csv(volumes_csv)
                
                # Replace numeric column headers with structure names from FreeSurfer LUT
                # Assuming the CSV has numeric headers (0, 1, 2, ...) or similar
                log.info(f"Original CSV columns: {list(volumes_data.columns)}")
                
                # Check if columns are numeric and map them to structure names
                new_columns = []
                for col in volumes_data.columns:
                    try:
                        # Try to convert column name to integer (FreeSurfer LUT index)
                        lut_index = int(col)
                        if lut_index in FREESURFER_STRUCTURE_NAMES:
                            new_columns.append(FREESURFER_STRUCTURE_NAMES[lut_index])
                            log.info(f"Mapped column {col} -> {FREESURFER_STRUCTURE_NAMES[lut_index]}")
                        else:
                            # Keep original column name if not found in LUT
                            new_columns.append(str(col))
                            log.warning(f"LUT index {lut_index} not found, keeping original column name: {col}")
                    except ValueError:
                        # Column name is not numeric, keep as is
                        new_columns.append(str(col))
                        log.info(f"Non-numeric column name, keeping as is: {col}")
                
                # Apply the new column names
                volumes_data.columns = new_columns
                log.info("Updated column headers with FreeSurfer structure names where possible")
                
                # Add demographics as FIRST columns if available
                if demographics is not None:
                    log.info("Adding demographics as first columns")
                    # Create a new dataframe with demographics first, then volumes
                    demo_cols = {}
                    for col in demographics.columns:
                        demo_cols[col] = demographics[col].values[0]
                    
                    # Create demographics dataframe
                    demo_df = pd.DataFrame([demo_cols])
                    
                    # Concatenate demographics first, then volumes
                    volumes_data = pd.concat([demo_df, volumes_data], axis=1)
                    log.info(f"Added demographics columns: {list(demographics.columns)}")
                
                # Save with appropriate name
                if use_bids_naming:
                    csv_filename = get_bids_filename(
                        subject_label,
                        session_label,
                        "volumes",
                        "supersynth"
                    ).replace(".nii.gz", ".csv")
                else:
                    csv_filename = "volumes.csv"
                
                output_csv = output_dir / csv_filename
                volumes_data.to_csv(output_csv, index=False)
                log.info(f"Saved volumes CSV: {csv_filename}")
                log.info(f"Final CSV columns: {list(volumes_data.columns)}")
                converted_files.append(csv_filename)
                
            except Exception as e:
                log.error(f"Error processing volumes.csv: {e}")
                import traceback
                log.error(traceback.format_exc())
        
        # Create dataset_description.json for BIDS compliance
        dataset_desc = {
            "Name": "SuperSynth Outputs",
            "BIDSVersion": "1.6.0",
            "DatasetType": "derivative",
            "GeneratedBy": [{
                "Name": "SuperSynth",
                "Version": "0.0.8",
                "Container": {
                    "Type": "docker",
                    "Tag": "flywheel/supersynth:0.0.8"
                }
            }],
            "HowToAcknowledge": "Please cite the SuperSynth paper when using these outputs.",
            "SourceDatasets": [{
                "URL": "flywheel://",
                "Version": datetime.now().isoformat()
            }]
        }
        
        dataset_desc_file = output_dir / "dataset_description.json"
        with open(dataset_desc_file, 'w') as f:
            json.dump(dataset_desc, f, indent=2)
        log.info("Created dataset_description.json")
        
        log.info(f"Output curation complete. Converted {len(converted_files)} files.")
        log.info(f"Files saved to: {output_dir}")
        
        return True
        
    except Exception as e:
        log.error(f"Error during output curation: {e}")
        import traceback
        log.error(traceback.format_exc())
        return False


def main():
    """Main entry point for testing."""
    logging.basicConfig(level=logging.INFO)
    
    # This would normally come from the gear context
    work_dir = pathlib.Path("/flywheel/v0/work")
    output_dir = pathlib.Path("/flywheel/v0/output")
    
    # For testing, you'd need to set up the context
    # curate_outputs(context, work_dir, output_dir)
    

if __name__ == "__main__":
    main()
