"""
Tests for authentication migration module.
Tests PERF203 refactoring and helper functions.
"""

import logging
from unittest.mock import MagicMock, Mock

import pytest

from backend.api.auth.migration import (
    AuthenticationMigration,
    ExecutionResult,
    execute_sql_statement,
)


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_success_result_has_no_error(self):
        """Test successful result has no error."""
        result = ExecutionResult(success=True)
        assert not result.has_error
        assert result.error_message is None

    def test_error_result_has_error(self):
        """Test error result has error."""
        result = ExecutionResult(success=False, error_message="Test error")
        assert result.has_error
        assert result.error_message == "Test error"

    def test_is_benign_error_matches_pattern(self):
        """Test benign error pattern matching."""
        result = ExecutionResult(
            success=False, error_message="table users already exists"
        )
        assert result.is_benign_error(["already exists"])

    def test_is_benign_error_case_insensitive(self):
        """Test benign error is case insensitive."""
        result = ExecutionResult(
            success=False, error_message="TABLE USERS ALREADY EXISTS"
        )
        assert result.is_benign_error(["already exists"])

    def test_is_benign_error_rejects_non_match(self):
        """Test benign error rejects non-matching patterns."""
        result = ExecutionResult(
            success=False, error_message="syntax error near 'CREATE'"
        )
        assert not result.is_benign_error(["already exists"])

    def test_is_benign_error_multiple_patterns(self):
        """Test benign error with multiple patterns."""
        result = ExecutionResult(
            success=False, error_message="index idx_users already exists"
        )
        patterns = ["already exists", "duplicate"]
        assert result.is_benign_error(patterns)

    def test_is_benign_error_returns_false_for_success(self):
        """Test benign error returns False for successful result."""
        result = ExecutionResult(success=True)
        assert not result.is_benign_error(["already exists"])

    def test_context_is_stored(self):
        """Test that context is properly stored."""
        result = ExecutionResult(
            success=False, error_message="Error", context="CREATE TABLE test"
        )
        assert result.context == "CREATE TABLE test"


