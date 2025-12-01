from cryptography.fernet import Fernet
from flask import current_app
import base64

class SecurityService:
    @staticmethod
    def _get_cipher():
        """
        Lazy-load the cipher suite using the current app configuration.
        """
        key = current_app.config.get('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY is missing in config.")
        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)

    @staticmethod
    def encrypt(value):
        """Encrypts a string value."""
        if not value:
            return None
        try:
            cipher = SecurityService._get_cipher()
            # Fernet requires bytes
            encrypted_bytes = cipher.encrypt(value.encode('utf-8'))
            # Store as base64 string for database compatibility
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            print(f"Encryption Error: {e}")
            return None

    @staticmethod
    def decrypt(encrypted_value):
        """Decrypts a string value."""
        if not encrypted_value:
            return None
        try:
            cipher = SecurityService._get_cipher()
            # Decode base64 wrapper -> get bytes -> decrypt
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value)
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            print(f"Decryption Error: {e}")
            return None