"""
Security and privacy protection
"""

import re
import hashlib
import secrets
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet
from urllib.parse import urlparse, quote
import bleach
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    enable_encryption: bool = True
    enable_sanitization: bool = True
    enable_privacy: bool = True
    allowed_domains: List[str] = None
    blocked_patterns: List[str] = None
    pii_patterns: List[str] = None


class SecurityManager:
    """Comprehensive security management."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.encryptor = DataEncryptor() if config.enable_encryption else None
        self.sanitizer = InputSanitizer() if config.enable_sanitization else None
        self.privacy_protector = PrivacyProtector() if config.enable_privacy else None
    
    def sanitize_input(self, user_input: str) -> str:
        """Sanitize user input to prevent attacks."""
        if not self.config.enable_sanitization:
            return user_input
        
        return self.sanitizer.sanitize(user_input)
    
    def validate_url(self, url: str) -> bool:
        """Validate URL for safety."""
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Check against allowed domains if configured
            if self.config.allowed_domains:
                if parsed.netloc not in self.config.allowed_domains:
                    return False
            
            # Check for suspicious patterns
            if self.config.blocked_patterns:
                for pattern in self.config.blocked_patterns:
                    if re.search(pattern, url):
                        return False
            
            return True
            
        except Exception:
            return False
    
    def protect_privacy(self, data: Any) -> Any:
        """Remove or mask PII from data."""
        if not self.config.enable_privacy:
            return data
        
        return self.privacy_protector.anonymize(data)
    
    def encrypt_sensitive(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not self.config.enable_encryption:
            return data
        
        return self.encryptor.encrypt(data)
    
    def decrypt_sensitive(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not self.config.enable_encryption:
            return encrypted_data
        
        return self.encryptor.decrypt(encrypted_data)


class InputSanitizer:
    """Input sanitization to prevent injection attacks."""
    
    def __init__(self):
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)",
            r"(--|\*|;|\/\*|\*\/|xp_|sp_|0x)",
            r"(\bOR\b.*=.*)",
            r"(\bAND\b.*=.*)"
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>"
        ]
    
    def sanitize(self, text: str) -> str:
        """Sanitize input text."""
        if not text:
            return text
        
        # Remove SQL injection patterns
        for pattern in self.sql_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        
        # Remove XSS patterns
        for pattern in self.xss_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        
        # Use bleach for HTML sanitization
        text = bleach.clean(text, tags=[], strip=True)
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Limit length to prevent buffer overflow
        max_length = 10000
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        # Remove path components
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Remove special characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + '.' + ext if ext else name[:255]
        
        return filename


class DataEncryptor:
    """Data encryption for sensitive information."""
    
    def __init__(self):
        # In production, load key from secure storage
        self.key = self._get_or_create_key()
        self.cipher_suite = Fernet(self.key)
    
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key from environment."""
        import os
        import base64
        
        k = os.getenv("RESEARCH_ENCRYPTION_KEY", "").strip()
        if not k:
            raise RuntimeError("RESEARCH_ENCRYPTION_KEY not set (must be a Fernet key)")
        try:
            # Accept raw or base64
            return k.encode() if k.startswith("gAAAA") else base64.urlsafe_b64decode(k)
        except Exception as e:
            raise RuntimeError("Invalid RESEARCH_ENCRYPTION_KEY") from e
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()


class PrivacyProtector:
    """Privacy protection through PII detection and anonymization."""
    
    def __init__(self):
        # PII patterns
        self.pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'ip_address': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        }
    
    def detect_pii(self, text: str) -> Dict[str, List[str]]:
        """Detect PII in text."""
        detected = {}
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                detected[pii_type] = matches
        
        return detected
    
    def anonymize(self, data: Any) -> Any:
        """Anonymize PII in data."""
        if isinstance(data, str):
            return self._anonymize_text(data)
        elif isinstance(data, dict):
            return {k: self.anonymize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.anonymize(item) for item in data]
        else:
            return data
    
    def _anonymize_text(self, text: str) -> str:
        """Anonymize PII in text."""
        # Replace emails
        text = re.sub(
            self.pii_patterns['email'],
            '[EMAIL_REDACTED]',
            text
        )
        
        # Replace phone numbers
        text = re.sub(
            self.pii_patterns['phone'],
            '[PHONE_REDACTED]',
            text
        )
        
        # Replace SSNs
        text = re.sub(
            self.pii_patterns['ssn'],
            '[SSN_REDACTED]',
            text
        )
        
        # Replace credit cards
        text = re.sub(
            self.pii_patterns['credit_card'],
            '[CC_REDACTED]',
            text
        )
        
        # Replace IP addresses
        text = re.sub(
            self.pii_patterns['ip_address'],
            '[IP_REDACTED]',
            text
        )
        
        return text
    
    def hash_pii(self, pii_value: str) -> str:
        """Create consistent hash of PII for tracking without storing."""
        return hashlib.sha256(pii_value.encode()).hexdigest()[:16]