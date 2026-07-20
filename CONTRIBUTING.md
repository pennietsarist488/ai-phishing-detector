# Contributing to AI Phishing Website Detector

First off, thank you for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to this project. These are mostly guidelines, not rules, use your best judgment and feel free to propose changes to this document in a pull request.

---

## Code of Conduct

This project and everyone participating in it is expected to be respectful and inclusive. Examples of behavior that contributes to a positive environment include:

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

---

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report, please check the existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the behavior
- **Expected behavior** vs **actual behavior**
- **Environment info**: OS, Python version, browser version
- **Logs and screenshots** if applicable

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Clear title and description**
- **Use case**: why is this enhancement useful?
- **Possible implementation** if you have ideas

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. Ensure the test suite passes
4. Make sure your code lints
5. Issue that pull request!

---

## Development Setup

```bash
# Clone your fork
git clone https://github.com/cheng-jun-hao/ai-phishing-detector.git
cd phishing-detector

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run the backend
python -m backend.app

# Load the extension in Chrome/Edge
# chrome://extensions/ -> Developer mode -> Load unpacked -> select extension/
```

---

## Coding Standards

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use type hints where possible
- Add docstrings to all functions and classes
- Keep functions focused and small

### JavaScript

- Use modern ES6+ syntax
- Use `const`/`let` instead of `var`
- Add comments for complex logic
- Follow Manifest V3 best practices

### Git Commit Messages

- Use the present tense: "Add feature" not "Added feature"
- Use the imperative mood: "Move cursor to..." not "Moves cursor to..."
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

Example:
```
Add suspicious TLD detection rule

- Add .click, .country to suspicious TLD list
- Update rule engine tests
- Fixes #123
```

---

## Project Structure

Please read the [README.md](README.md) for an overview of the project structure before contributing.

Key areas:
- `backend/engine/` — Detection engines (rule, CNN, form analysis)
- `backend/models/` — Deep learning models
- `backend/api/` — API routes and WebSocket
- `extension/` — Browser extension UI and logic
- `training/` — Model training and evaluation scripts

---

## Testing

```bash
# Run backend tests (if available)
python -m pytest tests/

# Test the extension
# 1. Load the extension in Chrome/Edge
# 2. Test with known phishing URLs (use safe test URLs only)
# 3. Test with known legitimate URLs
```

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
