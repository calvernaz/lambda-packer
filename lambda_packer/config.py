import yaml
import click
import os


class Config:
    default_python_runtime = "3.12"
    default_arch = "linux/amd64"
    package_config_yaml = "package_config.yaml"

    def __init__(self, config_path):
        self.config_path = config_path
        self.config_data = self.load_config()
        self.errors = []

    def load_config(self):
        """Load the YAML configuration from the file or create an empty one if it doesn't exist."""
        if not os.path.exists(self.config_path):
            click.echo(
                f"Config file not found: {self.package_config_yaml}, creating..."
            )
            # Create an empty config file
            with open(self.config_path, "w") as config_file:
                yaml.dump({}, config_file)
            return {}

        try:
            with open(self.config_path, "r") as config_file:
                return yaml.safe_load(config_file) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config: {str(e)}")

    def validate(self):
        """Validate the configuration for required fields and set defaults"""
        self.errors = []

        # Validate lambdas
        lambdas = self.config_data.get("lambdas")
        if not lambdas:
            self.errors.append("Missing or empty 'lambdas' section in config.")
            raise ValueError(
                f"Config validation failed with errors: {self.errors}"
            )  # Ensure the error is raised

        # Validate each lambda config
        for lambda_name, lambda_config in lambdas.items():
            if "type" not in lambda_config:
                self.errors.append(f"Missing 'type' for lambda: {lambda_name}")
            if lambda_config.get("type") == "docker":
                if "image" not in lambda_config:
                    lambda_config["image"] = f"{lambda_name}:latest"  # Default image

            # Validate layers as a list (if present)
            lambda_layers = lambda_config.get("layers", [])
            if not isinstance(lambda_layers, list):
                self.errors.append(
                    f"Layers for lambda '{lambda_name}' should be a list."
                )

            runtime = lambda_config.get("runtime", "3.8")
            self.validate_runtime(runtime)

        if self.errors:
            raise ValueError(f"Config validation failed with errors: {self.errors}")

    def config_lambda(
        self,
        lambda_name,
        layers,
        runtime=default_python_runtime,
        lambda_type="zip",
    ):
        """Add a specific lambda to package_config.yaml."""
        # base path of the repo path
        repo = os.path.dirname(self.config_path)
        lambda_path = os.path.join(repo, lambda_name)

        # Check if the lambda directory exists
        if not os.path.exists(lambda_path):
            click.echo(f"Error: Lambda '{lambda_name}' not found in {repo}.")
            return

        # Check if the lambda is already in the config
        if lambda_name in self.config_data.get("lambdas", {}):
            click.echo(
                f"Lambda '{lambda_name}' is already included in {self.package_config_yaml}."
            )
            return

        # Determine lambda type (zip or docker), based on the presence of a Dockerfile
        lambda_type = (
            "docker"
            if os.path.exists(os.path.join(lambda_path, "Dockerfile"))
            or lambda_type == "docker"
            else "zip"
        )

        # Add the lambda to the config
        if "lambdas" not in self.config_data:
            self.config_data["lambdas"] = {}

        self.config_data["lambdas"][lambda_name] = {
            "type": lambda_type,
            "runtime": runtime,
            "layers": list(layers),
        }

        # Save the updated config
        self.save_config()

        click.secho(
            f"Lambda '{lambda_name}' has been added to {self.package_config_yaml}.",
            fg="green",
        )

    def config_repo(self, layers=[], exclude_dirs=[]):
        """Scan the entire monorepo and add all detected lambdas to package_config.yaml."""

        exclude_dirs.extend(layers)

        lambdas = self.config_data.get("lambdas", {})
        repo = os.path.dirname(self.config_path)
        # Scan for lambdas
        for root, dirs, files in os.walk(repo):

            if any(exclude_dir in root for exclude_dir in exclude_dirs):
                continue

            # TODO: detect the lambda file if more than one throw an error
            if "lambda_handler.py" in files or "Dockerfile" in files:
                lambda_name = os.path.basename(root)
                if lambda_name not in lambdas:
                    lambda_type = "docker" if "Dockerfile" in files else "zip"
                    lambdas[lambda_name] = {
                        "type": lambda_type,
                        "runtime": self.default_python_runtime,
                        "layers": list(layers),
                    }
                else:
                    # Update existing lambda with new layers
                    existing_layers = set(lambdas[lambda_name].get("layers", []))
                    updated_layers = existing_layers.union(set(layers))
                    lambdas[lambda_name]["layers"] = list(updated_layers)

        self.config_data["lambdas"] = lambdas

        # Save the updated config
        self.save_config()

        click.secho(
            f"Updated {self.package_config_yaml} with {len(lambdas)} lambda(s).",
            fg="green",
        )

    def save_config(self):
        """Save the current configuration to the YAML file"""
        with open(self.config_path, "w") as config_file:
            yaml.dump(self.config_data, config_file, default_flow_style=False)

    def validate_runtime(self, runtime):
        """Validate that the runtime is between 3.8 and 3.12"""
        valid_runtimes = ["3.8", "3.9", "3.10", "3.11", "3.12"]
        if runtime not in valid_runtimes:
            self.errors.append(
                f"Invalid runtime: {runtime}. Supported runtimes are: {', '.join(valid_runtimes)}"
            )

    def get_lambdas(self):
        """Return the lambda configurations"""
        return self.config_data.get("lambdas", {})

    def get_lambda_config(self, lambda_name):
        """Return the configuration for a specific lambda"""
        return self.config_data["lambdas"].get(lambda_name)

    def get_lambda_layers(self, lambda_name):
        """Return the layers associated with a specific lambda"""
        return self.get_lambda_config(lambda_name).get("layers", [])

    def get_lambda_runtime(self, lambda_name):
        """Return the runtime for a specific lambda, defaulting to '3.8' if not provided"""
        lambda_config = self.get_lambda_config(lambda_name)
        return lambda_config.get("runtime", self.default_python_runtime)
