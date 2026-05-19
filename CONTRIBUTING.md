# Contributing to Klein Conformance Protocol

Thank you for your interest in contributing to Klein! This document provides guidelines and instructions for contributors.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)
- [Adding Test Vectors](#adding-test-vectors)
- [Terminology](#terminology)

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- pip

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/at1deer/klein.git
cd klein

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify installation
python -c "from klein.sim.physics import GeodesicSolver; print('OK')"
```

---

## Development Setup

### Environment Variables

```bash
# Add src to Python path (alternative to pip install -e .)
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

### IDE Configuration

For VS Code, add to `.vscode/settings.json`:

```json
{
    "python.analysis.extraPaths": ["./src"],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"]
}
```

---

## Project Structure

```
klein/
    schemas/           # JSON Schema definitions (source of truth)
    specs/             # Protocol specifications (human-readable)
    src/klein/
        common/
            models.py  # Pydantic models (generated from schemas)
            errors.py  # Error code definitions
        sim/
            physics.py # Geodesic solver, field math
            runner.py  # Simulator CLI
        substrate/
            api.py     # Hardware driver protocol
    tests/
        conform.py     # Conformance test harness
        test_physics.py # Physics engine tests
        vectors/
            kap/       # Compiled test vectors (.kleinc)
            loose/     # Unpacked test vectors (legacy)
    tools/
        pack_kleinc.py   # Container packing tool
    examples/          # Example projects (.klein files)
    docs/
        API.md         # API reference
        GLOSSARY.md    # Terminology glossary
```

---

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `test/vector-NNN` - New test vectors

### Commit Messages

Follow conventional commits:

```
feat: add support for RLE encoding
fix: correct Phi clamping at field boundaries
docs: update physics engine spec
test: add vector 121 for edge case
```

---

## Testing

### Run All Tests

```bash
# Physics engine tests
python tests/test_physics.py

# Conformance tests (mock backend)
python tests/conform.py --backend mock

# Conformance tests (specific vectors)
python tests/conform.py --vector 001 --vector 113 --verbose
```

### Test Categories

```bash
# Positive tests only
python tests/conform.py --category positive

# Negative tests only
python tests/conform.py --category negative

# List all vectors
python tests/conform.py --list
```

### Running the Simulator

```bash
# Basic simulation
python -m klein.sim.runner examples/simple_path.klein --source source --sink sink

# With trace output
python -m klein.sim.runner examples/simple_path.klein -s source -t sink --trace trace.json

# With State Image Bundle (SImgB)
python -m klein.sim.runner examples/simple_path.klein -s source -t sink --simgb device.json
```

---

## Submitting Changes

### Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** your changes
4. **Test** thoroughly
5. **Submit** a pull request

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New features have tests
- [ ] Documentation updated
- [ ] No linting errors

---

## Code Style

### Python

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Type hints**: Required for all public APIs
- **Docstrings**: Google style

```python
def solve_geodesic(
    project: KleinProject,
    source: str,
    sink: str,
) -> PathResult:
    """
    Find the optimal geodesic path in a Klein project.
    
    Args:
        project: The Klein project definition
        source: Source node ID
        sink: Sink (goal) node ID
        
    Returns:
        PathResult with optimal path and cost
        
    Raises:
        ValueError: If source or sink not in graph
    """
```

### JSON Schemas

- Use `$id` for schema identification
- Include `description` for all properties
- Define `required` arrays explicitly

---

## Adding Test Vectors

### Creating a New Vector

1. **Create folder** in `tests/vectors/loose/`:

```
tests/vectors/loose/121_my_new_test/
    manifest.json      # Package manifest
    payload.json       # Actuation data
    expected/
        expected.json  # Pass/fail criteria
    golden/
        observables.jsonl  # Expected HAIL output (optional)
```

2. **Pack to .kleinc**:

```bash
python tools/pack_kleinc.py tests/vectors/loose/121_my_new_test \
    -o tests/vectors/kap/121_my_new_test.kleinc
```

3. **Update index.json**:

Add entry to `tests/vectors/index.json`:

```json
{
    "id": "121",
    "file": "kap/121_my_new_test.kleinc",
    "purpose": "Description of what this tests"
}
```

4. **For negative tests**, also add to `negative_tests`:

```json
{
    "id": "121",
    "expected_error_code": "PAYLOAD_INVALID_VALUE"
}
```

### Vector Naming Convention

```
NNN_category_description.kleinc

Examples:
    001_minimal_muxed.kleinc                # Positive baseline
    010_tft_delta_invalid_negative.kleinc   # Negative test
    113_rimgb_runtime_state_positive.kleinc # HAIL feature test
```

---

## Terminology

The Klein Conformance Protocol uses specific terminology. See the [full glossary](docs/GLOSSARY.md) for details.

| Term | Full Name | Description |
|------|-----------|-------------|
| **HAIL** | Hardware Audit & Integrity Log | Cryptographic event log |
| **SImgB** | State Image Bundle | Static hardware config |
| **RImgB** | Runtime Image Bundle | Dynamic runtime state |
| **ECRP** | Error Correction & Recovery Protocol | Autonomous error healing |
| `.klein` | Klein Project File | Graph definition format |
| `.kleinc` | Klein Compiled Container | Bundled execution package |

---

## Schema Changes

If you modify JSON schemas:

1. Update the schema file in `schemas/`
2. Regenerate or update Pydantic models in `src/klein/common/models.py`
3. Update spec documentation in `specs/`
4. Add test vectors covering new functionality

---

## Questions?

- Open a [GitHub Issue](https://github.com/at1deer/klein/issues)
- Check existing documentation in `specs/` and `docs/`

Thank you for contributing!
