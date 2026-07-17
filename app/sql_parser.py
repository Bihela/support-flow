"""
SQL Parser Module for Query Lab.

Extracts schema knowledge from SQL query strings, detects parameterizable
values, validates queries against known schemas, and enforces read-only access.
"""

from __future__ import annotations

import re
from typing import Any

import sqlparse
from sqlparse.sql import (
    Comparison,
    Function,
    Identifier,
    IdentifierList,
    Parenthesis,
    Where,
)
from sqlparse.tokens import Keyword, DML, Punctuation, Wildcard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_backtick_wrapper(sql: str) -> str:
    """Remove surrounding backticks from a SQL string if present."""
    s = sql.strip()
    if s.startswith("`") and s.endswith("`"):
        s = s[1:-1].strip()
    return s


def _unquote_identifier(name: str) -> str:
    """Remove surrounding double-quotes or backticks from an identifier."""
    if len(name) >= 2:
        if (name[0] == '"' and name[-1] == '"') or (name[0] == '`' and name[-1] == '`'):
            return name[1:-1]
    return name


def _resolve_name(identifier_token) -> tuple[str | None, str | None]:
    """
    Given an sqlparse Identifier token, return (table_name, column_name).

    Rules:
    - schema.table  → (table, None)
    - table.column  → (None, column)  — but we can't know without context
    - plain name    → depends on context

    This helper resolves *table-like* identifiers from FROM/JOIN clauses.
    """
    real_name = identifier_token.get_real_name()
    if real_name:
        return _unquote_identifier(real_name), None
    return None, None


def _extract_table_name(identifier_token) -> str | None:
    """Extract a clean table name from an Identifier, handling schema qualification."""
    if isinstance(identifier_token, Identifier):
        # Check for subquery in FROM — the identifier wraps a Parenthesis
        for child in identifier_token.tokens:
            if isinstance(child, Parenthesis):
                return None  # subquery alias, not a real table

        real_name = identifier_token.get_real_name()
        if real_name:
            return _unquote_identifier(real_name)
    return None


# ---------------------------------------------------------------------------
# Core: extract_schema
# ---------------------------------------------------------------------------

