from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)

_APP: Any | None = None
_APP_LOCK = Lock()


class FirebaseAuthDisabledError(RuntimeError):
    """Raised when Firebase-backed verification is disabled."""


class FirebaseAuthUnavailableError(RuntimeError):
    """Raised when Firebase credentials or API calls are unavailable."""


def _require_enabled() -> None:
    if settings.firebase_enabled:
        return
    raise FirebaseAuthDisabledError("Firebase email verification is disabled.")


def _load_sdk() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from firebase_admin import auth as firebase_auth
        from firebase_admin import credentials
        from firebase_admin import exceptions as firebase_exceptions
        from firebase_admin import get_app, initialize_app
    except Exception as exc:  # pragma: no cover - exercised only without dependency installed
        raise FirebaseAuthUnavailableError("firebase-admin is not installed or failed to import.") from exc
    return firebase_auth, credentials, firebase_exceptions, get_app, initialize_app


def _service_account_source() -> dict[str, Any] | str:
    inline_json = (settings.FIREBASE_SERVICE_ACCOUNT_JSON or "").strip()
    if inline_json:
        try:
            return json.loads(inline_json)
        except json.JSONDecodeError as exc:
            raise FirebaseAuthUnavailableError("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    path = (settings.FIREBASE_SERVICE_ACCOUNT_PATH or "").strip()
    if not path:
        raise FirebaseAuthUnavailableError("Firebase service account credentials are not configured.")

    resolved = Path(path)
    if not resolved.exists():
        raise FirebaseAuthUnavailableError(f"Firebase service account file does not exist: {resolved}")
    return str(resolved)


def _firebase_app() -> Any:
    _require_enabled()
    global _APP
    if _APP is not None:
        return _APP

    firebase_auth, credentials, _, get_app, initialize_app = _load_sdk()
    del firebase_auth

    with _APP_LOCK:
        if _APP is not None:
            return _APP
        try:
            _APP = get_app()
        except ValueError:
            options = {"projectId": settings.FIREBASE_PROJECT_ID.strip()}
            try:
                certificate = credentials.Certificate(_service_account_source())
                _APP = initialize_app(certificate, options=options)
            except FirebaseAuthUnavailableError:
                raise
            except Exception as exc:
                raise FirebaseAuthUnavailableError("Failed to initialize firebase-admin.") from exc
    return _APP


def _normalized_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if normalized:
        return normalized
    raise FirebaseAuthUnavailableError("Email is required for Firebase verification.")


def _wrap_sdk_error(exc: Exception, *, operation: str) -> FirebaseAuthUnavailableError:
    return FirebaseAuthUnavailableError(f"Firebase Auth {operation} failed: {exc}")


def get_firebase_user(uid: str) -> Any:
    firebase_auth, _, firebase_exceptions, _, _ = _load_sdk()
    try:
        return firebase_auth.get_user((uid or "").strip(), app=_firebase_app())
    except firebase_auth.UserNotFoundError as exc:
        raise FirebaseAuthUnavailableError("Firebase user does not exist.") from exc
    except firebase_exceptions.FirebaseError as exc:
        raise _wrap_sdk_error(exc, operation="get_user") from exc


def ensure_firebase_user(email: str) -> str:
    firebase_auth, _, firebase_exceptions, _, _ = _load_sdk()
    normalized_email = _normalized_email(email)
    try:
        return firebase_auth.get_user_by_email(normalized_email, app=_firebase_app()).uid
    except firebase_auth.UserNotFoundError:
        pass
    except firebase_exceptions.FirebaseError as exc:
        raise _wrap_sdk_error(exc, operation="get_user_by_email") from exc

    try:
        record = firebase_auth.create_user(
            email=normalized_email,
            email_verified=False,
            app=_firebase_app(),
        )
        return record.uid
    except firebase_exceptions.FirebaseError:
        try:
            record = firebase_auth.get_user_by_email(normalized_email, app=_firebase_app())
            return record.uid
        except firebase_auth.UserNotFoundError as exc:
            raise _wrap_sdk_error(exc, operation="create_user") from exc
        except firebase_exceptions.FirebaseError as exc:
            raise _wrap_sdk_error(exc, operation="create_user") from exc


def generate_verification_link(email: str, continue_url: str) -> str:
    firebase_auth, _, firebase_exceptions, _, _ = _load_sdk()
    normalized_url = (continue_url or "").strip()
    if not normalized_url:
        raise FirebaseAuthUnavailableError("FIREBASE_EMAIL_CONTINUE_URL_BASE is not configured.")

    settings_obj = firebase_auth.ActionCodeSettings(
        url=normalized_url,
        handle_code_in_app=True,
    )
    try:
        return firebase_auth.generate_email_verification_link(
            _normalized_email(email),
            action_code_settings=settings_obj,
            app=_firebase_app(),
        )
    except firebase_exceptions.FirebaseError as exc:
        raise _wrap_sdk_error(exc, operation="generate_email_verification_link") from exc


def create_custom_token(uid: str) -> str:
    firebase_auth, _, firebase_exceptions, _, _ = _load_sdk()
    normalized_uid = (uid or "").strip()
    if not normalized_uid:
        raise FirebaseAuthUnavailableError("Firebase user id is required.")
    try:
        token = firebase_auth.create_custom_token(normalized_uid, app=_firebase_app())
    except firebase_exceptions.FirebaseError as exc:
        raise _wrap_sdk_error(exc, operation="create_custom_token") from exc
    return token.decode("utf-8") if isinstance(token, bytes) else str(token)


def is_firebase_email_verified(uid: str) -> bool:
    return bool(get_firebase_user(uid).email_verified)


def delete_firebase_user(uid: str) -> None:
    firebase_auth, _, firebase_exceptions, _, _ = _load_sdk()
    normalized_uid = (uid or "").strip()
    if not normalized_uid:
        return
    try:
        firebase_auth.delete_user(normalized_uid, app=_firebase_app())
    except FirebaseAuthDisabledError:
        return
    except firebase_auth.UserNotFoundError:
        return
    except firebase_exceptions.FirebaseError as exc:
        logger.warning("Failed to delete Firebase user %s: %s", normalized_uid, exc)