class TestExecuteSQLStatement:
    """Test execute_sql_statement wrapper function."""

    def test_successful_execution(self):
        """Test successful SQL execution."""
        mock_db = MagicMock()
        sql = "CREATE TABLE test (id INTEGER)"

        result = execute_sql_statement(mock_db, sql)

        assert result.success
        assert not result.has_error
        mock_db.execute.assert_called_once_with(sql)
        mock_db.commit.assert_called_once()

    def test_execution_with_exception(self):
        """Test SQL execution with exception."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("table already exists")
        sql = "CREATE TABLE test (id INTEGER)"

        result = execute_sql_statement(mock_db, sql)

        assert not result.success
        assert result.has_error
        assert "already exists" in result.error_message

    def test_context_truncation(self):
        """Test that SQL context is truncated to 100 chars."""
        mock_db = MagicMock()
        sql = "CREATE TABLE test (id INTEGER, " + "col VARCHAR(255), " * 50 + ")"

        result = execute_sql_statement(mock_db, sql)

        assert len(result.context) == 100
        assert result.context == sql[:100]

    def test_no_commit_when_disabled(self):
        """Test that commit is skipped when disabled."""
        mock_db = MagicMock()
        sql = "SELECT * FROM users"

        result = execute_sql_statement(mock_db, sql, commit=False)

        assert result.success
        mock_db.execute.assert_called_once_with(sql)
        mock_db.commit.assert_not_called()

    def test_commit_is_called_by_default(self):
        """Test that commit is called by default."""
        mock_db = MagicMock()
        sql = "CREATE TABLE test (id INTEGER)"

        result = execute_sql_statement(mock_db, sql)

        assert result.success
        mock_db.commit.assert_called_once()


class TestAuthenticationMigration:
    """Test AuthenticationMigration.migrate() method."""

    def test_fresh_migration_succeeds(self):
        """Test migration on empty database."""
        mock_db = MagicMock()

        success = AuthenticationMigration.migrate(mock_db)

        assert success
        # Verify all SQL statements executed (should be 24 statements)
        assert mock_db.execute.call_count == 24

    def test_idempotent_migration_succeeds(self):
        """Test re-running migration (already exists errors)."""
        mock_db = MagicMock()
        # Simulate "already exists" errors for all statements
        mock_db.execute.side_effect = [Exception("table users already exists")] * 24

        success = AuthenticationMigration.migrate(mock_db)

        assert success  # Should ignore benign errors

    def test_critical_error_aborts_migration(self):
        """Test migration aborts on syntax error."""
        mock_db = MagicMock()
        # First 4 statements succeed, 5th fails with syntax error
        errors = [None, None, None, None, Exception("syntax error near 'CREATE'")]
        errors.extend([None] * 18)  # Fill remaining
        mock_db.execute.side_effect = errors

        success = AuthenticationMigration.migrate(mock_db)

        assert not success

    def test_mixed_benign_and_critical_errors(self):
        """Test migration with both benign and critical errors."""
        mock_db = MagicMock()
        errors = [
            None,  # Statement 1: success
            Exception("table users already exists"),  # Statement 2: benign
            None,  # Statement 3: success
            Exception("FOREIGN KEY constraint failed"),  # Statement 4: critical
        ]
        errors.extend([None] * 19)  # Fill remaining
        mock_db.execute.side_effect = errors

        success = AuthenticationMigration.migrate(mock_db)

        assert not success  # Should abort on critical error

    def test_error_logging(self, caplog):
        """Test that errors are logged correctly."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = [Exception("syntax error")] * 24

        with caplog.at_level(logging.ERROR):
            success = AuthenticationMigration.migrate(mock_db)

        assert not success
        assert "Migration statement failed" in caplog.text
        assert "syntax error" in caplog.text

    def test_no_logging_for_benign_errors(self, caplog):
        """Test that benign errors don't generate logs."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = [Exception("table already exists")] * 24

        with caplog.at_level(logging.ERROR):
            success = AuthenticationMigration.migrate(mock_db)

        assert success
        assert "Migration statement failed" not in caplog.text

    def test_success_logging(self, caplog):
        """Test that success is logged."""
        mock_db = MagicMock()

        with caplog.at_level(logging.INFO):
            success = AuthenticationMigration.migrate(mock_db)

        assert success
        assert "completed successfully" in caplog.text

    def test_outer_exception_handling(self, caplog):
        """Test outer exception handler catches unexpected errors."""
        mock_db = Mock()
        # Patch get_migration_sql to raise an exception
        original_method = AuthenticationMigration.get_migration_sql
        AuthenticationMigration.get_migration_sql = Mock(
            side_effect=AttributeError("test error")
        )

        try:
            with caplog.at_level(logging.ERROR):
                success = AuthenticationMigration.migrate(mock_db)

            assert not success
            assert "migration failed" in caplog.text.lower()
        finally:
            # Restore original method
            AuthenticationMigration.get_migration_sql = original_method

    def test_all_statements_executed_on_success(self):
        """Test that all 24 SQL statements are executed."""
        mock_db = MagicMock()

        success = AuthenticationMigration.migrate(mock_db)

        assert success
        assert mock_db.execute.call_count == 24
        assert mock_db.commit.call_count == 24


class TestAuthenticationRollback:
    """Test AuthenticationMigration.rollback() method."""

    def test_rollback_succeeds(self):
        """Test rollback on database with tables."""
        mock_db = MagicMock()

        success = AuthenticationMigration.rollback(mock_db)

        assert success
        # Verify all 5 DROP statements executed
        assert mock_db.execute.call_count == 5

    def test_rollback_on_empty_database(self):
        """Test rollback when tables don't exist."""
        mock_db = MagicMock()
        # IF EXISTS clause should prevent errors, but simulate them
        mock_db.execute.side_effect = [Exception("no such table: user_sessions")] * 5

        success = AuthenticationMigration.rollback(mock_db)

        assert success  # Best-effort, continues on errors

    def test_partial_rollback_failure(self):
        """Test rollback when some tables fail to drop."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            None,  # user_sessions: success
            None,  # login_attempts: success
            Exception("table locked"),  # password_history: error
            None,  # refresh_tokens: success
            None,  # users: success
        ]

        success = AuthenticationMigration.rollback(mock_db)

        assert success  # Continues despite error
        # Should have attempted all 5 drops
        assert mock_db.execute.call_count == 5

    def test_rollback_error_logging(self, caplog):
        """Test that rollback errors are logged."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = [Exception("table locked")] * 5

        with caplog.at_level(logging.WARNING):
            success = AuthenticationMigration.rollback(mock_db)

        assert success
        assert "Failed to drop table" in caplog.text

    def test_rollback_success_logging(self, caplog):
        """Test that rollback success is logged."""
        mock_db = MagicMock()

        with caplog.at_level(logging.INFO):
            success = AuthenticationMigration.rollback(mock_db)

        assert success
        assert "rollback completed" in caplog.text

    def test_rollback_all_tables_in_correct_order(self):
        """Test that tables are dropped in correct order (reverse dependency)."""
        mock_db = MagicMock()

        AuthenticationMigration.rollback(mock_db)

        # Verify order: dependent tables first, then parent
        calls = [call[0][0] for call in mock_db.execute.call_args_list]
        assert "DROP TABLE IF EXISTS user_sessions" in calls[0]
        assert "DROP TABLE IF EXISTS users" in calls[4]  # Last

    def test_rollback_commits_each_drop(self):
        """Test that each DROP is committed."""
        mock_db = MagicMock()

        AuthenticationMigration.rollback(mock_db)

        assert mock_db.commit.call_count == 5

    def test_rollback_outer_exception_handling(self, caplog):
        """Test outer exception handler in rollback."""
        mock_db = Mock()
        # Make execute raise on first call, then let commit also fail
        mock_db.execute = Mock(side_effect=RuntimeError("Database connection lost"))
        mock_db.commit = Mock(side_effect=RuntimeError("Database connection lost"))

        # The rollback catches the exception in execute_sql_statement
        # but continues best-effort, so it should still return True
        with caplog.at_level(logging.WARNING):
            success = AuthenticationMigration.rollback(mock_db)

        # Best-effort rollback continues and returns True
        assert success
        # But warnings should be logged
        assert "Failed to drop table" in caplog.text
