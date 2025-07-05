# Repository Configuration Files

This folder contains all configuration files for the repository's development tools and CI/CD pipelines.

## Files

### Workflows
- **`ci.yml`** - Main CI/CD pipeline for testing, linting, and type checking
- **`security.yml`** - Security scanning workflow for vulnerability detection

### Code Quality Tools
- **`.pre-commit-config.yaml`** - Pre-commit hooks configuration for automatic code formatting
- **`mypy.ini`** - Type checking configuration for mypy

## Usage

### Local Development
```bash
# Install pre-commit hooks
pre-commit install --config .github/config/.pre-commit-config.yaml

# Run pre-commit on all files
pre-commit run --all-files --config .github/config/.pre-commit-config.yaml

# Run mypy with config
mypy . --config-file .github/config/mypy.ini
```

### CI/CD
The workflows automatically use the configuration files from this folder.

## Structure
```
.github/
├── config/
│   ├── README.md
│   ├── ci.yml
│   ├── security.yml
│   ├── .pre-commit-config.yaml
│   └── mypy.ini
└── workflows/ (empty - moved to config/)
``` 