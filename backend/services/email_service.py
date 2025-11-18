"""
Email Service
Handles sending transactional emails for authentication and notifications.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from backend.core.secrets import secrets_manager

logger = logging.getLogger(__name__)


class EmailConfig:
    """Email configuration settings."""

    def __init__(self):
        """Initialize email configuration from environment/secrets."""
        self.smtp_host = os.getenv("SMTP_HOST", "localhost")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.from_email = os.getenv("FROM_EMAIL", "noreply@example.com")
        self.from_name = os.getenv("FROM_NAME", "AI Enhanced PDF Scholar")

        # Use secrets manager if available
        try:
            if secrets_manager.is_initialized():
                smtp_secrets = secrets_manager.get_secret("smtp")
                if smtp_secrets:
                    self.smtp_host = smtp_secrets.get("host", self.smtp_host)
                    self.smtp_port = smtp_secrets.get("port", self.smtp_port)
                    self.smtp_user = smtp_secrets.get("user", self.smtp_user)
                    self.smtp_password = smtp_secrets.get(
                        "password", self.smtp_password
                    )
        except Exception as e:
            logger.warning(f"Could not load email secrets: {e}")

    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


class EmailTemplate:
    """Email template with HTML and text versions."""

    def __init__(self, subject: str, html_body: str, text_body: str):
        self.subject = subject
        self.html_body = html_body
        self.text_body = text_body

    def render(self, **kwargs: Any) -> "EmailTemplate":
        """Render template with variables."""
        return EmailTemplate(
            subject=self.subject.format(**kwargs),
            html_body=self.html_body.format(**kwargs),
            text_body=self.text_body.format(**kwargs),
        )


class EmailService:
    """Service for sending transactional emails."""

    def __init__(self, config: EmailConfig | None = None):
        """Initialize email service with configuration."""
        self.config = config or EmailConfig()
        self.templates = self._load_templates()

        if not self.config.is_configured:
            logger.warning("Email service is not configured - emails will be simulated")

    def _load_templates(self) -> dict[str, EmailTemplate]:
        """Load email templates."""
        return {
            "verification": EmailTemplate(
                subject="Verify your email address - {app_name}",
                html_body="""
                <html>
                <body>
                    <h2>Welcome to {app_name}!</h2>
                    <p>Hi {username},</p>
                    <p>Thank you for registering with {app_name}. To complete your registration,
                       please verify your email address by clicking the link below:</p>
                    <p><a href="{verification_url}">Verify Email Address</a></p>
                    <p>This link will expire in {expiry_hours} hours.</p>
                    <p>If you didn't create this account, please ignore this email.</p>
                    <p>Best regards,<br>The {app_name} Team</p>
                </body>
                </html>
                """,
                text_body="""
                Welcome to {app_name}!

                Hi {username},

                Thank you for registering with {app_name}. To complete your registration,
                please verify your email address by visiting this link:

                {verification_url}

                This link will expire in {expiry_hours} hours.

                If you didn't create this account, please ignore this email.

                Best regards,
                The {app_name} Team
                """,
            ),
            "password_reset": EmailTemplate(
                subject="Password Reset Request - {app_name}",
                html_body="""
                <html>
                <body>
                    <h2>Password Reset Request</h2>
                    <p>Hi {username},</p>
                    <p>We received a request to reset your password for {app_name}.</p>
                    <p>Click the link below to reset your password:</p>
                    <p><a href="{reset_url}">Reset Password</a></p>
                    <p>This link will expire in {expiry_hours} hours.</p>
                    <p>If you didn't request this password reset, please ignore this email
                       or contact support if you have concerns.</p>
                    <p>Best regards,<br>The {app_name} Team</p>
                </body>
                </html>
                """,
                text_body="""
                Password Reset Request

                Hi {username},

                We received a request to reset your password for {app_name}.

                Visit this link to reset your password:
                {reset_url}

                This link will expire in {expiry_hours} hours.

                If you didn't request this password reset, please ignore this email
                or contact support if you have concerns.

                Best regards,
                The {app_name} Team
                """,
            ),
            "welcome": EmailTemplate(
                subject="Welcome to {app_name}!",
                html_body="""
                <html>
                <body>
                    <h2>Welcome to {app_name}!</h2>
                    <p>Hi {username},</p>
                    <p>Your email has been verified successfully. Welcome to {app_name}!</p>
                    <p>You can now start uploading and analyzing PDF documents using our
                       AI-powered tools.</p>
                    <p>If you have any questions, please don't hesitate to contact our support team.</p>
                    <p>Best regards,<br>The {app_name} Team</p>
                </body>
                </html>
                """,
                text_body="""
                Welcome to {app_name}!

                Hi {username},

                Your email has been verified successfully. Welcome to {app_name}!

                You can now start uploading and analyzing PDF documents using our
                AI-powered tools.

                If you have any questions, please don't hesitate to contact our support team.

                Best regards,
                The {app_name} Team
                """,
            ),
        }

    def send_verification_email(
        self,
        email: str,
        username: str,
        verification_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """
        Send email verification email.

        Args:
            email: Recipient email address
            username: User's username
            verification_token: Email verification token
            base_url: Application base URL

        Returns:
            True if sent successfully, False otherwise
        """
        verification_url = f"{base_url}/auth/verify-email?token={verification_token}"

        template = self.templates["verification"].render(
            app_name="AI Enhanced PDF Scholar",
            username=username,
            verification_url=verification_url,
            expiry_hours=24,
        )

        return self._send_email(
            to_email=email,
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
        )

    def send_password_reset_email(
        self,
        email: str,
        username: str,
        reset_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """
        Send password reset email.

        Args:
            email: Recipient email address
            username: User's username
            reset_token: Password reset token
            base_url: Application base URL

        Returns:
            True if sent successfully, False otherwise
        """
        reset_url = f"{base_url}/auth/reset-password?token={reset_token}"

        template = self.templates["password_reset"].render(
            app_name="AI Enhanced PDF Scholar",
            username=username,
            reset_url=reset_url,
            expiry_hours=2,
        )

        return self._send_email(
            to_email=email,
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
        )

    def send_welcome_email(self, email: str, username: str) -> bool:
        """
        Send welcome email after email verification.

        Args:
            email: Recipient email address
            username: User's username

        Returns:
            True if sent successfully, False otherwise
        """
        template = self.templates["welcome"].render(
            app_name="AI Enhanced PDF Scholar", username=username
        )

        return self._send_email(
            to_email=email,
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
        )

    def _send_email(
        self, to_email: str, subject: str, html_body: str, text_body: str
    ) -> bool:
        """
        Send email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML version of email body
            text_body: Plain text version of email body

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.config.is_configured:
            # Simulate sending for development/testing
            logger.info(f"[EMAIL SIMULATION] To: {to_email}, Subject: {subject}")
            logger.debug(f"[EMAIL SIMULATION] Body: {text_body[:200]}...")
            return True

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = to_email

            # Attach text and HTML parts
            text_part = MIMEText(text_body, "plain", "utf-8")
            html_part = MIMEText(html_body, "html", "utf-8")

            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()

                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)

                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False


# Global email service instance
email_service = EmailService()
