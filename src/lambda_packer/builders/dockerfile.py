"""Dockerfile generation logic for multi-stage BuildKit builds."""

from __future__ import annotations

from typing import List, Optional

from jinja2 import Template

# The core "compiler" template.
# It uses multi-stage builds to:
# 1. Build each layer in isolation (optimized for caching).
# 2. Build the main lambda and merge the layers.
# 3. Export to either a runnable OCI image or a flat filesystem (for ZIP).
DOCKERFILE_TEMPLATE = """
# syntax=docker/dockerfile:1.4
{% for layer_name in layers %}
FROM python:{{ runtime_version }}-slim AS layer-{{ layer_name }}
WORKDIR /asset/python
{% if layer_requirements[layer_name] %}
COPY layer_{{ layer_name }}_requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \\
    pip install -r /tmp/requirements.txt -t .
{% endif %}
COPY layer_{{ layer_name }}/ .
{% endfor %}

FROM python:{{ runtime_version }}-slim AS builder
WORKDIR /asset
{% if requirements %}
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \\
    pip install -r /tmp/requirements.txt -t .
{% endif %}
COPY src/ .

# Merge layers: We copy the contents of /asset/python (site-packages + code)
# directly into the lambda root so they are importable without PYTHONPATH tweaks.
{% for layer_name in layers %}
COPY --from=layer-{{ layer_name }} /asset/python/ .
{% endfor %}

# Final stage
{% if is_image %}
# For OCI images, we use the official AWS Lambda base image to ensure it's runnable.
FROM public.ecr.aws/lambda/python:{{ runtime_version }}
WORKDIR ${LAMBDA_TASK_ROOT}
COPY --from=builder /asset .
{% if handler %}
# Standard AWS Lambda entrypoint requires the handler as the first CMD argument.
ENTRYPOINT [ "/lambda-entrypoint.sh" ]
CMD [ "{{ handler }}" ]
{% endif %}
{% else %}
# For ZIP exports, we use scratch to produce the smallest possible filesystem export.
FROM scratch
COPY --from=builder /asset /
{% endif %}
"""


class DockerfileGenerator:
    """Generates a Dockerfile based on the component type and requirements."""

    def __init__(self, template: Optional[str] = None):
        self.template = Template(template or DOCKERFILE_TEMPLATE)

    def generate(
        self,
        runtime: str,
        requirements: bool = False,
        layers: Optional[List[str]] = None,
        layer_requirements: Optional[dict[str, bool]] = None,
        is_image: bool = False,
        handler: Optional[str] = None,
    ) -> str:
        """
        Renders the Dockerfile template.
        
        Args:
            runtime: Python runtime (e.g., 'python3.12').
            requirements: Whether the Lambda has a requirements.txt.
            layers: List of layer names to include.
            layer_requirements: Map of layer names to a boolean indicating if they have requirements.
            is_image: Whether to produce a runnable OCI image.
            handler: The Lambda handler name (required if is_image is True).
        """
        return self.template.render(
            runtime_version=runtime.replace("python", ""),
            requirements=requirements,
            layers=layers or [],
            layer_requirements=layer_requirements or {},
            is_image=is_image,
            handler=handler,
        )
