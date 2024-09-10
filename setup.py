from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="lambda_packer",
    version='0.1.7',
    packages=find_packages(),
    install_requires=[
        "Click",
        "PyYAML",
        "docker",
    ],
    extras_require={
        "dev": ["pytest", "black", "twine", "bump2version"],
    },
    entry_points={
        "console_scripts": [
            "lambda-packer=lambda_packer.cli:main",
        ],
    },
    description="A tool to package Python AWS Lambda functions with zips, Docker containers, and layers.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/calvernaz/lambda-packer",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
