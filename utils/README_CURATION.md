# SuperSynth Output Curation

This module handles the conversion and organization of SuperSynth outputs into BIDS-compliant format.

## Overview

The `utils/curate_supersynth_output.py` module processes the SuperSynth working directory outputs and converts them to BIDS format with proper naming conventions and directory structure.

## What it does

1. **Converts .mgz to .nii.gz**: All MGZ files from the working directory are converted to NIfTI format using FreeSurfer's `mri_convert`
2. **BIDS Naming (when available)**: If subject/session information is successfully retrieved from Flywheel, outputs use BIDS-compliant naming conventions:
   ```
   /flywheel/v0/output/
   ├── sub-<subject>_ses-<session>_desc-synth_T1w.nii.gz
   ├── sub-<subject>_ses-<session>_desc-synth_T2w.nii.gz
   ├── sub-<subject>_ses-<session>_desc-synth_FLAIR.nii.gz
   ├── sub-<subject>_ses-<session>_desc-supersynth_dseg.nii.gz
   ├── ... (other derived images)
   ├── sub-<subject>_ses-<session>_desc-supersynth_volumes.csv
   └── dataset_description.json
   ```
3. **Fallback Naming**: If subject/session cannot be retrieved, files are copied with original names converted to .nii.gz:
   ```
   /flywheel/v0/output/
   ├── SynthT1.nii.gz
   ├── SynthT2.nii.gz
   ├── SynthFLAIR.nii.gz
   ├── segmentation.nii.gz
   ├── ... (other derived images)
   ├── volumes.csv
   └── dataset_description.json
   ```
4. **Demographics Integration**: When available, retrieves subject/session information from Flywheel and adds demographics to the volumes CSV
5. **BIDS Metadata**: Creates a `dataset_description.json` file for BIDS compliance

## File Mappings

The following files from the work directory are converted and renamed:

| Work Directory File | BIDS Output (with demographics) | Fallback Output (without demographics) |
|---------------------|-------------|-------------|
| `SynthT1.mgz` | `sub-X_ses-Y_desc-synth_T1w.nii.gz` | `SynthT1.nii.gz` |
| `SynthT2.mgz` | `sub-X_ses-Y_desc-synth_T2w.nii.gz` | `SynthT2.nii.gz` |
| `SynthFLAIR.mgz` | `sub-X_ses-Y_desc-synth_FLAIR.nii.gz` | `SynthFLAIR.nii.gz` |
| `segmentation.mgz` | `sub-X_ses-Y_desc-supersynth_dseg.nii.gz` | `segmentation.nii.gz` |
| `input_resampled.mgz` | `sub-X_ses-Y_desc-resampled_T1w.nii.gz` | `input_resampled.nii.gz` |
| `mni_coordinates.mgz` | `sub-X_ses-Y_desc-mnicoordinates_T1w.nii.gz` | `mni_coordinates.nii.gz` |
| `mni_deformed_affine.mgz` | `sub-X_ses-Y_desc-mnideformedaffine_T1w.nii.gz` | `mni_deformed_affine.nii.gz` |
| `mni_deformed_demons.mgz` | `sub-X_ses-Y_desc-mnideformeddemons_T1w.nii.gz` | `mni_deformed_demons.nii.gz` |
| `mni_deformed_direct.mgz` | `sub-X_ses-Y_desc-mnideformeddirect_T1w.nii.gz` | `mni_deformed_direct.nii.gz` |
| `fakeCortex.mgz` | `sub-X_ses-Y_desc-fakecortex_T1w.nii.gz` | `fakeCortex.nii.gz` |
| `volumes.csv` | `sub-X_ses-Y_desc-supersynth_volumes.csv` | `volumes.csv` |

## Integration with run.py

The `run.py` script has been updated to:

1. Initialize the Flywheel gear context for demographics retrieval
2. Execute SuperSynth as before
3. Call `curate_outputs()` after successful SuperSynth execution
4. Handle errors gracefully - if curation fails, the gear continues but logs warnings

## Dependencies

- FreeSurfer (for `mri_convert`)
- Flywheel SDK (for demographics)
- pandas
- Python standard library

## Usage

The curation runs automatically as part of the gear execution. No configuration needed.

If running in a local testing environment without Flywheel:
- The module will use default "unknown" labels for subject/session
- Demographics will be skipped but files will still be converted and organized

## Testing

To test conversion inside the container:

```bash
# Simple test without context (uses fallback naming - converts files with original names)
python -c "
import pathlib
import sys
sys.path.insert(0, '/flywheel/v0')

from utils.curate_supersynth_output import curate_outputs

work_dir = pathlib.Path('/flywheel/v0/work')
output_dir = pathlib.Path('/flywheel/v0/output')
curate_outputs(None, work_dir, output_dir)
"
```

To test locally with sample data:

```bash
cd /Users/nbourke/GD/atom/unity/fw-gears/fw-supersynth
# Ensure FreeSurfer is available
export FREESURFER_HOME=/usr/local/freesurfer
source $FREESURFER_HOME/SetUpFreeSurfer.sh

# Test conversion with sample data
python -c "
import pathlib
from utils.curate_supersynth_output import curate_outputs

work_dir = pathlib.Path('supersynth-0.0.7-6927617cde9f4d44b9b9b6a4/work')
output_dir = pathlib.Path('test_output')
curate_outputs(None, work_dir, output_dir)
"
```

**Note**: The context initialization and demographics retrieval happens automatically when running through `run.py`. Manual testing with context is not recommended due to complex dependencies.

## Notes

- The curation process is non-destructive - original files in the work directory are preserved
- **Smart fallback**: If demographics can't be retrieved (subject/session = "unknown"), files are simply converted and copied with original names (e.g., `SynthT1.nii.gz` instead of BIDS naming)
- All .mgz files are converted to .nii.gz for compatibility with standard neuroimaging tools
- Output files are saved directly to `/flywheel/v0/output` (flat structure, no subdirectories)
- BIDS naming is applied to filenames only when valid subject/session info is available

## Troubleshooting

If you see "sub-unknown_ses-unknown" in output filenames:

1. **Check API Key**: Ensure the `api-key` input is properly configured in the gear
2. **Check Logs**: Look for detailed error messages in the gear logs starting with "Error retrieving demographics"
3. **Context Initialization**: Verify the GearToolkitContext is initializing correctly (check logs for "Context initialized successfully")
4. **Destination**: Ensure the gear is running as an analysis (not standalone) so it has access to session/subject metadata

The demographics retrieval requires:
- Valid Flywheel API key passed as input
- Gear running in analysis context (attached to a session)
- Access to parent session and subject containers





python -c "
import pathlib
import sys
sys.path.insert(0, '/flywheel/v0')
sys.path.insert(0, '/flywheel/v0/utils')

from flywheel_gear_toolkit import GearToolkitContext
from utils.curate_supersynth_output import curate_outputs

context = GearToolkitContext()
work_dir = pathlib.Path('/flywheel/v0/work')
output_dir = pathlib.Path('/flywheel/v0/output')
curate_outputs(context, work_dir, output_dir)
"