# GitHub Copilot Instructions for roundtripper

This document provides guidance for GitHub Copilot when working on the roundtripper project.

## Project Overview

Roundtripper is a Python CLI application for roundtripping with Confluence, built using:
- **Python 3.13+**
- **cyclopts** for CLI framework
- **pydantic** for data validation
- **rich** for terminal output
- **uv** for dependency management
- **hatch** for environment management

## Development Workflow

### Makefile Commands

The project includes a `Makefile` with helpful development commands:

```bash
make help       # Show all available commands
make check      # Run linting (ruff) and type checking (pyright)
make fix        # Auto-format code and fix linting issues
make test       # Run tests with coverage reporting
make lock       # Update dependency lock file
```

**Always run `make check` and `make test` before committing changes.**

## Code Quality Standards

### Testing Philosophy

- **100% test coverage is required** for all new code
- **Prefer dependency injection over mocking** whenever possible
- Only use mocks when testing external dependencies (APIs, file systems, databases)
- Separate business logic from I/O and framework code for easier testing
- Follow cyclopts best practices: separate CLI presentation from business logic

### Test Structure

```python
# Good: Testable business logic with dependency injection
def process_data(data: str, writer: Protocol) -> None:
    result = transform(data)
    writer.write(result)

# Test without mocks
def test_process_data():
    buffer = StringIO()
    process_data("test", buffer)
    assert buffer.getvalue() == "expected"

# Bad: Hard to test without mocks
def process_data(data: str) -> None:
    result = transform(data)
    with open("output.txt", "w") as f:
        f.write(result)
```

### When Mocking is Acceptable

- External HTTP APIs
- File system operations that must not touch disk
- Database connections
- System calls (e.g., `sys.exit()`)
- Time-dependent operations (use freezegun/pytest-freezer)

### Type Checking

- **All code must pass `pyright` with strict settings**
- Use proper type annotations for all functions
- **Never use `object` as a type annotation** - use `Any` from `typing` or a more specific type
- **Prefer specific types over `Any`** - use actual types from libraries (e.g., `Confluence` from `atlassian`, not `Any`)
- Exception: it is good to use `dict[str, Any]` for JSON-like data structures, in particular in tests
- Minimize use of `# type: ignore` - use proper types from libraries instead
- For pytest fixtures, import types like `MockerFixture` from `pytest_mock`
- **Import types from source libraries** - e.g., `from atlassian import Confluence` for API clients

### Code Style

- **Line length: 100 characters**
- Use `ruff` for linting and formatting (configured in `pyproject.toml`)
- Follow PEP 8 naming conventions
- Use descriptive variable names
- Add docstrings to all public functions using NumPy style
- **All imports must be at the top of the file** - no local imports inside functions except for circular dependency resolution

### Docstring Guidelines

- **Do NOT include type annotations in docstrings** - they are already in function signatures
- Use NumPy-style docstrings without type information in parameter descriptions
- Only describe what the parameter does, not its type

Example:
```python
def calculate_total(items: list[Item], tax_rate: float = 0.0) -> Decimal:
    """Calculate the total price including tax.

    Parameters
    ----------
    items
        List of items to calculate total for.
    tax_rate
        Tax rate as a decimal (e.g., 0.1 for 10%), by default 0.0

    Returns
    -------
    Decimal
        Total price including tax.
    """
    subtotal = sum(item.price for item in items)
    return subtotal * (1 + Decimal(str(tax_rate)))
```

## CLI Development with Cyclopts

### Separation of Concerns

Always separate business logic from CLI presentation:

```python
# Business logic - pure function, easy to test
def _process_logic(input_data: str) -> Result:
    """Pure business logic without I/O."""
    return process(input_data)

# CLI command - handles I/O and user interaction
@app.command
def process_command(input_file: Path) -> None:
    """CLI command that orchestrates I/O."""
    data = input_file.read_text()
    result = _process_logic(data)
    print(result)
```

### Testing CLI Commands

