"""Unit tests for password validator protocol and result types."""

import pytest

from backend.api.auth.validators import (
    CharacterClassValidator,
    CommonPasswordValidator,
    LengthValidator,
    PasswordValidator,
    PatternValidator,
    ValidationResult,
)


def test_validation_result_ok():
    """Test ValidationResult.ok() creates a successful result."""
    result = ValidationResult.ok()
    assert result.is_valid is True
    assert result.errors == []


def test_validation_result_fail():
    """Test ValidationResult.fail() creates a failed result with error."""
    error_msg = "Password is too short"
    result = ValidationResult.fail(error_msg)
    assert result.is_valid is False
    assert result.errors == [error_msg]


def test_validation_result_constructor():
    """Test ValidationResult can be constructed directly."""
    result = ValidationResult(is_valid=True, errors=["warning1", "warning2"])
    assert result.is_valid is True
    assert result.errors == ["warning1", "warning2"]


def test_validation_result_default_errors():
    """Test ValidationResult uses empty list as default for errors."""
    result = ValidationResult(is_valid=True)
    assert result.errors == []


def test_password_validator_protocol_conformance():
    """Test that a class conforming to PasswordValidator protocol works correctly."""

    class TestValidator:
        """Simple validator for testing protocol conformance."""

        def validate(self, password: str) -> ValidationResult:
            if len(password) < 5:
                return ValidationResult.fail("Too short")
            return ValidationResult.ok()

    # This should work because TestValidator conforms to the protocol
    validator: PasswordValidator = TestValidator()

    # Test valid password
    result = validator.validate("longpassword")
    assert result.is_valid is True

    # Test invalid password
    result = validator.validate("abc")
    assert result.is_valid is False
    assert "Too short" in result.errors


def test_protocol_type_checking():
    """Test that protocol can be used for type hints."""

    def check_password_with_validator(
        password: str, validator: PasswordValidator
    ) -> bool:
        """Helper function that uses the protocol for type hinting."""
        result = validator.validate(password)
        return result.is_valid

    class DummyValidator:
        def validate(self, password: str) -> ValidationResult:
            return ValidationResult.ok()

    # This should work with any object that implements the protocol
    result = check_password_with_validator("test", DummyValidator())
    assert result is True


# LengthValidator tests


def test_length_validator_valid_password():
    """Test LengthValidator accepts valid password length."""
    validator = LengthValidator(min_length=8, max_length=128)
    result = validator.validate("ValidPass123!")
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_length_validator_too_short():
    """Test LengthValidator rejects too short passwords."""
    validator = LengthValidator(min_length=8)
    result = validator.validate("short")
    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "at least 8 characters" in result.errors[0]


def test_length_validator_too_long():
    """Test LengthValidator rejects too long passwords."""
    validator = LengthValidator(max_length=16)
    result = validator.validate("ThisPasswordIsWayTooLong12345")
    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "no more than 16 characters" in result.errors[0]


def test_length_validator_custom_limits():
    """Test LengthValidator with custom min/max limits."""
    validator = LengthValidator(min_length=10, max_length=20)

    # Too short
    result = validator.validate("short")
    assert not result.is_valid
    assert "at least 10" in result.errors[0]

    # Just right
    result = validator.validate("GoodLength12")
    assert result.is_valid

    # Too long
    result = validator.validate("WayTooLongPassword12345678")
    assert not result.is_valid
    assert "no more than 20" in result.errors[0]


# CharacterClassValidator tests


def test_character_class_validator_valid_password():
    """Test CharacterClassValidator accepts password with all requirements."""
    validator = CharacterClassValidator()
    result = validator.validate("ValidPass123!")
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_character_class_validator_missing_uppercase():
    """Test CharacterClassValidator rejects password without uppercase."""
    validator = CharacterClassValidator()
    result = validator.validate("lowercase123!")
    assert result.is_valid is False
    assert any("uppercase" in err for err in result.errors)


def test_character_class_validator_missing_lowercase():
    """Test CharacterClassValidator rejects password without lowercase."""
    validator = CharacterClassValidator()
    result = validator.validate("UPPERCASE123!")
    assert result.is_valid is False
    assert any("lowercase" in err for err in result.errors)


def test_character_class_validator_missing_digit():
    """Test CharacterClassValidator rejects password without digit."""
    validator = CharacterClassValidator()
    result = validator.validate("NoDigitsHere!")
    assert result.is_valid is False
    assert any("digit" in err for err in result.errors)


