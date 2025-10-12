#!/usr/bin/env python3
"""
CLI utility functions for file operations, validation, and error handling
"""

import json
import os
import sys
from datetime import datetime

import click
from pydantic import ValidationError


def serialize_nested_models(obj):
    """
    Recursively serialize nested Pydantic models to JSON-serializable dictionaries.

    Args:
        obj: Any object that may contain nested Pydantic models

    Returns:
        JSON-serializable version of the object with all Pydantic models converted to dicts
    """
    if hasattr(obj, "model_dump"):
        # This is a Pydantic model - convert it
        return serialize_nested_models(obj.model_dump())
    elif isinstance(obj, dict):
        # Recursively process dictionary values
        return {key: serialize_nested_models(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        # Recursively process list/tuple items
        return [serialize_nested_models(item) for item in obj]
    elif isinstance(obj, datetime):
        # Convert datetime to ISO format string
        return obj.isoformat()
    else:
        # Return primitive types as-is
        return obj


def handle_execution_errors(results: list, test_suite) -> tuple:
    """Process execution results and handle errors gracefully"""

    successful_results = []
    error_results = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Convert exception to error result
            test_case = test_suite.test_cases[i]
            error_result = {
                "test_id": test_case.test_id,
                "success": False,
                "error_message": str(result),
                "error_type": type(result).__name__,
            }
            error_results.append(error_result)

            # Log error with context
            click.echo(f"❌ Test {test_case.test_id} failed: {str(result)[:100]}")

        else:
            successful_results.append(result)

    # Show error summary if there were failures
    if error_results:
        click.echo(
            f"\\nWarning: {len(error_results)} tests failed due to execution errors."
        )
        click.echo("Check detailed logs above for specific error messages.")
        click.echo(
            "Common issues: API rate limits, network timeouts, configuration errors."
        )

    return successful_results, error_results


def validate_api_keys():
    """Validate that required API keys are available"""

    from dotenv import load_dotenv

    load_dotenv()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    missing_keys = []
    if not anthropic_key:
        missing_keys.append("ANTHROPIC_API_KEY")
    if not openai_key:
        missing_keys.append("OPENAI_API_KEY")

    if missing_keys:
        click.echo(
            f"❌ Missing required environment variables: {', '.join(missing_keys)}"
        )
        click.echo("\nPlease set these environment variables:")
        for key in missing_keys:
            click.echo(f"  export {key}=your_api_key_here")
        click.echo("\nOr create a .env file in your project directory.")
        sys.exit(1)

    return anthropic_key, openai_key


def load_json_file(file_path: str, model_class):
    """Load and validate JSON file against a Pydantic model"""
    try:
        with open(file_path) as f:
            data = json.load(f)
        return model_class(**data)
    except FileNotFoundError:
        click.echo(f"❌ File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON in {file_path}: {e}")
        sys.exit(1)
    except ValidationError as e:
        click.echo(f"❌ Invalid format in {file_path}:")
        for error in e.errors():
            click.echo(f"  - {error['loc']}: {error['msg']}")
        sys.exit(1)


def ensure_results_directory():
    """Create XDG-compliant test results directory structure"""
    from ..config.config_manager import ConfigManager

    config_manager = ConfigManager()
    system_paths = config_manager.paths.get_system_paths()

    results_dir = system_paths["data_dir"] / "results"
    runs_dir = results_dir / "runs"

    results_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Create .gitignore if it doesn't exist
    gitignore_path = results_dir / ".gitignore"
    if not gitignore_path.exists():
        with open(gitignore_path, "w") as f:
            f.write("# Ignore all test result files\n")
            f.write("*.json\n")
            f.write("*.html\n")
            f.write("runs/\n")

    return runs_dir


def ensure_local_results_directory():
    """Create local test results directory structure in current working directory"""
    from pathlib import Path

    results_dir = Path("./test_results")
    runs_dir = results_dir / "runs"

    results_dir.mkdir(exist_ok=True)
    runs_dir.mkdir(exist_ok=True)

    # Create .gitignore if it doesn't exist
    gitignore_path = results_dir / ".gitignore"
    if not gitignore_path.exists():
        with open(gitignore_path, "w") as f:
            f.write("# Ignore all test result files\n")
            f.write("*.json\n")
            f.write("*.html\n")
            f.write("runs/\n")

    return runs_dir


def write_test_results_with_location(
    run_id: str, test_run, evaluations, summary, use_global_dir: bool = False
):
    """Write test results to JSON files with location choice"""
    if use_global_dir:
        runs_dir = ensure_results_directory()  # Existing XDG function
    else:
        runs_dir = ensure_local_results_directory()  # New local function

    # Generate datetime prefix for better file recognition
    datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename_prefix = f"{datetime_str}_{run_id}"

    # Use recursive serialization to handle all nested Pydantic models
    test_run_data = serialize_nested_models(test_run)

    if evaluations:
        test_run_data["evaluations"] = serialize_nested_models(evaluations)

    if summary:
        test_run_data["summary"] = serialize_nested_models(summary)

    # Write main test run results (now includes evaluations and summary)
    run_file = runs_dir / f"{filename_prefix}.json"
    with open(run_file, "w") as f:
        json.dump(
            test_run_data,
            f,
            indent=2,
            default=str,
        )

    # Return run_file and None for eval_file to maintain backward compatibility
    return run_file, None


def convert_test_case_definition_to_test_case(test_case_def, server_name: str):
    """Convert TestCaseDefinition from JSON to TestCase for ConversationManager"""
    from ..testing.core.test_models import TestCase

    return TestCase(
        test_id=test_case_def.test_id,
        user_message=test_case_def.user_message,
        success_criteria=test_case_def.success_criteria,
        mcp_server=server_name,
        timeout_seconds=test_case_def.timeout_seconds,
        metadata=test_case_def.metadata or {},
    )


def write_test_results(run_id: str, test_run, evaluations, summary):
    """Write test results to JSON files"""
    runs_dir = ensure_results_directory()

    # Generate datetime prefix for better file recognition
    datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename_prefix = f"{datetime_str}_{run_id}"

    # Use recursive serialization to handle all nested Pydantic models
    test_run_data = serialize_nested_models(test_run)

    if evaluations:
        test_run_data["evaluations"] = serialize_nested_models(evaluations)

    if summary:
        test_run_data["summary"] = serialize_nested_models(summary)

    # Write main test run results (now includes evaluations and summary)
    run_file = runs_dir / f"{filename_prefix}.json"
    with open(run_file, "w") as f:
        json.dump(
            test_run_data,
            f,
            indent=2,
            default=str,
        )

    # Return run_file, None, None to maintain backward compatibility
    return run_file, None, None
