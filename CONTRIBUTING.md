# Contributing to Creative Automation Pipeline

Thank you for considering contributing! This document provides guidelines for contributing to the project.

---

## Code of Conduct

### Our Pledge
- Be respectful and inclusive
- Focus on constructive feedback
- Collaborate professionally
- Respect differing viewpoints

---

## How to Contribute

### 1. Fork the Repository

```bash
# Fork on GitHub, then clone
git clone https://github.com/your username/CreativeForgeAI.git
cd CreativeForgeAI
```

### 2. Create Feature Branch

```bash
# Create branch from main
git checkout -b feature/amazing-feature
```

**Branch Naming:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `refactor/` - Code refactoring
- `test/` - Test additions

### 3. Make Changes

Follow coding standards (see below).

### 4. Write Tests

```bash
# Add tests for new features
pytest tests/test_your_feature.py

# Ensure all tests pass
pytest

# Check coverage
pytest --cov=src
```

**Coverage Requirements:**
- Overall: ≥80%
- New code: ≥90%

### 5. Commit Changes

Use **Conventional Commits**:

```bash
git commit -m "feat: add amazing feature"
git commit -m "fix: resolve issue with image processing"
git commit -m "docs: update README with new examples"
```

**Commit Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `style:` - Formatting
- `refactor:` - Code restructuring
- `test:` - Test additions
- `chore:` - Maintenance

### 6. Push and Create PR

```bash
git push origin feature/amazing-feature
```

Then create Pull Request on GitHub.

---

## Coding Standards

### Python Style

Follow **PEP 8** with Black formatting:

```bash
# Format code
black src/

# Check linting
flake8 src/

# Type checking
mypy src/
```

### Code Quality

- **DRY** - Don't Repeat Yourself
- **SOLID** - Follow SOLID principles
- **Clear naming** - Descriptive variable/function names
- **Comments** - Only when necessary, code should be self-documenting
- **Type hints** - Use Python type annotations

### Example:

```python
from typing import List, Optional
from pydantic import BaseModel

class Product(BaseModel):
    """Represents a product in the campaign."""

    product_id: str
    product_name: str
    features: List[str]

    def validate_features(self) -> bool:
        """Validate product features are not empty."""
        return len(self.features) > 0
```

---

## Testing Guidelines

### Unit Tests

```python
import pytest
from src.models import Product

def test_product_validation():
    """Test product validation logic."""
    product = Product(
        product_id="TEST-001",
        product_name="Test Product",
        features=["Feature 1"]
    )
    assert product.validate_features() is True
```

### Integration Tests

```python
@pytest.mark.integration
async def test_pipeline_processing():
    """Test full pipeline execution."""
    pipeline = CreativeAutomationPipeline()
    result = await pipeline.process_campaign(test_brief)
    assert result.success_rate == 1.0
```

---

## Documentation

### Docstrings

Use **Google Style** docstrings:

```python
def generate_image(prompt: str, size: str = "1024x1024") -> bytes:
    """Generate image from text prompt.

    Args:
        prompt: Text description of desired image
        size: Image dimensions (default: "1024x1024")

    Returns:
        Image data as bytes

    Raises:
        APIError: If image generation fails
    """
    pass
```

### Update Documentation

- Update README.md if adding features
- Add to CHANGELOG.md
- Create/update docs/ files as needed

---

## Pull Request Process

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Conventional commit messages
- [ ] Branch is up-to-date with main

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added
- [ ] Documentation updated
```

---

## Development Setup

### Install Dev Dependencies

```bash
pip install -r requirements-dev.txt
```

Includes:
- pytest
- black
- flake8
- mypy
- coverage

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## Areas for Contribution

### High Priority
- [ ] Additional image backends
- [ ] More localization guidelines
- [ ] Additional legal templates
- [ ] Performance optimizations
- [ ] Documentation improvements

### Medium Priority
- [ ] Web UI
- [ ] API server
- [ ] Batch processing
- [ ] Cloud storage integration

### Good First Issues
- [ ] Add unit tests
- [ ] Fix typos
- [ ] Improve error messages
- [ ] Add examples

---

## Questions?

- **Issues:** [GitHub Issues](https://github.com/calabamatex/CreativeForgeAI/issues)
- **Discussions:** [GitHub Discussions](https://github.com/calabamatex/CreativeForgeAI/discussions)

---

Thank you for contributing! 🎉