def test_character_class_validator_missing_special():
    """Test CharacterClassValidator rejects password without special char."""
    validator = CharacterClassValidator()
    result = validator.validate("NoSpecial123")
    assert result.is_valid is False
    assert any("special character" in err for err in result.errors)


def test_character_class_validator_multiple_missing():
    """Test CharacterClassValidator reports multiple missing requirements."""
    validator = CharacterClassValidator()
    result = validator.validate("alllowercase")
    assert result.is_valid is False
    assert len(result.errors) >= 2  # Missing uppercase, digit, and special


def test_character_class_validator_optional_requirements():
    """Test CharacterClassValidator with optional requirements disabled."""
    validator = CharacterClassValidator(require_uppercase=False, require_special=False)
    # Only lowercase and digits required
    result = validator.validate("lowercase123")
    assert result.is_valid is True


# CommonPasswordValidator tests


def test_common_password_validator_blocks_common():
    """Test CommonPasswordValidator blocks common passwords."""
    common_set = {"password", "123456", "qwerty"}
    validator = CommonPasswordValidator(common_set)

    result = validator.validate("password")
    assert result.is_valid is False
    assert "too common" in result.errors[0]


def test_common_password_validator_case_insensitive():
    """Test CommonPasswordValidator is case-insensitive."""
    # Common passwords should be stored in lowercase
    common_set = {"password", "qwerty", "123456"}
    validator = CommonPasswordValidator(common_set)

    # All case variations should be blocked
    for pwd in ["password", "PASSWORD", "PasSWoRd", "QWERTY", "qWeRtY", "123456"]:
        result = validator.validate(pwd)
        assert result.is_valid is False, f"Expected {pwd} to be invalid"


def test_common_password_validator_accepts_unique():
    """Test CommonPasswordValidator accepts unique passwords."""
    common_set = {"password", "123456"}
    validator = CommonPasswordValidator(common_set)

    result = validator.validate("UniqueP@ssw0rd!")
    assert result.is_valid is True


# PatternValidator tests


def test_pattern_validator_valid_password():
    """Test PatternValidator accepts password without patterns."""
    validator = PatternValidator()
    result = validator.validate("R@nd0mP@ss!")
    assert result.is_valid is True


def test_pattern_validator_detects_sequential_abc():
    """Test PatternValidator detects alphabetic sequences."""
    validator = PatternValidator(max_sequential=3)

    # abcd is 4 sequential characters (exceeds max of 3)
    result = validator.validate("Passabcd123!")
    assert result.is_valid is False
    assert any("sequential" in err for err in result.errors)


def test_pattern_validator_detects_sequential_numbers():
    """Test PatternValidator detects numeric sequences."""
    validator = PatternValidator(max_sequential=3)

    # 12345 contains sequential numbers
    result = validator.validate("Pass12345!")
    assert result.is_valid is False
    assert any("sequential" in err for err in result.errors)


def test_pattern_validator_detects_qwerty():
    """Test PatternValidator detects QWERTY keyboard sequences."""
    validator = PatternValidator(max_sequential=3)

    # qwerty contains sequential keyboard characters
    result = validator.validate("Passqwerty123!")
    assert result.is_valid is False


def test_pattern_validator_detects_reverse_sequence():
    """Test PatternValidator detects reverse sequences."""
    validator = PatternValidator(max_sequential=3)

    # dcba is reverse alphabetic sequence
    result = validator.validate("Passdcba123!")
    assert result.is_valid is False


def test_pattern_validator_detects_repeated_chars():
    """Test PatternValidator detects excessive repeated characters."""
    validator = PatternValidator(max_repeats=2)

    # aaaa exceeds max_repeats of 2
    result = validator.validate("Passaaaa123!")
    assert result.is_valid is False
    assert any("repeated" in err for err in result.errors)


def test_pattern_validator_allows_limited_repeats():
    """Test PatternValidator allows limited repeated characters."""
    validator = PatternValidator(max_repeats=2)

    # aa is acceptable (doesn't exceed max_repeats)
    result = validator.validate("Passaa123!")
    assert result.is_valid is True


def test_pattern_validator_custom_thresholds():
    """Test PatternValidator with custom thresholds."""
    # More lenient validator
    validator = PatternValidator(max_sequential=5, max_repeats=4)

    # abcd would be blocked by default but allowed here
    result = validator.validate("Passabcd123!")
    assert result.is_valid is True

    # But 6+ sequential still blocked
    result = validator.validate("Passabcdef!")
    assert result.is_valid is False
