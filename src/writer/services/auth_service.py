"""Authentication service — re-exported from documentlm_core."""

from documentlm_core.services.auth_service import (  # noqa: F401
    DuplicateEmailError,
    InvalidInviteCodeError,
    UserNotFoundError,
    authenticate_user,
    create_invite_codes,
    get_user_by_id,
    hash_password,
    register_user,
    reset_password,
    verify_password,
)
