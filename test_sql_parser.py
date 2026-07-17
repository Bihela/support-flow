"""
Tests for app/sql_parser.py — Query Lab SQL parser module.
"""

import pytest
from app.sql_parser import (
    extract_schema,
    detect_parameters,
    is_select_only,
    validate_query,
)


# ===================================================================
# extract_schema tests
# ===================================================================

class TestExtractSchema:
    """Tests for extract_schema()."""

    def test_simple_select_with_quoted_identifiers(self):
        sql = '''SELECT "Name", "Age" FROM "Users"'''
        result = extract_schema(sql)
        assert "Users" in result["tables"]
        assert "Name" in result["tables"]["Users"]
        assert "Age" in result["tables"]["Users"]

    def test_select_star_not_in_columns(self):
        sql = 'SELECT * FROM public."CSDB_CallCDRs"'
        result = extract_schema(sql)
        assert "CSDB_CallCDRs" in result["tables"]
        # * should NOT appear as a column
        assert "*" not in result["tables"]["CSDB_CallCDRs"]

    def test_schema_qualified_names(self):
        sql = '''SELECT "Col1" FROM public."MyTable"'''
        result = extract_schema(sql)
        # Should extract "MyTable", not "public.MyTable"
        assert "MyTable" in result["tables"]
        assert "Col1" in result["tables"]["MyTable"]

    def test_complex_query_with_joins(self):
        sql = '''
        SELECT a."Id", b."Name"
        FROM "Orders" a
        JOIN "Customers" b ON a."CustomerId" = b."Id"
        '''
        result = extract_schema(sql)
        assert "Orders" in result["tables"]
        assert "Customers" in result["tables"]
        assert "Id" in result["tables"]["Orders"]
        assert "Name" in result["tables"]["Customers"]

    def test_subquery_extraction(self):
        """The main example query from the task brief."""
        sql = '''
        SELECT *
        FROM public."CSDB_CallCDRs"
        WHERE "CreatedTime" >= '2025-03-09 00:00:00+05:30'
        AND "CreatedTime" <= '2025-03-09 23:59:59+05:30'
        AND "DVPCallDirection" = 'inbound'
        AND "Uuid" NOT IN (SELECT "Uuid"
            FROM public."CSDB_CallCDRProcesseds"
            WHERE "CreatedTime" >= '2025-03-09 00:00:00+05:30'
            AND "CreatedTime" <= '2025-03-09 23:59:59+05:30'
            AND "DVPCallDirection" = 'inbound'
            ORDER BY "CreatedTime")
        '''
        result = extract_schema(sql)
        assert "CSDB_CallCDRs" in result["tables"]
        assert "CSDB_CallCDRProcesseds" in result["tables"]
        # Both tables should have these columns
        for table in ["CSDB_CallCDRs", "CSDB_CallCDRProcesseds"]:
            assert "CreatedTime" in result["tables"][table]
            assert "DVPCallDirection" in result["tables"][table]
            assert "Uuid" in result["tables"][table]

    def test_backtick_wrapped_sql(self):
        sql = '`SELECT "Name" FROM "Users"`'
        result = extract_schema(sql)
        assert "Users" in result["tables"]
        assert "Name" in result["tables"]["Users"]

    def test_empty_input(self):
        assert extract_schema("") == {"tables": {}}
        assert extract_schema("   ") == {"tables": {}}
        assert extract_schema(None) == {"tables": {}}

    def test_where_column_extraction(self):
        sql = '''SELECT "Id" FROM "Orders" WHERE "Status" = 'active' '''
        result = extract_schema(sql)
        assert "Orders" in result["tables"]
        assert "Id" in result["tables"]["Orders"]
        assert "Status" in result["tables"]["Orders"]

    def test_order_by_column_extraction(self):
        sql = '''SELECT "Name" FROM "Users" ORDER BY "CreatedAt"'''
        result = extract_schema(sql)
        assert "CreatedAt" in result["tables"]["Users"]

    def test_group_by_column_extraction(self):
        sql = '''SELECT "Department", COUNT("Id") FROM "Employees" GROUP BY "Department"'''
        result = extract_schema(sql)
        assert "Department" in result["tables"]["Employees"]


# ===================================================================
# detect_parameters tests
# ===================================================================