def _collect_tables_and_columns(parsed) -> dict[str, set[str]]:
    """Walk a parsed statement and collect tables + columns."""
    tables: dict[str, set[str]] = {}
    _found_tables: list[str] = []

    def _add_table(name: str) -> None:
        if name and name not in tables:
            tables[name] = set()
        if name:
            _found_tables.append(name)

    def _add_column(name: str) -> None:
        if name and name != "*":
            # Attach to the most recently seen table, or first table
            # We'll do a simpler approach: just collect columns globally
            # and attach later
            pass

    # --- Table extraction ---
    def _extract_tables_from_token(token_list):
        """Extract tables from FROM and JOIN clauses."""
        expect_table = False
        for token in token_list.tokens:
            # Recurse into subqueries and parenthesised groups
            if isinstance(token, Parenthesis):
                _walk_parenthesis(token)
                continue

            if isinstance(token, Where):
                _extract_columns_from_where(token)
                continue

            ttype = token.ttype

            if ttype is Keyword and token.normalized in (
                "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
                "FULL JOIN", "CROSS JOIN", "LEFT OUTER JOIN",
                "RIGHT OUTER JOIN", "FULL OUTER JOIN", "NATURAL JOIN",
            ):
                expect_table = True
                continue

            if expect_table:
                if isinstance(token, IdentifierList):
                    for ident in token.get_identifiers():
                        if isinstance(ident, Identifier):
                            name = _extract_table_name(ident)
                            if name:
                                _add_table(name)
                            # Check for subquery inside identifier
                            for child in ident.tokens:
                                if isinstance(child, Parenthesis):
                                    _walk_parenthesis(child)
                    expect_table = False
                elif isinstance(token, Identifier):
                    name = _extract_table_name(token)
                    if name:
                        _add_table(name)
                    # Check for subquery inside identifier
                    for child in token.tokens:
                        if isinstance(child, Parenthesis):
                            _walk_parenthesis(child)
                    expect_table = False
                elif isinstance(token, Parenthesis):
                    _walk_parenthesis(token)
                    expect_table = False
                elif ttype is not Punctuation:
                    # Some other keyword encountered, stop expecting table
                    if ttype is Keyword or ttype is DML:
                        expect_table = False

            # Recurse into sub-tokens that aren't basic types
            if hasattr(token, 'tokens') and not isinstance(token, (Where, Identifier, IdentifierList, Parenthesis)):
                _extract_tables_from_token(token)

    def _walk_parenthesis(paren_token):
        """Recurse into parenthesised subqueries."""
        # First, check if the parenthesis content is a full subquery
        inner_text = paren_token.value
        if inner_text.startswith('(') and inner_text.endswith(')'):
            inner_sql = inner_text[1:-1].strip()
            if inner_sql.upper().startswith('SELECT'):
                # Parse the subquery as standalone SQL
                sub_parsed = sqlparse.parse(inner_sql)
                for sub_stmt in sub_parsed:
                    _extract_tables_from_token(sub_stmt)
                    _extract_columns_from_statement(sub_stmt)
                return

        for child in paren_token.tokens:
            if hasattr(child, 'tokens'):
                if child.ttype is DML:
                    continue
                _extract_tables_from_token(child)
                _extract_columns_from_statement(child)
            if isinstance(child, Parenthesis):
                _walk_parenthesis(child)

    # --- Column extraction ---
    all_columns: set[str] = set()

    def _add_col(name: str) -> None:
        name = _unquote_identifier(name.strip())
        if name and name != "*":
            all_columns.add(name)

    def _extract_column_from_identifier(ident):
        """Extract a column name from an Identifier in SELECT / WHERE etc."""
        if isinstance(ident, Identifier):
            # Skip function calls — we want the arguments inside
            for child in ident.tokens:
                if isinstance(child, Function):
                    _extract_columns_from_function(child)
                    return
                if isinstance(child, Parenthesis):
                    # Subquery — recurse
                    _walk_parenthesis(child)
                    return

            real_name = ident.get_real_name()
            if real_name:
                real_name = _unquote_identifier(real_name)
                if real_name != "*":
                    _add_col(real_name)

    def _extract_columns_from_function(func_token):
        """Extract column refs inside function calls like COUNT(col)."""
        for token in func_token.tokens:
            if isinstance(token, Parenthesis):
                for child in token.tokens:
                    if isinstance(child, IdentifierList):
                        for ident in child.get_identifiers():
                            _extract_column_from_identifier(ident)
                    elif isinstance(child, Identifier):
                        _extract_column_from_identifier(child)
            elif isinstance(token, Identifier):
                _extract_column_from_identifier(token)

    def _extract_columns_from_where(where_token):
        """Extract column references from a WHERE clause."""
        for token in where_token.tokens:
            if isinstance(token, Comparison):
                for child in token.tokens:
                    if isinstance(child, Identifier):
                        _extract_column_from_identifier(child)
                    elif isinstance(child, Parenthesis):
                        _walk_parenthesis(child)
            elif isinstance(token, Identifier):
                _extract_column_from_identifier(token)
            elif isinstance(token, Parenthesis):
                _walk_parenthesis(token)
            elif hasattr(token, 'tokens'):
                _extract_columns_from_where(token)

    def _extract_columns_from_statement(stmt):
        """Extract columns from SELECT, ORDER BY, GROUP BY, HAVING."""
        in_select = False
        in_order_group_having = False

        for token in stmt.tokens:
            ttype = token.ttype

            if ttype is DML and token.normalized == "SELECT":
                in_select = True
                in_order_group_having = False
                continue

            if ttype is Keyword and token.normalized in ("FROM", "JOIN", "INNER JOIN",
                                                          "LEFT JOIN", "RIGHT JOIN",
                                                          "FULL JOIN", "INTO"):
                in_select = False
                in_order_group_having = False
                continue

            if ttype is Keyword and token.normalized in ("ORDER BY", "GROUP BY", "HAVING"):
                in_order_group_having = True
                in_select = False
                continue

            if isinstance(token, Where):
                _extract_columns_from_where(token)
                continue

            if in_select or in_order_group_having:
                if isinstance(token, IdentifierList):
                    for ident in token.get_identifiers():
                        if isinstance(ident, Identifier):
                            _extract_column_from_identifier(ident)
                        elif hasattr(ident, 'ttype') and ident.ttype is Wildcard:
                            pass  # skip *
                elif isinstance(token, Identifier):
                    _extract_column_from_identifier(token)
                elif isinstance(token, Function):
                    _extract_columns_from_function(token)
                elif hasattr(token, 'ttype') and token.ttype is Wildcard:
                    pass  # skip *

            # Recurse into Parenthesis for subqueries
            if isinstance(token, Parenthesis):
                _walk_parenthesis(token)

    # --- Run extraction ---
    for stmt in parsed:
        _extract_tables_from_token(stmt)
        _extract_columns_from_statement(stmt)

    # --- Assign columns to tables ---
    # If there's only one table, all columns belong to it.
    # If multiple, assign based on dot-qualified names or distribute to all.
    # We collect dot-qualified info from the raw SQL as a fallback.
    if tables:
        if len(tables) == 1:
            tname = next(iter(tables))
            tables[tname] = all_columns
        else:
            # Distribute all columns to all tables (schema knowledge is partial).
            # A column may belong to any table — we can't always tell without
            # real schema info, so we add each column to every table that
            # could own it. For correctness, we add to all.
            for tname in tables:
                tables[tname] = set(all_columns)

    return tables


