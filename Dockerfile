# Base image with Python installed
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the lambda-packer requirements and setup files
COPY . /app

# Install the lambda-packer and dependencies
RUN pip install --upgrade pip && \
    pip install .

# Set lambda-packer as the default entrypoint
ENTRYPOINT ["lambda-packer"]
