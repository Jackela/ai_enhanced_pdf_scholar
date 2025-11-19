"""Password validation protocol and result types.

This module defines the core protocol for composable password validators,
following the Strategy pattern to reduce cyclomatic complexity.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ValidationResult:
    """Result of a password validation check.

    Attributes:
        is_valid: Whether the validation passed
        errors: List of validation error messages
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        """Create a successful validation result.

        Returns:
            ValidationResult with is_valid=True and no errors
        """
        return cls(is_valid=True, errors=[])

    @classmethod
    def fail(cls, error: str) -> "ValidationResult":
        """Create a failed validation result with an error message.

        Args:
            error: The validation error message

        Returns:
            ValidationResult with is_valid=False and the error message
        """
        return cls(is_valid=False, errors=[error])


class PasswordValidator(Protocol):
    """Protocol for password validation strategies.

    This protocol defines the interface that all password validators must implement.
    Each validator checks a specific aspect of password strength (length, character
    classes, common passwords, patterns, etc.) and can be composed together.

    Example:
        ```python
        class LengthValidator:
            def __init__(self, min_length: int = 8):
                self.min_length = min_length

            def validate(self, password: str) -> ValidationResult:
                if len(password) < self.min_length:
                    return ValidationResult.fail(
                        f"Password must be at least {self.min_length} characters"
                    )
                return ValidationResult.ok()


        # Use the validator
        validator = LengthValidator(min_length=10)
        result = validator.validate("short")
        if not result.is_valid:
            print(result.errors)  # ["Password must be at least 10 characters"]
        ```
    """

    def validate(self, password: str) -> ValidationResult:
        """Validate a password against this validator's rules.

        Args:
            password: The password to validate

        Returns:
            ValidationResult indicating success or failure with error messages
        """
        ...


# Concrete validator implementations


class LengthValidator:
    """Validates password length constraints.

    Checks that password meets minimum and maximum length requirements.
    """

    def __init__(self, min_length: int = 8, max_length: int = 128):
        """Initialize length validator.

        Args:
            min_length: Minimum password length (default: 8)
            max_length: Maximum password length (default: 128)
        """
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, password: str) -> ValidationResult:
        """Validate password length.

        Args:
            password: Password to validate

        Returns:
            ValidationResult with length validation errors if any
        """
        errors = []

        if len(password) < self.min_length:
            errors.append(
                f"Password must be at least {self.min_length} characters long"
            )

        if len(password) > self.max_length:
            errors.append(
                f"Password must be no more than {self.max_length} characters long"
            )

        return ValidationResult.ok() if not errors else ValidationResult(False, errors)


class CharacterClassValidator:
    """Validates password character class requirements.

    Checks for presence of uppercase, lowercase, digits, and special characters.
    """

    def __init__(
        self,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True,
        special_chars: str = "!@#$%^&*()_+-=[]{}|;:,.<>?",
    ):
        """Initialize character class validator.

        Args:
            require_uppercase: Require at least one uppercase letter
            require_lowercase: Require at least one lowercase letter
            require_digit: Require at least one digit
            require_special: Require at least one special character
            special_chars: String of allowed special characters
        """
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special
        self.special_chars = special_chars

    def validate(self, password: str) -> ValidationResult:
        """Validate character class requirements.

        Args:
            password: Password to validate

        Returns:
            ValidationResult with character class errors if any
        """
        errors = []

        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if self.require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        if self.require_special and not any(c in self.special_chars for c in password):
            errors.append(
                f"Password must contain at least one special character: {self.special_chars}"
            )

        return ValidationResult.ok() if not errors else ValidationResult(False, errors)


class CommonPasswordValidator:
    """Validates password is not in the common passwords list.

    Checks password against a set of commonly used (and therefore weak) passwords.
    """

    def __init__(self, common_passwords: set[str]):
        """Initialize common password validator.

        Args:
            common_passwords: Set of common passwords to block (case-insensitive)
        """
        # Ensure all common passwords are stored in lowercase for case-insensitive matching
        self.common_passwords = {pwd.lower() for pwd in common_passwords}

    def validate(self, password: str) -> ValidationResult:
        """Validate password is not common.

        Args:
            password: Password to validate

        Returns:
            ValidationResult indicating if password is common
        """
        if password.lower() in self.common_passwords:
            return ValidationResult.fail("Password is too common and easily guessable")
        return ValidationResult.ok()


class PatternValidator:
    """Validates password does not contain problematic patterns.

    Checks for sequential characters (abc, 123, qwerty) and excessive
    repeated characters (aaa, 111).
    """

    def __init__(self, max_sequential: int = 3, max_repeats: int = 2):
        """Initialize pattern validator.

        Args:
            max_sequential: Maximum allowed sequential characters (default: 3)
            max_repeats: Maximum allowed consecutive repeated characters (default: 2)
        """
        self.max_sequential = max_sequential
        self.max_repeats = max_repeats
        self.sequences = [
            "abcdefghijklmnopqrstuvwxyz",
            "0123456789",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
        ]

    def validate(self, password: str) -> ValidationResult:
        """Validate password does not contain problematic patterns.

        Args:
            password: Password to validate

        Returns:
            ValidationResult with pattern validation errors if any
        """
        errors = []

        if self._has_sequential_chars(password):
            errors.append("Password contains too many sequential characters")

        if self._has_excessive_repeats(password):
            errors.append("Password contains too many repeated characters")

        return ValidationResult.ok() if not errors else ValidationResult(False, errors)

    def _has_sequential_chars(self, password: str) -> bool:
        """Check if password has too many sequential characters.

        Args:
            password: Password to check

        Returns:
            True if has excessive sequential characters
        """
        password_lower = password.lower()

        for seq in self.sequences:
            for i in range(len(seq) - self.max_sequential + 1):
                # Check forward sequence
                if seq[i : i + self.max_sequential + 1] in password_lower:
                    return True
                # Check reverse sequence
                if seq[i : i + self.max_sequential + 1][::-1] in password_lower:
                    return True

        return False

    def _has_excessive_repeats(self, password: str) -> bool:
        """Check if password has too many repeated characters.

        Args:
            password: Password to check

        Returns:
            True if has excessive repeated characters
        """
        count = 1
        prev_char = None

        for char in password:
            if char == prev_char:
                count += 1
                if count > self.max_repeats:
                    return True
            else:
                count = 1
            prev_char = char

        return False