def extract_schema(sql: str) -> dict[str, Any]:
    """
    Parse SQL and return extracted schema information.

    Returns:
        ``{"tables": {"table_name": ["col1", "col2", ...]}}``
    """
    if not sql or not sql.strip():
        return {"tables": {}}

    sql = _strip_backtick_wrapper(sql)
    parsed = sqlparse.parse(sql)

    tables = _collect_tables_and_columns(parsed)

    # Convert sets to sorted lists for deterministic output
    return {
        "tables": {
            tname: sorted(cols) for tname, cols in tables.items()
        }
    }


# ---------------------------------------------------------------------------
# Core: detect_parameters
# ---------------------------------------------------------------------------

# Date patterns: 'YYYY-MM-DD' with optional time and timezone
_DATE_RE = re.compile(
    r"'(\d{4}-\d{2}-\d{2}"           # YYYY-MM-DD
    r"(?:\s+\d{2}:\d{2}:\d{2})?"     # optional HH:MM:SS
    r"(?:[+-]\d{2}:\d{2})?)"         # optional timezone
    r"'"
)

# Numeric ID list in IN (...) — matches IN (1, 2, 3) or IN ('1', '2')
_IN_LIST_RE = re.compile(
    r"\bIN\s*\(\s*"
    r"("
    r"(?:'?\d+'?\s*,\s*)*'?\d+'?"    # comma-separated numbers, optionally quoted
    r")"
    r"\s*\)",
    re.IGNORECASE,
)

# String literals in single quotes (non-date)
_STRING_LITERAL_RE = re.compile(r"'([^']*)'")

# Standalone numeric comparison: = 1, > 42, etc.
_NUMERIC_CMP_RE = re.compile(
    r"(?:=|!=|<>|>=|<=|>|<)\s*(\d+(?:\.\d+)?)\b"
)


def detect_parameters(sql: str) -> list[dict[str, Any]]:
    """
    Find parameterizable values in the SQL with type and position.

    Returns a list of dicts with keys: type, value, start, end.
    """
    if not sql or not sql.strip():
        return []

    sql = _strip_backtick_wrapper(sql)
    params: list[dict[str, Any]] = []
    seen_ranges: set[tuple[int, int]] = set()

    def _overlaps(start: int, end: int) -> bool:
        for s, e in seen_ranges:
            if start < e and end > s:
                return True
        return False

    def _add(ptype: str, value: str, start: int, end: int) -> None:
        if not _overlaps(start, end):
            params.append({"type": ptype, "value": value, "start": start, "end": end})
            seen_ranges.add((start, end))

    # 1. Detect dates first (most specific)
    for m in _DATE_RE.finditer(sql):
        _add("date", m.group(1), m.start(), m.end())

    # 2. Detect IN (...) numeric lists
    for m in _IN_LIST_RE.finditer(sql):
        # Check if this is a subquery IN (SELECT ...)
        inner = m.group(1).strip()
        if inner.upper().startswith("SELECT"):
            continue
        # Clean up: remove quotes
        cleaned = inner.replace("'", "")
        # Make sure it's actually numeric
        parts = [p.strip() for p in cleaned.split(",")]
        if all(re.match(r"^\d+$", p) for p in parts if p):
            value = ", ".join(parts)
            # Position: the content inside parentheses
            content_start = m.start(1)
            content_end = m.end(1)
            _add("id_list", value, content_start, content_end)

    # 3. Detect remaining string literals (non-date)
    for m in _STRING_LITERAL_RE.finditer(sql):
        value = m.group(1)
        # Skip if already captured as date
        if _overlaps(m.start(), m.end()):
            continue
        # Skip empty strings
        if not value.strip():
            continue
        # Skip if looks like a date
        if re.match(r"^\d{4}-\d{2}-\d{2}", value):
            continue
        _add("string", value, m.start(), m.end())

    # 4. Detect standalone numeric comparisons
    for m in _NUMERIC_CMP_RE.finditer(sql):
        value = m.group(1)
        val_start = m.start(1)
        val_end = m.end(1)
        if not _overlaps(val_start, val_end):
            _add("number", value, val_start, val_end)

    # Sort by position
    params.sort(key=lambda p: p["start"])
    return params


# ---------------------------------------------------------------------------
# Core: is_select_only
# ---------------------------------------------------------------------------

