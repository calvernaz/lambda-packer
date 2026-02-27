# Lambda Packer (BuildKit-Native)

`lambda-packer` is a "compiler" for AWS Lambda and Layers. Instead of running `pip install` on your host machine, it compiles your `package_config.yaml` into a BuildKit execution graph, ensuring your artifacts are always built in a runtime-correct, isolated environment.

## 🚀 Key Features

- **BuildKit-First:** Zero host-side dependencies (except Docker). No more "it works on my machine" C-extension issues.
- **Standardized Context:** Build from any folder on your machine; the tool automatically stages your source and layers.
- **Parallel Builds:** High-performance execution using `ThreadPoolExecutor` and BuildKit's internal graph concurrency.
- **Multi-Platform:** Built-in support for `linux/amd64` and `linux/arm64`.
- **Deterministic ZIPs:** Reproducible artifacts with fixed timestamps and sorted entries.
- **OCI Image Support:** Build and push multi-platform Lambda images directly to a registry.

---

## 🚦 Quick Start

### 1. Initialize the project
```bash
uv sync
```

### 2. Run a Parallel Build
```bash
# Build with 4 parallel workers
uv run lambda-packer build --config package_config.yaml -j 4
```

### 3. Push to a Registry
Ensure you are logged into your registry (`docker login`), then run:
```bash
uv run lambda-packer build --config package_config.yaml --push
```

---

## 📖 Configuration (`package_config.yaml`)

The configuration supports absolute paths, allowing you to build Lambdas from other projects.

```yaml
runtime_default: "python3.12"

layers:
  # Shared layer from an external project
  common-utils:
    path: ./common
    requirements: ./common/requirements.txt
    platforms: [linux/amd64, linux/arm64]

lambdas:
  # ZIP-based Lambda
  api-handler:
    path: ./lambdas/api
    type: zip
    layers: [common-utils]
    platforms: [linux/amd64, linux/arm64]

  # Image-based Lambda with custom tagging
  processor:
    path: ./samples/processor
    type: image
    image_tag: "my-registry.com/processor:{arch}"
    handler: "app.handler"
    layers: [common-utils]
    platforms: [linux/amd64, linux/arm64]
```

---

## 💻 CLI Usage

### `build` command
```bash
uv run lambda-packer build [OPTIONS]
```

**Options:**
- `--config PATH`: Path to your config YAML (default: `package_config.yaml`).
- `--dist PATH`: Directory to store outputs (default: `dist/`).
- `--cache STR`: BuildKit cache options (e.g., `type=local,dest=.buildkit-cache`).
- `--push`: Push OCI images to the registry.
- `-j, --concurrency INT`: Number of parallel builds (default: 1).

---

## 🏗 How it Works (Standardized Context)

The tool uses a "Staging Area" strategy to handle absolute paths and complex dependencies:

1. **Stage:** A temporary directory is created for each build task.
2. **Map:** Source code, requirements, and layers are copied/symlinked into standardized locations (`src/`, `layer_<name>/`).
3. **Compile:** A multi-stage Dockerfile is generated to reference these fixed paths.
4. **Execute:** BuildKit runs the build using this isolated staging directory as the context.

This ensures that **only the necessary files** are sent to Docker, making builds fast and independent of your local file structure.

---

## 🔒 Security & Determinism

All ZIP files are generated with a fixed timestamp (`1980-01-01`) and sorted file entries. 
This ensures that if your code doesn't change, the SHA-256 hash of your ZIP file remains identical, 
preventing unnecessary AWS Lambda deployments.

---

## 🛠 Development

### Setup
```bash
git clone https://github.com/calvernaz/lambda-packer.git
cd lambda-packer
uv sync --extra dev
```

### Running Tests
```bash
PYTHONPATH=src uv run pytest tests/
```

## License

This project is licensed under the MIT License.
