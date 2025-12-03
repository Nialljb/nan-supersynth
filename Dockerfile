FROM nialljb/fw-supersynth:latest

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh

# Set up environment variables
ENV CONDA_DIR=/opt/conda
ENV PATH="${CONDA_DIR}/bin:${PATH}"
ENV FSL_CONDA_CHANNEL="https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/public"

# Accept Anaconda Terms of Service
RUN /opt/conda/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    /opt/conda/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Install tini and FSL packages
RUN /opt/conda/bin/conda install -n base -y -c conda-forge tini && \
    /opt/conda/bin/conda install -n base -y -c ${FSL_CONDA_CHANNEL} -c conda-forge fsl-base fsl-utils fsl-avwutils

# Define FSLDIR
ENV FSLDIR=/opt/conda

# Install PyTorch (without torchaudio, which isn't available for Python 3.13)
RUN /opt/conda/bin/pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install Flywheel packages
RUN /opt/conda/bin/pip install --no-cache-dir \
    flywheel-gear-toolkit \
    flywheel-sdk \
    jsonschema \
    pandas

# Setup environment for Docker image
ENV HOME=/root/
ENV FLYWHEEL="/flywheel/v0"
WORKDIR $FLYWHEEL
RUN mkdir -p $FLYWHEEL/input

COPY ./ $FLYWHEEL/

# Configure entrypoint
ENTRYPOINT ["bash", "/flywheel/v0/start.sh"]