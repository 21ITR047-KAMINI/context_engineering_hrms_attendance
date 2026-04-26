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


# ------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------
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


def _clean_string_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []

    output: List[str] = []
    seen = set()

    for item in values:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)

    return output


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

    if not isinstance(normalized["columns"], dict):
        raise SchemaLoaderError(f"'columns' must be an object/dictionary for table '{table_name}'.")

    # Normalize columns
    cleaned_columns: Dict[str, str] = {}
    for column_name, column_description in normalized["columns"].items():
        if not isinstance(column_name, str):
            raise SchemaLoaderError(
                f"Column name must be a string in table '{table_name}'."
            )
        cleaned_columns[column_name.strip()] = str(column_description).strip()

    normalized["columns"] = cleaned_columns

    # Normalize list fields
    normalized["primary_keys"] = _clean_string_list(normalized.get("primary_keys", []))
    normalized["business_keys"] = _clean_string_list(normalized.get("business_keys", []))
    normalized["used_for"] = _clean_string_list(normalized.get("used_for", []))
    normalized["join_hints"] = _clean_string_list(normalized.get("join_hints", []))

    # Normalize simple strings
    normalized["domain"] = normalized["domain"].strip()
    normalized["description"] = normalized["description"].strip()

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

    normalized["notes"] = _clean_string_list(normalized["notes"])

    cleaned_tables: Dict[str, Dict[str, Any]] = {}
    for table_name, table_data in normalized["tables"].items():
        if not isinstance(table_name, str):
            raise SchemaLoaderError("All table names in schema JSON must be strings.")
        cleaned_tables[table_name.strip()] = _validate_table_metadata(table_name.strip(), table_data)

    normalized["tables"] = cleaned_tables
    return normalized


def _build_case_insensitive_table_map(all_tables: Dict[str, Any]) -> Dict[str, str]:
    return {
        str(table_name).strip().lower(): table_name
        for table_name in all_tables.keys()
        if str(table_name).strip()
    }


def _resolve_requested_table_names(
    requested_table_names: List[str],
    all_tables: Dict[str, Any],
) -> Dict[str, str]:
    """
    Resolve requested table names to real schema_docs.json names
    using case-insensitive matching.

    Returns:
        {
            "requested_name": "ActualTableName"
        }
    """
    table_map = _build_case_insensitive_table_map(all_tables)
    resolved: Dict[str, str] = {}

    for raw_name in requested_table_names:
        clean_name = str(raw_name).strip()
        if not clean_name:
            continue

        lower_name = clean_name.lower()

        if clean_name in all_tables:
            resolved[clean_name] = clean_name
        elif lower_name in table_map:
            resolved[clean_name] = table_map[lower_name]

    return resolved


def _filter_columns_in_table_metadata(
    table_metadata: Dict[str, Any],
    selected_columns: Optional[List[str]] = None,
    strict_columns: bool = False,
) -> Dict[str, Any]:
    """
    Return a deep-copied table metadata object with only the requested columns preserved.

    If selected_columns is empty/None, keep all columns.
    """
    metadata_copy = deepcopy(table_metadata)
    columns = metadata_copy.get("columns", {})

    if not isinstance(columns, dict):
        metadata_copy["columns"] = {}
        return metadata_copy

    if not selected_columns:
        return metadata_copy

    real_columns_map = {
        str(column_name).strip().lower(): column_name
        for column_name in columns.keys()
    }

    resolved_columns: List[str] = []
    missing_columns: List[str] = []

    for raw_col in selected_columns:
        clean_col = str(raw_col).strip()
        if not clean_col:
            continue

        if clean_col in columns:
            resolved_columns.append(clean_col)
            continue

        lower_col = clean_col.lower()
        if lower_col in real_columns_map:
            resolved_columns.append(real_columns_map[lower_col])
        else:
            missing_columns.append(clean_col)

    if strict_columns and missing_columns:
        available = ", ".join(sorted(columns.keys()))
        missing = ", ".join(missing_columns)
        raise SchemaLoaderError(
            f"Requested column(s) not found: {missing}. Available columns: {available}"
        )

    resolved_columns = list(dict.fromkeys(resolved_columns))
    metadata_copy["columns"] = {
        column_name: columns[column_name]
        for column_name in resolved_columns
        if column_name in columns
    }

    return metadata_copy


# ------------------------------------------
# PUBLIC LOADERS
# ------------------------------------------
def load_full_schema_document(schema_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load and validate the entire schema document, preserving every field.
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
    """
    schema_doc = load_full_schema_document(schema_path=schema_path)
    all_tables = schema_doc["tables"]

    if not table_names:
        selected_tables = deepcopy(all_tables)
    else:
        selected_tables = {}
        requested_names = [str(name).strip() for name in table_names if str(name).strip()]
        resolved_map = _resolve_requested_table_names(requested_names, all_tables)

        missing_tables = [name for name in requested_names if name not in resolved_map]

        for requested_name, real_name in resolved_map.items():
            selected_tables[real_name] = deepcopy(all_tables[real_name])

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


def load_selected_schema(
    selected_tables: List[str],
    selected_columns: Optional[Dict[str, List[str]]] = None,
    schema_path: Optional[str] = None,
    strict_tables: bool = True,
    strict_columns: bool = False,
) -> Dict[str, Any]:
    """
    Load schema for selected tables and optionally filter to selected columns.

    Example:
        load_selected_schema(
            selected_tables=["login_mast"],
            selected_columns={"login_mast": ["emp_id", "login_date", "login_time"]}
        )
    """
    base_schema = load_schema(
        table_names=selected_tables,
        schema_path=schema_path,
        include_meta=False,
        strict=strict_tables,
    )

    if not selected_columns:
        return base_schema

    output: Dict[str, Any] = {}
    for table_name, metadata in base_schema.items():
        columns_for_table = selected_columns.get(table_name, [])
        output[table_name] = _filter_columns_in_table_metadata(
            table_metadata=metadata,
            selected_columns=columns_for_table,
            strict_columns=strict_columns,
        )

    return output


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
    return next(iter(schema.values()))


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
    selected_columns: Optional[Dict[str, List[str]]] = None,
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
    """
    selected_tables = load_selected_schema(
        selected_tables=table_names,
        selected_columns=selected_columns,
        schema_path=schema_path,
        strict_tables=True,
        strict_columns=False,
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