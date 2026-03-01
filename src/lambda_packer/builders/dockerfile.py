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
WORKDIR /asset
{% if layer_requirements[layer_name] %}
COPY layer_{{ layer_name }}_requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \\
    pip install -r /tmp/requirements.txt -t /asset/python
{% endif %}
COPY layer_{{ layer_name }}/ /asset/{{ layer_name }}/
{% endfor %}

FROM python:{{ runtime_version }}-slim AS builder
WORKDIR /asset
{% if requirements %}
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \\
    pip install -r /tmp/requirements.txt -t .
{% endif %}
COPY src/ .

# Merge layer dependencies into the lambda root, but keep layer source code
# namespaced under its layer directory so imports like `common.http` still work
# and do not shadow stdlib modules such as `http`.
{% for layer_name in layers %}
COPY --from=layer-{{ layer_name }} /asset/python/ .
COPY --from=layer-{{ layer_name }} /asset/{{ layer_name }}/ ./{{ layer_name }}/
{% endfor %}

# Final stage
{% if is_image %}
# For OCI images, we use the official AWS Lambda base image to ensure it's runnable.
FROM public.ecr.aws/lambda/python:{{ runtime_version }}
WORKDIR ${LAMBDA_TASK_ROOT}
COPY --from=builder /asset .
# The AWS base image already provides the correct Lambda entrypoint.
CMD [ "{{ handler }}" ]
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
        if is_image and not handler:
            raise ValueError("handler is required when building an image Lambda")

        return self.template.render(
            runtime_version=runtime.replace("python", ""),
            requirements=requirements,
            layers=layers or [],
            layer_requirements=layer_requirements or {},
            is_image=is_image,
            handler=handler,
        )
