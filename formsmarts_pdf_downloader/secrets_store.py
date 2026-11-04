"""API key storage.

The user chooses one of two modes:

  "none"       Most secure: the API key is never saved; the user enters it
               each session.
  "protected"  The API key is saved, and the OS requires the user to verify
               (Windows Hello PIN / fingerprint / face, or Touch ID / the
               account password on macOS) every time it is read. Other
               programs running as the same user can't read it silently.
                 - Windows: see _win_hello.py
                 - macOS:   see _mac_keychain.py (signed app builds only)

The key is never written to the plain-text config file. Earlier versions
saved it unprotected in the OS credential store; take_legacy_key() reads
and removes such an entry so it can be migrated.
"""

import sys

SERVICE_NAME = "FormSmarts PDF Downloader"

MODE_NONE = "none"
MODE_PROTECTED = "protected"
MODES = (MODE_NONE, MODE_PROTECTED)


class KeyStoreError(Exception):
    """Saving or reading the protected key failed."""


class UnlockCancelled(KeyStoreError):
    """The user dismissed the Windows Hello / Touch ID prompt."""


_available = None


def protection_name():
    """Human-readable name of the OS verification, or None if unsupported."""
    if not protected_available():
        return None
    if sys.platform == "win32":
        return "Windows Hello"
    return "Touch ID or your Mac password"


def protected_available() -> bool:
    global _available
    if _available is None:
        _available = _probe()
    return _available


def _probe() -> bool:
    if sys.platform == "win32":
        from . import _win_hello

        return _keyring() is not None and _win_hello.is_available()
    if sys.platform == "darwin":
        from . import _mac_keychain

        return _mac_keychain.is_available(SERVICE_NAME)
    return False


def mode_labels():
    """(mode, label) pairs, most secure first, limited to what's supported."""
    labels = [(MODE_NONE, "Most secure: don't save the API key, ask for it each time")]
    name = protection_name()
    if name:
        labels.append((MODE_PROTECTED, "Save the API key, unlock it with {}".format(name)))
    return labels


def effective_mode(cfg: dict) -> str:
    mode = cfg.get("key_storage")
    if mode == MODE_PROTECTED and protected_available():
        return MODE_PROTECTED
    return MODE_NONE


# ------------------------------------------------------------- protected


def save_api_key(account_id: str, api_key: str) -> None:
    """Save the key with OS-enforced protection. May prompt the user."""
    if not protected_available():
        raise KeyStoreError("Protected key storage isn't available on this computer.")
    if sys.platform == "win32":
        from . import _win_hello

        try:
            value = _win_hello.seal(api_key)
        except _win_hello.HelloCancelled as e:
            raise UnlockCancelled(str(e)) from e
        except Exception as e:
            raise KeyStoreError(str(e)) from e
        _keyring_set(account_id, value)
    else:
        from . import _mac_keychain

        try:
            _mac_keychain.save(SERVICE_NAME, account_id, api_key)
        except Exception as e:
            raise KeyStoreError(str(e)) from e


def load_api_key(account_id: str):
    """Return the saved key, or None. Prompts the user to verify."""
    if not protected_available():
        return None
    if sys.platform == "win32":
        from . import _win_hello

        value = _keyring_get(account_id)
        if not value or not value.startswith(_win_hello.PREFIX):
            return None
        try:
            return _win_hello.unseal(value)
        except _win_hello.HelloCancelled as e:
            raise UnlockCancelled(str(e)) from e
        except Exception as e:
            raise KeyStoreError(str(e)) from e
    from . import _mac_keychain

    try:
        return _mac_keychain.load(SERVICE_NAME, account_id)
    except _mac_keychain.KeychainCancelled as e:
        raise UnlockCancelled(str(e)) from e
    except Exception as e:
        raise KeyStoreError(str(e)) from e


def has_saved_key(account_id: str) -> bool:
    """Whether a protected key is saved, without prompting the user."""
    if not account_id or not protected_available():
        return False
    if sys.platform == "win32":
        from . import _win_hello

        value = _keyring_get(account_id)
        return bool(value and value.startswith(_win_hello.PREFIX))
    from . import _mac_keychain

    return _mac_keychain.exists(SERVICE_NAME, account_id)


def delete_api_key(account_id: str) -> None:
    """Remove any saved key for this account (protected or legacy)."""
    if not account_id:
        return
    if sys.platform == "darwin":
        try:
            from . import _mac_keychain

            _mac_keychain.delete(SERVICE_NAME, account_id)
        except ImportError:
            pass
    _keyring_delete(account_id)


def forget_everything(account_id: str) -> None:
    """Delete the saved key and, on Windows, the app's Windows Hello key."""
    delete_api_key(account_id)
    if sys.platform == "win32":
        from . import _win_hello

        _win_hello.delete_hello_key()


# ----------------------------------------------------------------- legacy


def take_legacy_key(account_id: str):
    """Read and delete an unprotected key saved by an earlier version."""
    if not account_id:
        return None
    value = _keyring_get(account_id)
    if not value:
        return None
    if sys.platform == "win32":
        from . import _win_hello

        if value.startswith(_win_hello.PREFIX):
            return None
    _keyring_delete(account_id)
    return value


# ---------------------------------------------------------------- keyring


def _keyring():
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    try:
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
    except Exception:
        return None
    return keyring


def _keyring_get(account_id):
    kr = _keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(SERVICE_NAME, account_id)
    except Exception:
        return None


def _keyring_set(account_id, value):
    kr = _keyring()
    if kr is None:
        raise KeyStoreError("Windows Credential Manager isn't available.")
    try:
        kr.set_password(SERVICE_NAME, account_id, value)
    except Exception as e:
        raise KeyStoreError(str(e)) from e


def _keyring_delete(account_id):
    kr = _keyring()
    if kr is None:
        return
    try:
        kr.delete_password(SERVICE_NAME, account_id)
    except Exception:
        pass
