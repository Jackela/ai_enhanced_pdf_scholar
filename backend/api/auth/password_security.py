"""
Password Security Module
Handles password hashing, verification, and security policies.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import bcrypt


class PasswordHasher:
    """
    Secure password hashing using bcrypt with salt.
    """

    # Bcrypt configuration
    DEFAULT_ROUNDS = 12  # Cost factor (2^12 iterations)
    MAX_PASSWORD_LENGTH = 72  # Bcrypt limitation

    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Hash a password using bcrypt with salt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        # Bcrypt has a maximum password length of 72 bytes
        if len(password.encode('utf-8')) > cls.MAX_PASSWORD_LENGTH:
            # Hash long passwords with SHA256 first
            password = hashlib.sha256(password.encode('utf-8')).hexdigest()

        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=cls.DEFAULT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)

        return hashed.decode('utf-8')

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Stored password hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            # Handle long passwords same as in hash_password
            if len(plain_password.encode('utf-8')) > cls.MAX_PASSWORD_LENGTH:
                plain_password = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()

            # Verify password
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            # Invalid hash format or other error
            return False

    @classmethod
    def needs_rehash(cls, hashed_password: str, rounds: int = DEFAULT_ROUNDS) -> bool:
        """
        Check if a password hash needs to be updated (different cost factor).

        Args:
            hashed_password: Current password hash
            rounds: Desired cost factor

        Returns:
            True if rehashing is recommended
        """
        try:
            # Extract the cost factor from the hash
            hash_info = hashed_password.encode('utf-8')
            current_rounds = int(hash_info.split(b'$')[2])
            return current_rounds != rounds
        except Exception:
            return True


class PasswordPolicy:
    """
    Password policy enforcement and validation.
    """

    # Policy configuration
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Password history
    PASSWORD_HISTORY_COUNT = 5  # Remember last 5 passwords
    PASSWORD_MIN_AGE_DAYS = 1  # Minimum days before password can be changed
    PASSWORD_MAX_AGE_DAYS = 90  # Maximum password age

    # Common passwords to block
    COMMON_PASSWORDS = {
        "password", "123456", "password123", "12345678", "qwerty",
        "abc123", "monkey", "1234567", "letmein", "trustno1",
        "dragon", "baseball", "111111", "iloveyou", "master",
        "sunshine", "ashley", "bailey", "passw0rd", "shadow",
        "123123", "654321", "superman", "qazwsx", "michael",
        "football", "password1", "password123", "welcome", "admin"
    }

    @classmethod
    def validate_password_strength(cls, password: str, username: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate password against security policy.

        Args:
            password: Password to validate
            username: Username to check against (optional)

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Length checks
        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters long")

        if len(password) > cls.MAX_LENGTH:
            errors.append(f"Password must be no more than {cls.MAX_LENGTH} characters long")

        # Character requirements
        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if cls.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        if cls.REQUIRE_SPECIAL and not any(c in cls.SPECIAL_CHARS for c in password):
            errors.append(f"Password must contain at least one special character: {cls.SPECIAL_CHARS}")

        # Common password check
        if password.lower() in cls.COMMON_PASSWORDS:
            errors.append("Password is too common and easily guessable")

        # Username similarity check
        if username:
            username_lower = username.lower()
            password_lower = password.lower()

            # Check if password contains username
            if username_lower in password_lower:
                errors.append("Password cannot contain your username")

            # Check if password is too similar to username
            if cls._calculate_similarity(username_lower, password_lower) > 0.7:
                errors.append("Password is too similar to your username")

        # Check for sequential characters
        if cls._has_sequential_chars(password):
            errors.append("Password contains too many sequential characters")

        # Check for repeated characters
        if cls._has_excessive_repeats(password):
            errors.append("Password contains too many repeated characters")

        return len(errors) == 0, errors

    @staticmethod
    def _calculate_similarity(str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using Levenshtein distance.

        Returns:
            Similarity score between 0 and 1
        """
        if not str1 or not str2:
            return 0.0

        # Simple similarity calculation
        longer = max(len(str1), len(str2))
        if longer == 0:
            return 1.0

        # Count matching characters
        matches = sum(1 for a, b in zip(str1, str2) if a == b)
        return matches / longer

    @staticmethod
    def _has_sequential_chars(password: str, max_sequential: int = 3) -> bool:
        """
        Check if password has too many sequential characters.

        Args:
            password: Password to check
            max_sequential: Maximum allowed sequential characters

        Returns:
            True if has excessive sequential characters
        """
        sequences = [
            "abcdefghijklmnopqrstuvwxyz",
            "0123456789",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm"
        ]

        password_lower = password.lower()

        for seq in sequences:
            for i in range(len(seq) - max_sequential + 1):
                if seq[i:i + max_sequential + 1] in password_lower:
                    return True
                # Check reverse
                if seq[i:i + max_sequential + 1][::-1] in password_lower:
                    return True

        return False

    @staticmethod
    def _has_excessive_repeats(password: str, max_repeats: int = 2) -> bool:
        """
        Check if password has too many repeated characters.

        Args:
            password: Password to check
            max_repeats: Maximum allowed consecutive repeats

        Returns:
            True if has excessive repeated characters
        """
        count = 1
        prev_char = None

        for char in password:
            if char == prev_char:
                count += 1
                if count > max_repeats:
                    return True
            else:
                count = 1
                prev_char = char

        return False

    @classmethod
    def check_password_history(cls, new_password: str, password_history: List[str]) -> bool:
        """
        Check if password was recently used.

        Args:
            new_password: New password to check
            password_history: List of previous password hashes

        Returns:
            True if password is acceptable (not in history)
        """
        for old_hash in password_history[-cls.PASSWORD_HISTORY_COUNT:]:
            if PasswordHasher.verify_password(new_password, old_hash):
                return False
        return True

    @classmethod
    def check_password_age(cls, last_changed: Optional[datetime]) -> Tuple[bool, str]:
        """
        Check if password has reached minimum or maximum age.

        Args:
            last_changed: When password was last changed

        Returns:
            Tuple of (can_change, message)
        """
        if not last_changed:
            return True, "Password can be changed"

        now = datetime.utcnow()
        age_days = (now - last_changed).days

        # Check minimum age
        if age_days < cls.PASSWORD_MIN_AGE_DAYS:
            hours_remaining = (cls.PASSWORD_MIN_AGE_DAYS * 24) - ((now - last_changed).total_seconds() / 3600)
            return False, f"Password cannot be changed for another {hours_remaining:.1f} hours"

        # Check maximum age
        if age_days > cls.PASSWORD_MAX_AGE_DAYS:
            return True, "Password has expired and must be changed"

        return True, "Password can be changed"

    @classmethod
    def generate_strong_password(cls, length: int = 16) -> str:
        """
        Generate a strong random password.

        Args:
            length: Password length (default 16)

        Returns:
            Strong random password
        """
        if length < cls.MIN_LENGTH:
            length = cls.MIN_LENGTH
        if length > cls.MAX_LENGTH:
            length = cls.MAX_LENGTH

        # Character sets
        uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        lowercase = "abcdefghijklmnopqrstuvwxyz"
        digits = "0123456789"
        special = cls.SPECIAL_CHARS

        # Ensure at least one of each required character type
        password = []

        if cls.REQUIRE_UPPERCASE:
            password.append(secrets.choice(uppercase))
        if cls.REQUIRE_LOWERCASE:
            password.append(secrets.choice(lowercase))
        if cls.REQUIRE_DIGIT:
            password.append(secrets.choice(digits))
        if cls.REQUIRE_SPECIAL:
            password.append(secrets.choice(special))

        # Fill remaining length with random characters
        all_chars = uppercase + lowercase + digits + special
        for _ in range(length - len(password)):
            password.append(secrets.choice(all_chars))

        # Shuffle to avoid predictable patterns
        secrets.SystemRandom().shuffle(password)

        return ''.join(password)


