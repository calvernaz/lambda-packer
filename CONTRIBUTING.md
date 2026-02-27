# Contribution Guidelines

Thank you for considering contributing to this project! Here are a few guidelines to help you get started:

---

### **How to Contribute**

1. **Fork the Repository**  
   Create a fork of the repository to make your changes.

2. **Create a Branch**  
   Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
   Ensure your code is clean and follows any existing style guidelines. If possible, include tests for any changes you make.
4. **Test your changes**
   Run tests locally to ensure everything works as expected:
   ```
   uv run pytest tests/
   ```
   Run the samples:
   ```bash
   cd samples; uv run lambda-packer build --config package_config.yaml --dist dist
   ```
5. **Commit your changes**
   Write a clear and concise message:
   ```bash
   git commit -m "Add feature or fix bug in..."
   ```
7. **Push to your fork**
   Push the changes to your forked repository:
   ```bash
   git push origin feature/your-feature-name
   ```
9. **Submit a Pull Request**
   Open a pull request (PR) to the main branch of the repository. Be sure to include a description of your changes and link any related issues.

### Code Style ###

* Follow PEP 8 for Python code.
* Ensure that your code is formatted using **black** or another formatter where appropriate.
* Make sure to write clear and concise comments when necessary.

### Bug Reports and Feature Requests ###

If you find a bug or have a feature request, please open an issue in the Issues section of the repository.

For bug reports, include clear steps to reproduce the issue and, if possible, a code example.
For feature requests, describe the feature, its purpose, and how you would implement it.

### License ###

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

