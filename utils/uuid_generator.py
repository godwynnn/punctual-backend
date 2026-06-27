import secrets
import string


def generate_custom_id(length=20):
    """Generate a random alphanumeric ID of specified length."""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))