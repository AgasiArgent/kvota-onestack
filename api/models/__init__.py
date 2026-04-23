"""Pydantic v2 models for /api/* request and response contracts.

Submodules group models by domain (journey, ...). Models live here rather
than inline in router files so they can be shared between handlers, tests,
and future MCP / OpenAPI tooling without creating circular imports.
"""
