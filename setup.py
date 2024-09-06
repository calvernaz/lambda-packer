from setuptools import setup, find_packages

setup(
    name="lambda_packer",
    version="0.1",
    packages=find_packages(),  # Will find the package directory
    install_requires=["Click", "PyYAML", "docker"],
    extras_require={
        "dev": ["black"],  # Add black as a development dependency
    },
    entry_points="""
        [console_scripts]
        lambda-packer=lambda_packer.cli:main
    """,
)
