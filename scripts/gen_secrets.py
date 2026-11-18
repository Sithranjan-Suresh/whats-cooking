"""Print fresh APP_SECRET (Fernet key) and OWNER_TOKEN values for .env."""
import secrets

from cryptography.fernet import Fernet

print(f"APP_SECRET={Fernet.generate_key().decode()}")
print(f"OWNER_TOKEN={secrets.token_urlsafe(24)}")
