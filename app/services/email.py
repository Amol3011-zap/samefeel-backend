"""Transactional email service.

Transport is chosen from environment variables (nothing is hardcoded):

* SMTP  - used when SMTP_HOST is set.
          SMTP_HOST, SMTP_PORT (default 587), SMTP_USERNAME, SMTP_PASSWORD,
          SMTP_FROM_EMAIL, optional SMTP_FROM_NAME (default "SameFeel").
          Port 465 uses implicit TLS; any other port uses STARTTLS.
* Resend - optional fallback, used only when SMTP_HOST is unset and
          RESEND_API_KEY is set (FROM_EMAIL is the sender).

If neither is configured the backend still starts; send methods log a clear
configuration error and return False, and callers carry on (a waitlist signup
never fails because an email could not be sent).
"""

import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional
import html

logger = logging.getLogger("email_service")

CONFIG_HELP = (
    "Email is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, "
    "SMTP_PASSWORD and SMTP_FROM_EMAIL (or RESEND_API_KEY + FROM_EMAIL)."
)


class EmailService:
    """Send emails over SMTP (preferred) or the Resend API (optional fallback)."""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        try:
            self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        except ValueError:
            logger.error("SMTP_PORT is not a number; falling back to 587")
            self.smtp_port = 587
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_name = os.getenv("SMTP_FROM_NAME", "SameFeel")
        self.api_key = os.getenv("RESEND_API_KEY", "").strip()
        self.from_email = (
            os.getenv("SMTP_FROM_EMAIL") or os.getenv("FROM_EMAIL") or ""
        ).strip()
        self.admin_email = os.getenv("ADMIN_EMAIL", "").strip()

        if self.smtp_host:
            self.provider = "smtp"
        elif self.api_key:
            self.provider = "resend"
        else:
            self.provider = None

        if not self.is_configured:
            logger.warning(CONFIG_HELP)

    @property
    def is_configured(self) -> bool:
        return self.provider is not None and bool(self.from_email)

    def config_error(self) -> Optional[str]:
        """Human-readable reason email cannot be sent, or None if it can."""
        if self.provider is None:
            return CONFIG_HELP
        if not self.from_email:
            return "Email sender is not set. Set SMTP_FROM_EMAIL (or FROM_EMAIL)."
        return None

    def _send(self, to_email: str, subject: str, email_html: str) -> bool:
        error = self.config_error()
        if error:
            logger.error("Cannot send email: %s", error)
            return False
        if not to_email:
            logger.error("Cannot send email: no recipient")
            return False
        try:
            if self.provider == "smtp":
                return self._send_smtp(to_email, subject, email_html)
            return self._send_resend(to_email, subject, email_html)
        except Exception as e:  # never let email break the caller
            logger.error("Exception sending email via %s: %s", self.provider, e)
            return False

    def _send_smtp(self, to_email: str, subject: str, email_html: str) -> bool:
        msg = EmailMessage()
        msg["From"] = formataddr((self.from_name, self.from_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content("This message is best viewed in an HTML-capable email client.")
        msg.add_alternative(email_html, subtype="html")

        context = ssl.create_default_context()
        if self.smtp_port == 465:
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15, context=context)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
        with server:
            if self.smtp_port != 465:
                server.starttls(context=context)
            if self.smtp_username:
                server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
        return True

    def _send_resend(self, to_email: str, subject: str, email_html: str) -> bool:
        import httpx

        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "from": formataddr((self.from_name, self.from_email)),
                "to": to_email,
                "subject": subject,
                "html": email_html,
            },
            timeout=10.0,
        )
        if response.status_code in (200, 201):
            return True
        logger.error("Resend rejected email: status %s", response.status_code)
        return False

    def send_welcome_email(self, user_email: str, user_name: Optional[str] = None) -> bool:
        """Send welcome email to new waitlist member."""
        email_html = self._get_welcome_email_html(user_name or "Friend")
        ok = self._send(user_email, "💜 Welcome to the SoulConnect Waitlist", email_html)
        if ok:
            logger.info("Welcome email sent to %s", user_email)
        return ok

    def send_admin_notification(self, user_email: str, user_name: Optional[str] = None, struggle: Optional[str] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        """Send admin notification."""
        if not self.admin_email:
            logger.error("Cannot send admin notification: ADMIN_EMAIL is not set")
            return False
        now = datetime.utcnow()
        email_html = self._get_admin_notification_html(
            user_email, user_name, struggle,
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S UTC"), ip_address, user_agent,
        )
        ok = self._send(self.admin_email, "🎉 New Waitlist Signup", email_html)
        if ok:
            logger.info("Admin notification sent for %s", user_email)
        return ok

    @staticmethod
    def _get_welcome_email_html(user_name: str) -> str:
        """Gmail Android compatible welcome email - CORRECTED VERSION."""
        safe_name = html.escape(str(user_name or "Friend"))

        email_html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>Welcome to SoulConnect</title>
<style type="text/css">
body {{ margin: 0; padding: 0; min-width: 100% !important; }}
img {{ border: 0; outline: 0; text-decoration: none; }}
table {{ border-collapse: collapse; border-spacing: 0; }}
td {{ padding: 0; }}
.ReadMsgBody {{ width: 100%; }}
.ExternalClass {{ width: 100%; }}
@media only screen and (max-width: 480px) {{
  body {{ width: 100% !important; min-width: 100% !important; }}
  table[class="container"] {{ width: 100% !important; }}
  td[class="content"] {{ width: 100% !important; padding: 16px !important; }}
  img[class="banner"] {{ width: 100% !important; height: auto !important; }}
}}
</style>
</head>
<body style="margin: 0; padding: 0; min-width: 100% !important; font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.6; color: #1a1a1a; background-color: #ffffff;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td align="center" style="padding: 0;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="border-collapse: collapse; width: 600px; max-width: 600px;">
<tbody>
<tr>
<td width="600" style="padding: 16px 0; width: 600px; text-align: center; line-height: 0; font-size: 0;">
<img src="https://res.cloudinary.com/lh7xcjvh/image/upload/f_auto,q_auto/ChatGPT_Image_Jul_6_2026_03_22_00_AM_qkzxxu.png" width="560" alt="SoulConnect" style="width: 100%; max-width: 560px; height: auto; display: block; margin: 0 auto; padding: 0; border: 0; outline: 0; text-decoration: none;">
</td>
</tr>
<tr>
<td width="600" style="padding: 0; width: 600px; height: 4px; background-color: #D4AF37; border: 0; line-height: 0; font-size: 0;"></td>
</tr>
<tr>
<td style="padding: 32px 24px; width: 600px; line-height: 1.6; font-size: 14px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td align="center" style="padding: 0; text-align: center;">
<p style="font-size: 40px; line-height: 48px; margin: 0 0 12px 0; text-align: center;">💜</p>
<h1 style="font-size: 28px; font-weight: 700; color: #1a1a1a; margin: 0 0 8px 0; line-height: 1.2; text-align: center; font-family: Arial, Helvetica, sans-serif;">Welcome to SoulConnect</h1>
<p style="font-size: 16px; font-weight: 600; color: #1a1a1a; margin: 0 0 16px 0; line-height: 1.4; text-align: center; font-family: Arial, Helvetica, sans-serif;">Hi {safe_name}! 👋</p>
<p style="font-size: 15px; color: #4a4a4a; margin: 8px 0; line-height: 1.5; text-align: center; font-family: Arial, Helvetica, sans-serif;">Thank you for joining the SoulConnect waitlist.</p>
<p style="font-size: 15px; color: #4a4a4a; margin: 8px 0; line-height: 1.5; text-align: center; font-family: Arial, Helvetica, sans-serif;">You're now part of a community built on one simple belief.</p>
<p style="font-size: 16px; font-style: italic; color: #4B2E83; font-weight: 600; margin: 16px 0 0 0; line-height: 1.6; text-align: center; font-family: Arial, Helvetica, sans-serif;">"You don't have to go through life's challenges alone."</p>
</td>
</tr>
</tbody>
</table>
</td>
</tr>
<tr>
<td style="padding: 24px 24px 32px 24px; width: 600px; line-height: 1.6; font-size: 14px;">
<p style="font-size: 14px; font-weight: 600; color: #4B2E83; margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.4; text-align: center; font-family: Arial, Helvetica, sans-serif;">What you'll get</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td align="center" style="padding: 6px 0; text-align: center;">
<p style="font-size: 14px; color: #1a1a1a; margin: 0; line-height: 1.5; text-align: center; font-family: Arial, Helvetica, sans-serif;">✔ Connect with people who understand</p>
</td>
</tr>
<tr>
<td align="center" style="padding: 6px 0; text-align: center;">
<p style="font-size: 14px; color: #1a1a1a; margin: 0; line-height: 1.5; text-align: center; font-family: Arial, Helvetica, sans-serif;">✔ Daily wellness support</p>
</td>
</tr>
<tr>
<td align="center" style="padding: 6px 0; text-align: center;">
<p style="font-size: 14px; color: #1a1a1a; margin: 0; line-height: 1.5; text-align: center; font-family: Arial, Helvetica, sans-serif;">✔ Access to trusted professionals</p>
</td>
</tr>
</tbody>
</table>
</td>
</tr>
<tr>
<td style="padding: 24px; text-align: center; width: 600px; line-height: 1.6; font-size: 14px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse: collapse; margin: 0 auto;">
<tbody>
<tr>
<td bgcolor="#4B2E83" style="background-color: #4B2E83; padding: 12px 32px; text-align: center; border-radius: 0;">
<a href="https://samefeel.co" style="color: #ffffff; text-decoration: none; font-weight: 600; font-size: 15px; font-family: Arial, Helvetica, sans-serif; display: inline-block; line-height: 1.2;">Visit SoulConnect</a>
</td>
</tr>
</tbody>
</table>
</td>
</tr>
<tr>
<td style="padding: 24px; text-align: center; width: 600px; line-height: 1.6; font-size: 14px;">
<p style="font-size: 14px; color: #4a4a4a; margin: 8px 0; line-height: 1.5; text-align: center; font-family: Arial, Helvetica, sans-serif;">We'll let you know as soon as early access is available.</p>
<p style="font-size: 14px; color: #4a4a4a; margin: 8px 0; line-height: 1.5; text-align: center; font-family: Arial, Helvetica, sans-serif;">Take care of yourself.</p>
<p style="font-size: 24px; line-height: 32px; margin: 12px 0; text-align: center;">💜</p>
<p style="font-size: 14px; color: #4B2E83; font-weight: 600; margin: 8px 0; line-height: 1.4; text-align: center; font-family: Arial, Helvetica, sans-serif;">The SoulConnect Team</p>
</td>
</tr>
</tbody>
</table>
</td>
</tr>
</tbody>
</table>
</body>
</html>"""

        with open("debug_email.html", "w", encoding="utf-8") as f:
            f.write(email_html)

        import subprocess
        import platform
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["start", "debug_email.html"], shell=True)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "debug_email.html"])
            else:
                subprocess.Popen(["xdg-open", "debug_email.html"])
        except Exception as e:
            logger.warning(f"Could not open debug_email.html: {e}")

        return email_html

    @staticmethod
    def _get_admin_notification_html(user_email: str, user_name: Optional[str], struggle: Optional[str], date: str, time: str, ip_address: Optional[str], user_agent: Optional[str]) -> str:
        """Admin notification HTML - Gmail compatible."""
        return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>New Waitlist Signup</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.6; color: #1a1a1a; background-color: #f5f5f5;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td align="center" style="padding: 20px 0;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="border-collapse: collapse; width: 600px; max-width: 600px; background-color: #ffffff;">
<tbody>
<tr bgcolor="#7C3AED" style="background-color: #7C3AED;">
<td align="center" style="padding: 20px; text-align: center;">
<h1 style="margin: 0; font-size: 24px; color: #ffffff; font-family: Arial, Helvetica, sans-serif;">🎉 New Waitlist Signup</h1>
</td>
</tr>
<tr>
<td style="padding: 30px;">
<p style="margin: 0 0 10px 0; color: #7C3AED; font-weight: 600; font-size: 12px; text-transform: uppercase; font-family: Arial, Helvetica, sans-serif;">Email</p>
<p style="margin: 0 0 20px 0; border-bottom: 1px solid #e5e5e5; padding-bottom: 15px; color: #1a1a1a; font-family: Arial, Helvetica, sans-serif;">{html.escape(user_email)}</p>

{f'<p style="margin: 0 0 10px 0; color: #7C3AED; font-weight: 600; font-size: 12px; text-transform: uppercase; font-family: Arial, Helvetica, sans-serif;">Name</p><p style="margin: 0 0 20px 0; border-bottom: 1px solid #e5e5e5; padding-bottom: 15px; color: #1a1a1a; font-family: Arial, Helvetica, sans-serif;">{html.escape(user_name)}</p>' if user_name else ''}

{f'<p style="margin: 0 0 10px 0; color: #7C3AED; font-weight: 600; font-size: 12px; text-transform: uppercase; font-family: Arial, Helvetica, sans-serif;">Struggle</p><p style="margin: 0 0 20px 0; border-bottom: 1px solid #e5e5e5; padding-bottom: 15px; color: #1a1a1a; font-family: Arial, Helvetica, sans-serif;">{html.escape(struggle)}</p>' if struggle else ''}

<p style="margin: 0 0 10px 0; color: #7C3AED; font-weight: 600; font-size: 12px; text-transform: uppercase; font-family: Arial, Helvetica, sans-serif;">Date & Time</p>
<p style="margin: 0 0 20px 0; border-bottom: 1px solid #e5e5e5; padding-bottom: 15px; color: #1a1a1a; font-family: Arial, Helvetica, sans-serif;">{date} at {time}</p>

{f'<p style="margin: 0 0 10px 0; color: #7C3AED; font-weight: 600; font-size: 12px; text-transform: uppercase; font-family: Arial, Helvetica, sans-serif;">IP Address</p><p style="margin: 0 0 20px 0; border-bottom: 1px solid #e5e5e5; padding-bottom: 15px; color: #1a1a1a; font-family: Arial, Helvetica, sans-serif; word-break: break-all;">{html.escape(ip_address)}</p>' if ip_address else ''}
</td>
</tr>
<tr bgcolor="#f9f5ff" style="background-color: #f9f5ff;">
<td align="center" style="padding: 20px; text-align: center; font-size: 12px; color: #4a4a4a; font-family: Arial, Helvetica, sans-serif;">
<p style="margin: 0;">This is an automated notification from SoulConnect.</p>
</td>
</tr>
</tbody>
</table>
</td>
</tr>
</tbody>
</table>
</body>
</html>"""


_email_service = None

def get_email_service() -> EmailService:
    """Get or create email service."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
