FROM docker:27-cli AS docker-cli

FROM python:3.12-slim

WORKDIR /app

# lambda-packer shells out to `docker buildx build`, so the published
# container image needs both the Docker CLI and the buildx plugin available.
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins

COPY . /app

RUN pip install --upgrade pip && \
    pip install .

CMD ["lambda-packer"]
