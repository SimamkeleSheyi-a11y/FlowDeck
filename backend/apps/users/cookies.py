from django.conf import settings


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.SIMPLE_JWT["REFRESH_COOKIE_NAME"],
        value=refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/api/auth/",
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(settings.SIMPLE_JWT["REFRESH_COOKIE_NAME"], path="/api/auth/")