class TestDetectParameters:
    """Tests for detect_parameters()."""

    def test_date_detection(self):
        sql = '''SELECT * FROM t WHERE created >= '2025-03-09 00:00:00+05:30' '''
        params = detect_parameters(sql)
        dates = [p for p in params if p["type"] == "date"]
        assert len(dates) >= 1
        assert "2025-03-09 00:00:00+05:30" in dates[0]["value"]

    def test_date_only(self):
        sql = "SELECT * FROM t WHERE dt = '2025-01-15'"
        params = detect_parameters(sql)
        dates = [p for p in params if p["type"] == "date"]
        assert len(dates) == 1
        assert dates[0]["value"] == "2025-01-15"

    def test_numeric_id_list(self):
        sql = "SELECT * FROM t WHERE id IN (6, 24, 25, 26, 27, 28)"
        params = detect_parameters(sql)
        id_lists = [p for p in params if p["type"] == "id_list"]
        assert len(id_lists) == 1
        assert "6" in id_lists[0]["value"]
        assert "28" in id_lists[0]["value"]

    def test_string_literal(self):
        sql = """SELECT * FROM t WHERE direction = 'inbound'"""
        params = detect_parameters(sql)
        strings = [p for p in params if p["type"] == "string"]
        assert len(strings) >= 1
        assert any(p["value"] == "inbound" for p in strings)

    def test_positions_are_correct(self):
        sql = "SELECT * FROM t WHERE name = 'hello'"
        params = detect_parameters(sql)
        for p in params:
            # The value between start and end in the original SQL should
            # contain the detected value
            snippet = sql[p["start"]:p["end"]]
            assert p["value"] in snippet or snippet in f"'{p['value']}'"

    def test_standalone_numeric(self):
        sql = "SELECT * FROM t WHERE status = 1"
        params = detect_parameters(sql)
        nums = [p for p in params if p["type"] == "number"]
        assert len(nums) >= 1
        assert nums[0]["value"] == "1"

    def test_empty_input(self):
        assert detect_parameters("") == []
        assert detect_parameters(None) == []

    def test_multiple_dates(self):
        sql = '''
        SELECT * FROM t
        WHERE created >= '2025-03-09 00:00:00+05:30'
        AND created <= '2025-03-09 23:59:59+05:30'
        '''
        params = detect_parameters(sql)
        dates = [p for p in params if p["type"] == "date"]
        assert len(dates) == 2


# ===================================================================
# is_select_only tests
# ===================================================================

class TestIsSelectOnly:
    """Tests for is_select_only()."""

    def test_simple_select(self):
        assert is_select_only("SELECT * FROM users") is True

    def test_select_with_where(self):
        assert is_select_only("SELECT id FROM users WHERE active = 1") is True

    def test_with_cte_select(self):
        sql = """
        WITH active_users AS (
            SELECT id FROM users WHERE active = 1
        )
        SELECT * FROM active_users
        """
        assert is_select_only(sql) is True

    def test_rejects_insert(self):
        assert is_select_only("INSERT INTO users (name) VALUES ('test')") is False

    def test_rejects_update(self):
        assert is_select_only("UPDATE users SET name = 'test'") is False

    def test_rejects_delete(self):
        assert is_select_only("DELETE FROM users") is False

    def test_rejects_drop(self):
        assert is_select_only("DROP TABLE users") is False

    def test_rejects_alter(self):
        assert is_select_only("ALTER TABLE users ADD COLUMN age INT") is False

    def test_rejects_create(self):
        assert is_select_only("CREATE TABLE users (id INT)") is False

    def test_rejects_truncate(self):
        assert is_select_only("TRUNCATE TABLE users") is False

    def test_rejects_multiple_statements_with_write(self):
        assert is_select_only("SELECT 1; DROP TABLE users;") is False

    def test_handles_leading_whitespace(self):
        assert is_select_only("   \n  SELECT * FROM users") is True

    def test_handles_comments(self):
        assert is_select_only("-- comment\nSELECT * FROM users") is True

    def test_handles_block_comments(self):
        assert is_select_only("/* block comment */ SELECT * FROM users") is True

    def test_case_insensitive(self):
        assert is_select_only("select * from users") is True
        assert is_select_only("Select * From Users") is True

    def test_empty_input(self):
        assert is_select_only("") is False
        assert is_select_only(None) is False

    def test_backtick_wrapped(self):
        assert is_select_only("`SELECT * FROM users`") is True


# ===================================================================
# validate_query tests
# ===================================================================

class TestValidateQuery:
    """Tests for validate_query()."""

    @pytest.fixture
    def known_schema(self):
        return {
            "tables": {
                "Users": {"columns": ["Id", "Name", "Email"]},
                "Orders": {"columns": ["Id", "UserId", "Total"]},
            }
        }

    def test_known_tables_pass(self, known_schema):
        sql = 'SELECT "Name" FROM "Users"'
        result = validate_query(sql, known_schema)
        assert result["valid"] is True
        assert result["is_select_only"] is True
        assert len(result["errors"]) == 0

    def test_unknown_table_error(self, known_schema):
        sql = 'SELECT "Col" FROM "UnknownTable"'
        result = validate_query(sql, known_schema)
        assert result["valid"] is False
        assert any("Unknown table" in e for e in result["errors"])

    def test_unknown_column_warning(self, known_schema):
        sql = 'SELECT "UnknownCol" FROM "Users"'
        result = validate_query(sql, known_schema)
        # Should still be valid (column warnings, not errors)
        assert result["valid"] is True
        assert any("Unknown column" in w for w in result["warnings"])

    def test_non_select_invalid(self, known_schema):
        sql = 'INSERT INTO "Users" ("Name") VALUES (\'test\')'
        result = validate_query(sql, known_schema)
        assert result["valid"] is False
        assert result["is_select_only"] is False

    def test_tables_found_populated(self, known_schema):
        sql = 'SELECT "Name" FROM "Users"'
        result = validate_query(sql, known_schema)
        assert "Users" in result["tables_found"]

    def test_columns_found_populated(self, known_schema):
        sql = 'SELECT "Name", "Email" FROM "Users"'
        result = validate_query(sql, known_schema)
        assert "Name" in result["columns_found"]
        assert "Email" in result["columns_found"]

    def test_empty_query(self, known_schema):
        result = validate_query("", known_schema)
        assert result["valid"] is False
        assert "Empty query" in result["errors"]
