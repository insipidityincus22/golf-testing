#!/usr/bin/env python3
"""
Shared file utilities for JSON operations, directory management, and API key validation.
Consolidates common patterns used across the codebase.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, cast

import click
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError


def safe_json_load(
    file_path: str | Path, error_context: str | None = None
) -> dict[str, Any]:
    """
    Safely load JSON file with consistent error handling.

    Args:
        file_path: Path to JSON file to load
        error_context: Optional context for error messages

    Returns:
        Parsed JSON data as dictionary

    Raises:
        SystemExit: On file not found, invalid JSON, or other errors
    """
    file_path = Path(file_path)
    context = error_context or f"loading {file_path.name}"

    try:
        with file_path.open("r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))
    except FileNotFoundError:
        click.echo(f"❌ File not found: {file_path}")
        if error_context:
            click.echo(f"   Context: {error_context}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON in {file_path}: {e}")
        if error_context:
            click.echo(f"   Context: {error_context}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error {context}: {e}")
        sys.exit(1)


def safe_json_dump(
    data: Any,
    file_path: str | Path,
    error_context: str | None = None,
    indent: int = 2,
    ensure_parents: bool = True,
) -> None:
    """
    Safely save data to JSON file with consistent error handling.

    Args:
        data: Data to save as JSON
        file_path: Path where to save the JSON file
        error_context: Optional context for error messages
        indent: JSON indentation (default: 2)
        ensure_parents: Whether to create parent directories (default: True)

    Raises:
        SystemExit: On write errors or other issues
    """
    file_path = Path(file_path)
    context = error_context or f"saving {file_path.name}"

    try:
        if ensure_parents:
            ensure_directory(file_path.parent)

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    except Exception as e:
        click.echo(f"❌ Error {context}: {e}")
        if error_context:
            click.echo(f"   Context: {error_context}")
        sys.exit(1)


def safe_json_load_model(
    file_path: str | Path,
    model_class: type[BaseModel],
    error_context: str | None = None,
) -> BaseModel:
    """
    Load and validate JSON file against a Pydantic model.

    Args:
        file_path: Path to JSON file to load
        model_class: Pydantic model class for validation
        error_context: Optional context for error messages

    Returns:
        Validated Pydantic model instance

    Raises:
        SystemExit: On file errors, JSON errors, or validation errors
    """
    file_path = Path(file_path)
    context = error_context or f"loading {file_path.name} as {model_class.__name__}"

    try:
        data = safe_json_load(file_path, context)
        return model_class(**data)
    except ValidationError as e:
        click.echo(f"❌ Invalid format in {file_path}:")
        for error in e.errors():
            click.echo(f"  - {error['loc']}: {error['msg']}")
        if error_context:
            click.echo(f"   Context: {error_context}")
        sys.exit(1)


def ensure_directory(path: str | Path) -> Path:
    """
    Ensure directory exists, creating it and parents if necessary.

    Args:
        path: Directory path to ensure exists

    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_api_key(key_name: str) -> str | None:
    """
    Validate that a specific API key environment variable is set.

    Args:
        key_name: Name of the environment variable (e.g., 'ANTHROPIC_API_KEY')

    Returns:
        The API key value if found, None if not set
    """
    return os.getenv(key_name)


def validate_required_api_keys(*key_names: str) -> dict[str, str]:
    """
    Validate that all required API keys are available.

    Args:
        *key_names: Names of required environment variables

    Returns:
        Dictionary mapping key names to their values

    Raises:
        SystemExit: If any required API keys are missing
    """
    # Load .env file with default parent directory search
    load_dotenv()

    found_keys = {}
    missing_keys = []

    for key_name in key_names:
        key_value = os.getenv(key_name)
        if key_value:
            found_keys[key_name] = key_value
        else:
            missing_keys.append(key_name)

    if missing_keys:
        click.echo(
            f"❌ Missing required environment variables: {', '.join(missing_keys)}"
        )
        click.echo("\nPlease set these environment variables:")
        for key in missing_keys:
            click.echo(f"  export {key}=your_api_key_here")
        click.echo("\nOr create a .env file in your project directory.")
        sys.exit(1)

    return found_keys


def create_gitignore_if_needed(directory: str | Path, patterns: list[str]) -> None:
    """
    Create a .gitignore file in a directory if it doesn't exist.

    Args:
        directory: Directory where to create .gitignore
        patterns: List of patterns to ignore
    """
    directory = Path(directory)
    gitignore_path = directory / ".gitignore"

    if not gitignore_path.exists():
        with gitignore_path.open("w", encoding="utf-8") as f:
            f.write("# Auto-generated .gitignore\n")
            for pattern in patterns:
                f.write(f"{pattern}\n")


def ensure_results_directory_structure(base_dir: str | Path) -> Path:
    """
    Create a standard test results directory structure with .gitignore.

    Args:
        base_dir: Base directory for results

    Returns:
        Path to the runs subdirectory
    """
    base_dir = Path(base_dir)
    runs_dir = base_dir / "runs"

    ensure_directory(runs_dir)

    # Create .gitignore for test results
    create_gitignore_if_needed(
        base_dir, ["# Ignore all test result files", "*.json", "*.html", "runs/"]
    )

    return runs_dir
