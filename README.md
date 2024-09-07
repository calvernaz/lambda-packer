# lambda-packer

**A streamlined tool for managing and packaging Python AWS Lambda functions**
---

## Overview

`lambda-packer` is a command-line tool designed to simplify the process of packaging Python AWS Lambda functions. 
It provides an opinionated approach to develop Lambdas using a monorepo, allowing packaging as either zip files or Docker containers, 
with shared dependencies packaged as Lambda layers.
### Key Features

- **Package Lambdas as zip files or Docker containers**
- **Support for multiple Lambda layers** shared across functions
- **Simple YAML configuration** to manage Lambdas and layers
- **Layer packaging with automatic dependency handling**

---

## Installation

To install the tool, clone this repository and run:

```bash
git clone https://github.com/calvernaz/lambda-packer.git
cd lambda-packer
pip install -e .
```

For development:

```bash
pip install -e .[dev]
```

---

## Usage

### 1. Initialize a New Monorepo

The `init` command creates a basic monorepo structure for your Lambda functions, including a `common` folder for shared dependencies, an example Lambda function, and a `package_config.yaml` file.

```bash
lambda-packer init <parent_directory> --lambda-name <lambda_name>
```

Example:

```bash
lambda-packer init my_project --lambda-name my_lambda
```

This command creates:

```
my_project/
├── common/
├── my_lambda/
│   ├── lambda_handler.py
│   └── requirements.txt
├── dist/
└── package_config.yaml
```

### 2. Configuration

The `package_config.yaml` file is where you define how to package your Lambdas. You can specify the type of packaging (`zip` or `docker`), the Python runtime, and any layers associated with the Lambda.

#### Example `package_config.yaml`

```yaml
lambdas:
my_lambda:
type: zip
runtime: "3.12"  # Specify the Python runtime version
layers:
- common
```

### 3. Package Lambda as a Zip

To package a Lambda function (for a `zip` type Lambda), use the following command:

```bash
lambda-packer package my_lambda
```

This will package the Lambda function and any referenced layers (e.g., `common`) into a zip file in the `dist` directory.

### 4. Package Lambda as a Docker Container

To package a Lambda as a Docker container (for a `docker` type Lambda), modify the `package_config.yaml` and set `type: docker`.

```yaml
lambdas:
my_lambda:
type: docker
runtime: "3.9"
layers:
- common
```

Then run:

```bash
lambda-packer package my_lambda
```

The tool will build a Docker image using the specified Python runtime and package the Lambda function.

### 5. Packaging Lambda Layers

If you need to package shared dependencies (like the `common` folder) as Lambda layers, you can use the `package-layer` command:

```bash
lambda-packer package-layer common
```

This command packages the `common` directory as a Lambda layer and zips it to the `dist/` folder.

---

## Available Commands

- `init <parent_directory> --lambda-name <lambda_name>`: Initialize a new monorepo with a common folder, a lambda, and `package_config.yaml`.
- `package <lambda_name>`: Package the specified Lambda function (either as zip or Docker container).
- `package-layer <layer_name>`: Package a specific layer (e.g., `common`) into a zip file.
- `clean`: Clean the `dist/` directory by removing all contents.

---

## Example Workflow

1. **Initialize the project**:

```bash
lambda-packer init my_project --lambda-name my_lambda
```

2. **Edit `package_config.yaml`** to configure the Lambda:

```yaml
lambdas:
my_lambda:
type: zip
runtime: "3.9"
layers:
- common
```

3. **Install dependencies** for `my_lambda` by editing `my_lambda/requirements.txt`.

4. **Package the Lambda**:

```bash
lambda-packer package my_lambda
```

5. **Package the `common` layer** (if needed):

```bash
lambda-packer package-layer common
```

### 6. Adding a New Lambda to an Existing Monorepo

You can add a new Lambda to an existing monorepo using the `lambda` command. You can also specify layers to be added to the new Lambda.

```bash
lambda-packer lambda <lambda_name> --runtime <runtime_version> --type <zip|docker> --layers <layer1> --layers <layer2>
```

Example:

```bash
lambda-packer lambda my_new_lambda --runtime 3.9 --type docker --layers common --layers shared
```

This will create a new Lambda directory and update the `package_config.yaml` like so:

```yaml
lambdas:
my_new_lambda:
runtime: "3.9"
type: docker
layers:
- common
- shared
```

If no layers are specified, the `layers` key will not be added.

Example without layers:

```bash
lambda-packer lambda my_new_lambda --runtime 3.9 --type docker
```

This will update the `package_config.yaml` like this:

```yaml
lambdas:
my_new_lambda:
runtime: "3.9"
type: docker
```

---

## Contributing

Contributions are welcome! If you'd like to contribute to this project, please open a pull request or issue on GitHub.

### Development Setup

```bash
pip install -e .[dev]
```

### Running Tests

```bash
pytest tests/
```

---

## License

This project is licensed under the MIT License.

---

## Contact

For any questions or feedback, feel free to open an issue on GitHub.