"""macOS protected storage for the API key.

The key is stored in the data protection keychain with an access control of
"user presence": macOS itself requires Touch ID (or the account password)
every time the item is read, and the item never leaves this device.

This keychain is only available to apps signed with a Developer ID and an
embedded provisioning profile granting a keychain access group; anything
else (e.g. running from a plain Python interpreter) gets
errSecMissingEntitlement, and is_available() returns False.
"""

ERR_SUCCESS = 0
ERR_USER_CANCELED = -128
ERR_AUTH_FAILED = -25293
ERR_DUPLICATE = -25299
ERR_NOT_FOUND = -25300
ERR_INTERACTION_NOT_ALLOWED = -25308
ERR_MISSING_ENTITLEMENT = -34018

PROMPT_REASON = "unlock your FormSmarts API key"


class KeychainError(Exception):
    pass


class KeychainCancelled(KeychainError):
    pass


def _frameworks():
    import Foundation
    import LocalAuthentication
    import Security

    return Security, Foundation, LocalAuthentication


def _base_query(service: str, account: str):
    S, _, _ = _frameworks()
    return {
        S.kSecClass: S.kSecClassGenericPassword,
        S.kSecAttrService: service,
        S.kSecAttrAccount: account,
        S.kSecUseDataProtectionKeychain: True,
    }


def _status(result):
    return result[0] if isinstance(result, tuple) else result


def is_available(service: str) -> bool:
    try:
        S, F, _ = _frameworks()
    except ImportError:
        return False
    probe = _base_query(service + ".probe", "probe")
    add = dict(probe)
    add[S.kSecValueData] = F.NSData.dataWithBytes_length_(b"1", 1)
    status = _status(S.SecItemAdd(add, None))
    if status in (ERR_SUCCESS, ERR_DUPLICATE):
        S.SecItemDelete(probe)
        return True
    return False


def save(service: str, account: str, api_key: str) -> None:
    S, F, _ = _frameworks()
    acl, err = S.SecAccessControlCreateWithFlags(
        None,
        S.kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        S.kSecAccessControlUserPresence,
        None,
    )
    if acl is None:
        raise KeychainError("Couldn't create keychain access control: {}".format(err))
    delete(service, account)
    data = api_key.encode("utf-8")
    query = _base_query(service, account)
    query[S.kSecValueData] = F.NSData.dataWithBytes_length_(data, len(data))
    query[S.kSecAttrAccessControl] = acl
    status = _status(S.SecItemAdd(query, None))
    if status != ERR_SUCCESS:
        raise KeychainError("Couldn't save the API key to the keychain (error {}).".format(status))


def load(service: str, account: str):
    """Return the saved key (prompting for Touch ID / password) or None."""
    S, _, LA = _frameworks()
    ctx = LA.LAContext.alloc().init()
    ctx.setLocalizedReason_(PROMPT_REASON)
    query = _base_query(service, account)
    query[S.kSecReturnData] = True
    query[S.kSecMatchLimit] = S.kSecMatchLimitOne
    query[S.kSecUseAuthenticationContext] = ctx
    status, data = S.SecItemCopyMatching(query, None)
    if status == ERR_NOT_FOUND:
        return None
    if status in (ERR_USER_CANCELED, ERR_AUTH_FAILED):
        raise KeychainCancelled("Touch ID / password verification was cancelled.")
    if status != ERR_SUCCESS or data is None:
        raise KeychainError("Couldn't read the API key from the keychain (error {}).".format(status))
    return bytes(data).decode("utf-8")


def exists(service: str, account: str) -> bool:
    """Check for a saved key without prompting the user."""
    S, _, LA = _frameworks()
    ctx = LA.LAContext.alloc().init()
    ctx.setInteractionNotAllowed_(True)
    query = _base_query(service, account)
    query[S.kSecUseAuthenticationContext] = ctx
    status = _status(S.SecItemCopyMatching(query, None))
    return status in (ERR_SUCCESS, ERR_INTERACTION_NOT_ALLOWED)


def delete(service: str, account: str) -> None:
    S, _, _ = _frameworks()
    S.SecItemDelete(_base_query(service, account))
