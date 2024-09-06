import yaml


class Config:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config_data = self.load_config()
        self.errors = []

    def load_config(self):
        """Load the YAML configuration from the file"""
        try:
            with open(self.config_path, "r") as config_file:
                return yaml.safe_load(config_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config: {str(e)}")

    def validate(self):
        """Validate the configuration for required fields and set defaults"""
        self.errors = []

        # Validate lambdas
        lambdas = self.config_data.get("lambdas")
        if not lambdas:
            self.errors.append("Missing or empty 'lambdas' section in config.")

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

        if self.errors:
            raise ValueError(f"Config validation failed with errors: {self.errors}")

    def get_lambdas(self):
        """Return the lambda configurations"""
        return self.config_data.get("lambdas", {})

    def get_lambda_config(self, lambda_name):
        """Return the configuration for a specific lambda"""
        return self.config_data["lambdas"].get(lambda_name)

    def get_lambda_layers(self, lambda_name):
        """Return the layers associated with a specific lambda"""
        return self.get_lambda_config(lambda_name).get("layers", [])
