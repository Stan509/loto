import logging
from django.core.mail import get_connection, EmailMessage
from accounts.models import SMTPSettings

logger = logging.getLogger(__name__)

def send_custom_email(subject, body, to_emails, html_message=None):
    """
    Sends an email using database-configured SMTP settings (Namecheap, etc.)
    Falls back to settings.py backend if no active SMTPSettings are found.
    """
    if isinstance(to_emails, str):
        to_emails = [to_emails]

    smtp = SMTPSettings.objects.filter(is_active=True).first()
    
    if not smtp or not smtp.smtp_host:
        # Fallback to default Django connection
        logger.info("Using default Django email backend fallback.")
        from django.conf import settings
        connection = get_connection()
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gaboom509.com'),
            to=to_emails,
            connection=connection,
        )
        if html_message:
            email.content_subtype = "html"
            email.body = html_message
        email.send()
        return True

    # Use database-configured SMTP settings
    try:
        logger.info(f"Using SMTP settings from database: host={smtp.smtp_host}, user={smtp.smtp_username}")
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=smtp.smtp_host,
            port=smtp.smtp_port,
            username=smtp.smtp_username,
            password=smtp.smtp_password,
            use_tls=smtp.smtp_use_tls,
            use_ssl=smtp.smtp_use_ssl,
            timeout=10,
        )
        
        from_email = smtp.from_email or smtp.smtp_username or 'no-reply@gaboom509.com'
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=to_emails,
            connection=connection,
        )
        if html_message:
            email.content_subtype = "html"
            email.body = html_message
            
        email.send()
        logger.info(f"Email sent successfully to {to_emails}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via SMTP settings: {str(e)}", exc_info=True)
        # Try to fall back to default Django configuration to prevent complete failure
        try:
            logger.info("Retrying email send with default fallback connection.")
            from django.conf import settings
            connection = get_connection()
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gaboom509.com'),
                to=to_emails,
                connection=connection,
            )
            if html_message:
                email.content_subtype = "html"
                email.body = html_message
            email.send()
            return True
        except Exception as fallback_err:
            logger.critical(f"Email send and fallback both failed: {str(fallback_err)}")
            return False
