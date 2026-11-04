"""Windows Hello protected storage for the API key.

Windows Hello can't wrap an arbitrary secret, so we use the standard
technique: a Windows Hello key (an RSA key held by the TPM, usable only
after the user verifies with their PIN, fingerprint or face, with attempt
limits enforced by Windows) signs a random per-account challenge. RSA
PKCS#1 v1.5 signatures are deterministic, so the same challenge always
yields the same signature; its SHA-256 is used as an AES-256-GCM key to
encrypt the API key.

Only the challenge and the ciphertext are stored (in Windows Credential
Manager, via `keyring`). Reading them is useless without a Windows Hello
verification by the user.
"""

import asyncio
import base64
import ctypes
import hashlib
import json
import os
import threading
import time

HELLO_KEY_NAME = "FormSmartsDownloader"
PREFIX = "fshello1:"
_AAD = PREFIX.encode()


class HelloError(Exception):
    pass


class HelloCancelled(HelloError):
    pass


def _winrt():
    from winrt.windows.security.credentials import (
        KeyCredentialCreationOption,
        KeyCredentialManager,
        KeyCredentialStatus,
    )
    from winrt.windows.security.cryptography import CryptographicBuffer
    import winrt.windows.storage.streams  # noqa: F401 - registers IBuffer

    return KeyCredentialManager, KeyCredentialCreationOption, KeyCredentialStatus, CryptographicBuffer


def _to_ibuffer(data: bytes):
    _, _, _, CryptographicBuffer = _winrt()
    try:
        return CryptographicBuffer.create_from_byte_array(data)
    except TypeError:
        return CryptographicBuffer.create_from_byte_array(list(data))


def _from_ibuffer(buf) -> bytes:
    try:
        return bytes(memoryview(buf))
    except TypeError:
        _, _, _, CryptographicBuffer = _winrt()
        return bytes(CryptographicBuffer.copy_to_byte_array(buf))


def _bring_prompt_to_front(stop: threading.Event):
    """The Windows Hello dialog often opens behind a desktop app's window;
    raise it when it appears."""
    user32 = ctypes.windll.user32
    deadline = time.monotonic() + 10
    while not stop.is_set() and time.monotonic() < deadline:
        hwnd = user32.FindWindowW("Credential Dialog Xaml Host", None)
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            return
        time.sleep(0.1)


def _run(coro):
    stop = threading.Event()
    threading.Thread(target=_bring_prompt_to_front, args=(stop,), daemon=True).start()
    try:
        return asyncio.run(coro)
    finally:
        stop.set()


def is_available() -> bool:
    try:
        KeyCredentialManager, _, _, _ = _winrt()
        return bool(asyncio.run(_is_supported(KeyCredentialManager)))
    except Exception:
        return False


async def _is_supported(KeyCredentialManager):
    return await KeyCredentialManager.is_supported_async()


def _check(status, KeyCredentialStatus, what):
    if status == KeyCredentialStatus.SUCCESS:
        return
    if status == KeyCredentialStatus.USER_CANCELED:
        raise HelloCancelled("Windows Hello verification was cancelled.")
    raise HelloError("Windows Hello {} failed (status {}).".format(what, int(status)))


async def _sign(challenge: bytes, create: bool) -> bytes:
    KeyCredentialManager, Option, Status, _ = _winrt()
    result = await KeyCredentialManager.open_async(HELLO_KEY_NAME)
    if result.status == Status.NOT_FOUND:
        if not create:
            raise HelloError(
                "The Windows Hello key for this app no longer exists. "
                "Please enter your API key again."
            )
        result = await KeyCredentialManager.request_create_async(
            HELLO_KEY_NAME, Option.FAIL_IF_EXISTS
        )
    _check(result.status, Status, "setup")
    signed = await result.credential.request_sign_async(_to_ibuffer(challenge))
    _check(signed.status, Status, "verification")
    return _from_ibuffer(signed.result)


def _aes_key(signature: bytes) -> bytes:
    return hashlib.sha256(b"FormSmartsDownloader/v1" + signature).digest()


def seal(api_key: str) -> str:
    """Encrypt the API key; prompts the user for Windows Hello."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    challenge = os.urandom(32)
    key = _aes_key(_run(_sign(challenge, create=True)))
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, api_key.encode("utf-8"), _AAD)
    blob = {
        "challenge": base64.b64encode(challenge).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ct": base64.b64encode(ct).decode(),
    }
    return PREFIX + json.dumps(blob, separators=(",", ":"))


def unseal(value: str) -> str:
    """Decrypt a value produced by seal(); prompts the user for Windows Hello."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        blob = json.loads(value[len(PREFIX):])
        challenge = base64.b64decode(blob["challenge"])
        nonce = base64.b64decode(blob["nonce"])
        ct = base64.b64decode(blob["ct"])
    except (ValueError, KeyError, TypeError) as e:
        raise HelloError("The saved API key is corrupted. Please enter it again.") from e
    key = _aes_key(_run(_sign(challenge, create=False)))
    try:
        return AESGCM(key).decrypt(nonce, ct, _AAD).decode("utf-8")
    except InvalidTag as e:
        raise HelloError(
            "The saved API key can't be unlocked (the Windows Hello key may have "
            "been reset). Please enter your API key again."
        ) from e


def delete_hello_key() -> None:
    try:
        KeyCredentialManager, _, _, _ = _winrt()

        async def _delete():
            await KeyCredentialManager.delete_async(HELLO_KEY_NAME)

        asyncio.run(_delete())
    except Exception:
        pass
