# ==========================================
# Schema Loader
# ==========================================

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = BASE_DIR / "schema_docs.json"


class SchemaLoaderError(Exception):
    """Raised when schema loading or validation fails."""


def _read_json_file(schema_path: Path) -> Dict[str, Any]:
    """
    Read schema JSON file safely.
    """
    if not schema_path.exists():
        raise SchemaLoaderError(f"Schema file not found: {schema_path}")

    if not schema_path.is_file():
        raise SchemaLoaderError(f"Schema path is not a file: {schema_path}")

    try:
        with schema_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise SchemaLoaderError(
            f"Invalid JSON format in schema file: {schema_path}"
        ) from exc
    except Exception as exc:
        raise SchemaLoaderError(
            f"Unexpected error while reading schema file: {schema_path}"
        ) from exc

    if not isinstance(data, dict):
        raise SchemaLoaderError("Top-level schema JSON must be a dictionary/object.")

    return data


def _validate_table_metadata(table_name: str, table_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize one table's metadata.
    Preserves all fields present in schema_docs.json while ensuring
    required keys exist in a predictable format.
    """
    if not isinstance(table_data, dict):
        raise SchemaLoaderError(
            f"Metadata for table '{table_name}' must be an object/dictionary."
        )

    normalized = deepcopy(table_data)

    # Required structure defaults
    normalized.setdefault("domain", "unknown")
    normalized.setdefault("description", "")
    normalized.setdefault("primary_keys", [])
    normalized.setdefault("business_keys", [])
    normalized.setdefault("columns", {})
    normalized.setdefault("used_for", [])
    normalized.setdefault("join_hints", [])

    # Type checks
    if not isinstance(normalized["domain"], str):
        raise SchemaLoaderError(f"'domain' must be a string for table '{table_name}'.")

    if not isinstance(normalized["description"], str):
        raise SchemaLoaderError(f"'description' must be a string for table '{table_name}'.")

    if not isinstance(normalized["primary_keys"], list):
        raise SchemaLoaderError(f"'primary_keys' must be a list for table '{table_name}'.")

    if not isinstance(normalized["business_keys"], list):
        raise SchemaLoaderError(f"'business_keys' must be a list for table '{table_name}'.")

    if not isinstance(normalized["columns"], dict):
        raise SchemaLoaderError(f"'columns' must be an object/dictionary for table '{table_name}'.")

    if not isinstance(normalized["used_for"], list):
        raise SchemaLoaderError(f"'used_for' must be a list for table '{table_name}'.")

    if not isinstance(normalized["join_hints"], list):
        raise SchemaLoaderError(f"'join_hints' must be a list for table '{table_name}'.")

    # Column checks
    cleaned_columns: Dict[str, str] = {}
    for column_name, column_description in normalized["columns"].items():
        if not isinstance(column_name, str):
            raise SchemaLoaderError(
                f"Column name must be a string in table '{table_name}'."
            )
        if not isinstance(column_description, str):
            raise SchemaLoaderError(
                f"Column description for '{table_name}.{column_name}' must be a string."
            )
        cleaned_columns[column_name] = column_description.strip()

    normalized["columns"] = cleaned_columns

    # Clean lists
    normalized["primary_keys"] = [str(item).strip() for item in normalized["primary_keys"]]
    normalized["business_keys"] = [str(item).strip() for item in normalized["business_keys"]]
    normalized["used_for"] = [str(item).strip() for item in normalized["used_for"]]
    normalized["join_hints"] = [str(item).strip() for item in normalized["join_hints"]]

    return normalized


def _normalize_schema_document(schema_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize full schema document.

    Expected shape:
    {
        "version": "...",
        "purpose": "...",
        "notes": [...],
        "tables": {
            "table_name": {...}
        }
    }
    """
    normalized = deepcopy(schema_doc)

    normalized.setdefault("version", "1.0")
    normalized.setdefault("purpose", "")
    normalized.setdefault("notes", [])
    normalized.setdefault("tables", {})

    if not isinstance(normalized["version"], str):
        raise SchemaLoaderError("'version' must be a string.")

    if not isinstance(normalized["purpose"], str):
        raise SchemaLoaderError("'purpose' must be a string.")

    if not isinstance(normalized["notes"], list):
        raise SchemaLoaderError("'notes' must be a list.")

    if not isinstance(normalized["tables"], dict):
        raise SchemaLoaderError("'tables' must be an object/dictionary.")

    cleaned_notes = [str(note).strip() for note in normalized["notes"]]
    normalized["notes"] = cleaned_notes

    cleaned_tables: Dict[str, Dict[str, Any]] = {}
    for table_name, table_data in normalized["tables"].items():
        if not isinstance(table_name, str):
            raise SchemaLoaderError("All table names in schema JSON must be strings.")
        cleaned_tables[table_name] = _validate_table_metadata(table_name, table_data)

    normalized["tables"] = cleaned_tables
    return normalized


def load_full_schema_document(schema_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load and validate the entire schema document, preserving every field.

    Returns:
        {
            "version": str,
            "purpose": str,
            "notes": list[str],
            "tables": {
                "table_name": {
                    "domain": str,
                    "description": str,
                    "primary_keys": list[str],
                    "business_keys": list[str],
                    "columns": dict[str, str],
                    "used_for": list[str],
                    "join_hints": list[str],
                    ...any additional fields preserved...
                }
            }
        }
    """
    path = Path(schema_path) if schema_path else DEFAULT_SCHEMA_PATH
    raw_data = _read_json_file(path)
    return _normalize_schema_document(raw_data)


def load_schema(
    table_names: Optional[List[str]] = None,
    schema_path: Optional[str] = None,
    include_meta: bool = False,
    strict: bool = True,
) -> Dict[str, Any]:
    """
    Load schema metadata for selected tables or all tables.

    Args:
        table_names:
            List of table names to load.
            If None or empty, returns all tables.
        schema_path:
            Optional custom path to schema_docs.json
        include_meta:
            If True, return full document including version/purpose/notes/tables.
            If False, return only the selected tables dictionary.
        strict:
            If True, raise error when any requested table is missing.
            If False, silently ignore missing tables.

    Returns:
        If include_meta=False:
            {
                "login_mast": {...},
                "emp_leave_setting": {...}
            }

        If include_meta=True:
            {
                "version": "...",
                "purpose": "...",
                "notes": [...],
                "tables": {
                    ...
                }
            }
    """
    schema_doc = load_full_schema_document(schema_path=schema_path)
    all_tables = schema_doc["tables"]

    if not table_names:
        selected_tables = deepcopy(all_tables)
    else:
        selected_tables = {}
        missing_tables = []

        for table_name in table_names:
            if table_name in all_tables:
                selected_tables[table_name] = deepcopy(all_tables[table_name])
            else:
                missing_tables.append(table_name)

        if strict and missing_tables:
            available = ", ".join(sorted(all_tables.keys()))
            missing = ", ".join(missing_tables)
            raise SchemaLoaderError(
                f"Requested table(s) not found in schema_docs.json: {missing}. "
                f"Available tables: {available}"
            )

    if include_meta:
        return {
            "version": schema_doc["version"],
            "purpose": schema_doc["purpose"],
            "notes": schema_doc["notes"],
            "tables": selected_tables,
        }

    return selected_tables


def get_table_names(schema_path: Optional[str] = None) -> List[str]:
    """
    Return all available table names from schema_docs.json.
    """
    schema_doc = load_full_schema_document(schema_path=schema_path)
    return sorted(schema_doc["tables"].keys())


def get_table_schema(table_name: str, schema_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Return schema metadata for a single table.
    """
    schema = load_schema(
        table_names=[table_name],
        schema_path=schema_path,
        include_meta=False,
        strict=True,
    )
    return schema[table_name]


def get_table_columns(table_name: str, schema_path: Optional[str] = None) -> Dict[str, str]:
    """
    Return column metadata for a single table.
    """
    table_schema = get_table_schema(table_name, schema_path=schema_path)
    return deepcopy(table_schema.get("columns", {}))


def search_tables_by_domain(domain: str, schema_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Return all tables belonging to a specific domain.
    Example domains: attendance, leave, shift, policy, reference
    """
    schema = load_schema(schema_path=schema_path, include_meta=False)
    target_domain = (domain or "").strip().lower()

    return {
        table_name: metadata
        for table_name, metadata in schema.items()
        if str(metadata.get("domain", "")).strip().lower() == target_domain
    }


def search_tables_by_use_case(use_case: str, schema_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Return tables whose 'used_for' contains the given phrase.
    """
    schema = load_schema(schema_path=schema_path, include_meta=False)
    target = (use_case or "").strip().lower()

    if not target:
        return {}

    matched: Dict[str, Any] = {}
    for table_name, metadata in schema.items():
        used_for = metadata.get("used_for", [])
        if any(target in str(item).lower() for item in used_for):
            matched[table_name] = metadata

    return matched


def build_llm_schema_context(
    table_names: List[str],
    schema_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a clean, LLM-friendly subset of schema metadata.

    This is useful because downstream prompt builders usually need:
    - table name
    - description
    - important columns
    - join hints
    - use cases

    rather than raw file metadata only.

    Returns:
        {
            "tables": {
                "login_mast": {
                    "description": "...",
                    "columns": {...},
                    "primary_keys": [...],
                    "business_keys": [...],
                    "join_hints": [...],
                    "used_for": [...]
                }
            }
        }
    """
    selected_tables = load_schema(
        table_names=table_names,
        schema_path=schema_path,
        include_meta=False,
        strict=True,
    )

    llm_context = {"tables": {}}

    for table_name, metadata in selected_tables.items():
        llm_context["tables"][table_name] = {
            "description": metadata.get("description", ""),
            "domain": metadata.get("domain", ""),
            "columns": deepcopy(metadata.get("columns", {})),
            "primary_keys": deepcopy(metadata.get("primary_keys", [])),
            "business_keys": deepcopy(metadata.get("business_keys", [])),
            "join_hints": deepcopy(metadata.get("join_hints", [])),
            "used_for": deepcopy(metadata.get("used_for", [])),
        }

    return llm_context