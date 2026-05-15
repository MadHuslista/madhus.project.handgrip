# Testing Guide

This project uses a decentralized pytest configuration where each submodule maintains its own test configuration in its local `pyproject.toml`.

## Running Tests

### Option 1: Test All Submodules (Recommended)

Run all tests from the repo root using the helper script:

```bash
python pytest_all.py
```

This runs each submodule's tests with its own configuration:
- **RS485_GUI**: 71 tests
- **LSL_Bridge**: 66 tests
- **Handgrip_Calibration**: 5 tests
- **Handgrip_Analysis**: 97 tests
- **LSL_Viewer**: 78 tests

### Option 2: Test Individual Submodules

From the repo root, test a specific submodule:

```bash
cd RS485_GUI && pytest
cd ../LSL_Bridge && pytest
cd ../Handgrip_Calibration && pytest
cd ../Handgrip_Analysis && pytest
cd ../LSL_Viewer && pytest
```

Or using the venv Python directly:

```bash
.venv/bin/python -m pytest RS485_GUI/tests
```

### Option 3: Run All Tests from Root

For CI/CD pipelines, you can also run all tests from the root with a single command:

```bash
.venv/bin/python -m pytest -v
```

This discovers and runs all tests using the root's minimal `pyproject.toml` configuration.

## Configuration Structure

### Root Configuration (`pyproject.toml`)

The root configuration contains **shared settings only**:
- `python_files`: Test file pattern
- `python_classes`: Test class pattern  
- `python_functions`: Test function pattern
- `addopts = "--import-mode=importlib"`: Allows independent test modules across packages

It does **NOT** define `testpaths`, allowing each submodule to manage its own test discovery.

### Submodule Configurations

Each submodule has its own `pyproject.toml` with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

This ensures:
- **Independence**: Each submodule's tests can run standalone from its directory
- **Clarity**: Test configuration lives with the package code
- **Maintainability**: Changes to test structure don't affect other packages

### Coverage Reports

For LSL_Bridge specifically, you can generate coverage reports when needed:

```bash
cd LSL_Bridge
.venv/bin/python -m pytest --cov=lsl_bridge --cov-report=html
```

(Requires `pytest-cov` to be installed)

## Why This Approach?

This structure offers:

1. **Package Independence**: Each team/package can modify their test setup without affecting others
2. **Flexible Invocation**: Test from either the repo root or individual subdirectories
3. **CI/CD Compatible**: Single command (`python pytest_all.py` or `pytest`) works for automation
4. **Scalability**: New packages can be added by editing `pytest_all.py`'s `SUBMODULES` list

## Adding New Submodules

To add a new submodule with tests:

1. Create `NewPackage/tests/` directory with test files
2. Add pytest config to `NewPackage/pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   ```
3. Add `"NewPackage"` to the `SUBMODULES` list in `pytest_all.py`