class AccountLockoutPolicy:
    """
    Account lockout policy for brute force protection.
    """

    # Lockout configuration
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    LOCKOUT_RESET_WINDOW_MINUTES = 15  # Reset counter after this time of no attempts

    @classmethod
    def should_lock_account(cls, failed_attempts: int) -> bool:
        """
        Check if account should be locked.

        Args:
            failed_attempts: Number of consecutive failed login attempts

        Returns:
            True if account should be locked
        """
        return failed_attempts >= cls.MAX_FAILED_ATTEMPTS

    @classmethod
    def get_lockout_duration(cls, failed_attempts: int) -> int:
        """
        Get lockout duration based on failed attempts.
        Implements progressive lockout (doubles each time).

        Args:
            failed_attempts: Number of failed attempts

        Returns:
            Lockout duration in minutes
        """
        if failed_attempts < cls.MAX_FAILED_ATTEMPTS:
            return 0

        # Progressive lockout: doubles for each set of max attempts
        lockout_multiplier = ((failed_attempts - 1) // cls.MAX_FAILED_ATTEMPTS) + 1
        duration = cls.LOCKOUT_DURATION_MINUTES * (2 ** (lockout_multiplier - 1))

        # Cap at 24 hours
        return min(duration, 1440)

    @classmethod
    def should_reset_counter(cls, last_failed_attempt: Optional[datetime]) -> bool:
        """
        Check if failed attempt counter should be reset.

        Args:
            last_failed_attempt: Timestamp of last failed attempt

        Returns:
            True if counter should be reset
        """
        if not last_failed_attempt:
            return False

        time_since_last = datetime.utcnow() - last_failed_attempt
        return time_since_last > timedelta(minutes=cls.LOCKOUT_RESET_WINDOW_MINUTES)

    @classmethod
    def get_remaining_lockout_time(cls, locked_until: Optional[datetime]) -> int:
        """
        Get remaining lockout time in seconds.

        Args:
            locked_until: When account lockout expires

        Returns:
            Remaining seconds, 0 if not locked
        """
        if not locked_until:
            return 0

        remaining = (locked_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))