FROM nvidia/cuda:11.6.2-cudnn8-runtime-ubuntu20.04

# Declare ENV variables
ENV TZ=Etc/UTC

# Set timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install system dependencies
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y libgl1-mesa-glx
RUN apt-get install -y python3-pip
RUN apt-get install -y python3-dev
RUN apt-get install -y libglib2.0-0

# Set working directory
WORKDIR /ImageServer

# Combine pip install commands
COPY requirements.txt requirements.txt
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install diffusers --upgrade invisible_watermark transformers accelerate safetensors
RUN python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu117
RUN python3 -m pip install python-dotenv
RUN python3 -m pip install xformers -U
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy necessary files only, use .dockerignore for excluding unnecessary files
COPY cache/ cache/
COPY generative-models/ generative-models/
COPY src/ src/
COPY .env .env

# Run the server
CMD ["python3", "src/run.py"]