- Use `app([], result_action="return_value")` to avoid `sys.exit()` in tests
- Test business logic functions directly without cyclopts
- Test CLI behavior separately using `capsys` for output verification or `caplog` for logging
- **Commands should raise `SystemExit(code)`** instead of calling `sys.exit(code)` - more testable
- Use `pytest.raises(SystemExit)` to test exit behavior
- Provide `console` fixture for consistent Rich output in tests

### CLI Entry Point

The CLI entry point should use `app([])` to avoid warnings in tests:

```python
def cli() -> None:
    """CLI entry point for the roundtripper command."""
    app([])  # Pass empty list to read from sys.argv
```

## Project Structure

```
roundtripper/
├── src/roundtripper/       # Main package code
│   ├── __init__.py         # Version info
│   ├── cli.py              # CLI commands and entry point
│   └── py.typed            # PEP 561 marker
├── tests/                  # Test files
│   ├── conftest.py         # Pytest configuration and fixtures
│   └── test_*.py           # Test modules
├── stubs/                  # Type stubs for external packages
├── pyproject.toml          # Project configuration
├── Makefile                # Development commands
└── .github/
    └── workflows/ci.yml    # GitHub Actions CI pipeline
```

## Dependency Management

- Use `uv` for all dependency operations
- Keep dependencies minimal and well-justified
- Pin dependency versions in `pyproject.toml` using `>=`
- Use dependency groups: `[dependency-groups.dev]` for dev dependencies
- Run `make lock` after adding dependencies

## Git Workflow

- Write clear, descriptive commit messages
- Keep commits atomic and focused
- Run `make check` and `make test` before committing
- All code must pass CI before merging

## Error Handling

- Use custom exception classes for domain errors
- Let exceptions propagate unless you can handle them meaningfully
- Use `rich` for user-friendly error messages
- Log errors with context for debugging

## Configuration

- Use `pydantic-settings` for configuration management
- Support environment variables for all config options
- Provide sensible defaults where possible
- Validate configuration at startup

## Documentation

- Keep `README.md` up to date with usage examples
- Document all public APIs with docstrings
- Include type annotations as inline documentation
- Add comments for complex logic, not obvious code

## CI/CD

The project uses GitHub Actions for CI:
- Linting (ruff)
- Type checking (pyright)
- Tests with coverage
- CLI functionality verification

All checks must pass before merging.

## Common Patterns

### Dependency Injection Example

```python
from typing import Protocol

class Storage(Protocol):
    """Protocol for storage backends."""
    def save(self, key: str, value: str) -> None: ...
    def load(self, key: str) -> str: ...

# Business logic with injected dependency
def sync_data(source: Storage, dest: Storage, key: str) -> None:
    """Sync data between storage backends."""
    data = source.load(key)
    dest.save(key, data)

# Easy to test with fake implementations
def test_sync_data():
    source = FakeStorage({"key": "value"})
    dest = FakeStorage({})
    sync_data(source, dest, "key")
    assert dest.data["key"] == "value"
```

### Result Types Over Exceptions

For expected failure cases, prefer result types:

```python
from typing import Literal

type Result[T] = tuple[Literal[True], T] | tuple[Literal[False], str]

def parse_config(data: str) -> Result[Config]:
    """Parse configuration, returning result or error message."""
    try:
        return (True, Config.parse(data))
    except ValueError as e:
        return (False, f"Invalid config: {e}")

# Test both success and failure without exceptions
def test_parse_config_success():
    success, result = parse_config("valid data")
    assert success
    assert isinstance(result, Config)

def test_parse_config_failure():
    success, error = parse_config("invalid")
    assert not success
    assert "Invalid config" in error
```

## Summary

- **Test everything** - 100% coverage required
- **Inject dependencies** - makes code testable without mocks
- **Use the Makefile** - `make check` and `make test` are your friends
- **Follow cyclopts patterns** - separate logic from CLI
- **Type everything** - strict pyright checking enabled
- **Keep it simple** - prefer clarity over cleverness
