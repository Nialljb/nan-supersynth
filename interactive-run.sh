#!/usr/bin/env bash 

GEAR=fw-supersynth
IMAGE=flywheel/supersynth:0.0.10
LOG=supersynth-0.0.10-692dfbd6de9f4d44b9b9bfff
user=/Users/nbourke/GD/atom/

# Command:
docker run -it --rm --entrypoint bash\
	-v $user/unity/fw-gears/${GEAR}/run.py:/flywheel/v0/run.py\
	-v $user/unity/fw-gears/${GEAR}/${LOG}/input:/flywheel/v0/input\
	-v $user/unity/fw-gears/${GEAR}/${LOG}/output:/flywheel/v0/output\
	-v $user/unity/fw-gears/${GEAR}/${LOG}/work:/flywheel/v0/work\
	-v $user/unity/fw-gears/${GEAR}/${LOG}/config.json:/flywheel/v0/config.json\
	-v $user/unity/fw-gears/${GEAR}/utils:/flywheel/v0/utils\
	$IMAGE
