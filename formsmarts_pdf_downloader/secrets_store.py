"""Wrapper around the OS secret store (macOS Keychain, Windows Credential
Locker, or the Linux Secret Service) via the `keyring` package.

The FormSmarts API key is only ever written here. If no OS backend is
available, callers fall back to the (explicitly opt-in) plain-text config
entry in config.py.
"""

SERVICE_NAME = "FormSmarts PDF Downloader"


class KeyringUnavailableError(Exception):
    """Raised when no usable OS secret store backend is found."""


def _keyring():
    try:
        import keyring
        import keyring.errors
    except ImportError as e:
        raise KeyringUnavailableError(
            "The 'keyring' package is not installed."
        ) from e
    return keyring


def save_api_key(account_id: str, api_key: str) -> None:
    keyring = _keyring()
    try:
        keyring.set_password(SERVICE_NAME, account_id, api_key)
    except keyring.errors.NoKeyringError as e:
        raise KeyringUnavailableError(str(e)) from e


def get_api_key(account_id: str):
    keyring = _keyring()
    try:
        return keyring.get_password(SERVICE_NAME, account_id)
    except keyring.errors.NoKeyringError as e:
        raise KeyringUnavailableError(str(e)) from e


def delete_api_key(account_id: str) -> None:
    keyring = _keyring()
    try:
        keyring.delete_password(SERVICE_NAME, account_id)
    except keyring.errors.PasswordDeleteError:
        pass
    except keyring.errors.NoKeyringError as e:
        raise KeyringUnavailableError(str(e)) from e
