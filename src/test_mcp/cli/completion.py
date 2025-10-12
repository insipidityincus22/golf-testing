#!/usr/bin/env python3
"""
Tab completion functions for CLI arguments and options
"""

from click.shell_completion import CompletionItem

from ..config.config_manager import ConfigManager


def complete_server_ids(ctx, param, incomplete):
    """Tab completion for server IDs with descriptions"""
    config_manager = ConfigManager()

    try:
        servers = config_manager.list_servers()
        return [
            CompletionItem(
                server_id, help=f"Server: {server_info['name']} ({server_info['url']})"
            )
            for server_id, server_info in servers.items()
            if server_id.startswith(incomplete)
        ]
    except Exception:
        return []


def complete_suite_ids(ctx, param, incomplete):
    """Tab completion for suite IDs with descriptions"""
    config_manager = ConfigManager()

    try:
        suites = config_manager.list_suites()
        return [
            CompletionItem(
                suite_id,
                help=f"Suite: {suite_info['name']} ({suite_info['test_count']} tests)",
            )
            for suite_id, suite_info in suites.items()
            if suite_id.startswith(incomplete)
        ]
    except Exception:
        return []


def complete_config_types(ctx, param, incomplete):
    """Tab completion for configuration types"""
    types = ["server", "suite"]
    return [
        CompletionItem(t, help=f"Show {t} configurations")
        for t in types
        if t.startswith(incomplete)
    ]


def complete_list_filters(ctx, param, incomplete):
    """Tab completion for list command filters"""
    filters = ["servers", "suites"]
    return [
        CompletionItem(f, help=f"List only {f}")
        for f in filters
        if f.startswith(incomplete)
    ]
