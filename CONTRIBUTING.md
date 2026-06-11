# Contributing to Chess Analyzer Pro

First off, thank you for considering contributing to Chess Analyzer Pro! It's people like you that make open source such a fantastic community.

## 🤝 How Can I Contribute?

### Reporting Bugs
This section guides you through submitting a bug report. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.
- **Ensure the bug was not already reported** by searching on GitHub under Issues.
- **Use a clear and descriptive title** for the issue to identify the problem.
- **Describe the exact steps** which reproduce the problem in as many details as possible.

### Suggesting Enhancements
This section guides you through submitting an enhancement suggestion, including completely new features and minor improvements to existing functionality.
- **Use a clear and descriptive title** for the issue to identify the suggestion.
- **Provide a step-by-step description** of the suggested enhancement.
- **Explain why this enhancement would be useful** to most users.

### Pull Requests
1. Fork the repository and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. Ensure the test suite passes (`python -m pytest tests/`).
4. Update the documentation if you change any functionality.
5. Issue that pull request!

## 💻 Development Setup
1. Clone the repo and navigate to it:
   ```bash
   git clone https://github.com/yourusername/chess-analyzer-pro.git
   cd chess-analyzer-pro
   ```
2. Create and activate a virtual environment:
   ```bash
   uv venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   uv run main.py
   ```

## 📝 Code Style
- Follow PEP 8 guidelines for Python code.
- Write meaningful commit messages.
- Keep pull requests focused on a single issue or feature.