_WRITE_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "GRANT", "REVOKE",
}


def is_select_only(sql: str) -> bool:
    """
    Check if the SQL is read-only (SELECT or WITH ... SELECT only).

    Returns False for any DML/DDL that modifies data.
    """
    if not sql or not sql.strip():
        return False

    sql = _strip_backtick_wrapper(sql)
    parsed = sqlparse.parse(sql)

    if not parsed:
        return False

    for stmt in parsed:
        # Skip empty statements (e.g. trailing semicolons)
        if not stmt.tokens or str(stmt).strip() == "":
            continue

        # Get the first meaningful token (skip whitespace/comments)
        first_keyword = None
        for token in stmt.flatten():
            if token.ttype in (Keyword, DML) or (
                token.ttype is not None and token.ttype in sqlparse.tokens.Keyword
            ):
                first_keyword = token.normalized.upper()
                break
            # Skip whitespace, comments, newlines
            if token.is_whitespace or token.ttype in (
                sqlparse.tokens.Comment.Single,
                sqlparse.tokens.Comment.Multiline,
                sqlparse.tokens.Newline,
                sqlparse.tokens.Whitespace,
            ):
                continue
            # If we hit a non-whitespace, non-keyword token first, suspicious
            first_keyword = token.normalized.upper() if hasattr(token, 'normalized') else str(token).upper()
            break

        if first_keyword is None:
            continue

        if first_keyword == "SELECT":
            continue
        elif first_keyword == "WITH":
            # CTE — make sure it eventually does a SELECT
            # Check if any DML token in the statement is a write keyword
            has_select = False
            has_write = False
            for token in stmt.flatten():
                if token.ttype is DML:
                    word = token.normalized.upper()
                    if word == "SELECT":
                        has_select = True
                    elif word in _WRITE_KEYWORDS:
                        has_write = True
            if has_write or not has_select:
                return False
            continue
        elif first_keyword in _WRITE_KEYWORDS:
            return False
        else:
            # Unknown first keyword — check if it's a write keyword
            if first_keyword in _WRITE_KEYWORDS:
                return False
            # Could be a comment-prefixed SELECT — dig deeper
            has_dml = False
            for token in stmt.flatten():
                if token.ttype is DML:
                    word = token.normalized.upper()
                    if word == "SELECT":
                        has_dml = True
                        break
                    elif word in _WRITE_KEYWORDS:
                        return False
            if not has_dml:
                return False

    return True


# ---------------------------------------------------------------------------
# Core: validate_query
# ---------------------------------------------------------------------------

def validate_query(sql: str, known_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a query against a known schema map.

    Args:
        sql: The SQL query string.
        known_schema: Schema dict in format
            ``{"tables": {"TableName": {"columns": ["col1", "col2"]}}}``

    Returns:
        Dict with keys: valid, is_select_only, errors, warnings,
        tables_found, columns_found.
    """
    result: dict[str, Any] = {
        "valid": False,
        "is_select_only": False,
        "errors": [],
        "warnings": [],
        "tables_found": [],
        "columns_found": [],
    }

    if not sql or not sql.strip():
        result["errors"].append("Empty query")
        return result

    # Check read-only
    select_only = is_select_only(sql)
    result["is_select_only"] = select_only
    if not select_only:
        result["errors"].append("Query is not read-only (SELECT only)")

    # Extract schema from the query
    schema = extract_schema(sql)
    query_tables = list(schema.get("tables", {}).keys())
    result["tables_found"] = query_tables

    # Collect all columns from extracted schema
    query_columns: list[str] = []
    for cols in schema.get("tables", {}).values():
        for col in cols:
            if col not in query_columns:
                query_columns.append(col)
    result["columns_found"] = query_columns

    # Validate tables against known schema
    known_tables = known_schema.get("tables", {})
    for table in query_tables:
        if table not in known_tables:
            result["errors"].append(f"Unknown table: {table}")

    # Validate columns against known schema
    known_columns: set[str] = set()
    for table in query_tables:
        if table in known_tables:
            table_info = known_tables[table]
            if isinstance(table_info, dict):
                known_columns.update(table_info.get("columns", []))
            elif isinstance(table_info, list):
                known_columns.update(table_info)

    for col in query_columns:
        if col not in known_columns:
            result["warnings"].append(f"Unknown column: {col}")

    # Valid only if select-only AND no table errors
    table_errors = [e for e in result["errors"] if e.startswith("Unknown table:")]
    non_select_errors = [e for e in result["errors"] if "not read-only" in e]
    result["valid"] = select_only and len(table_errors) == 0 and len(non_select_errors) == 0

    return result
