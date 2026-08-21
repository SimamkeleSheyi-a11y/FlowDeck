"""
Consistent error envelope for the FlowDeck API (Phase 1 architecture doc,
Section 7): field-validation errors keep DRF's normal {"field": [...]} shape
so the frontend can bind errors directly to form fields, while every other
error (401/403/404/405/429/500) is normalized to {"detail": ..., "code": ...}.
"""
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


def flowdeck_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(exc, ValidationError):
        return response

    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        code = getattr(exc, "default_code", exc.__class__.__name__.lower())
        response.data = {"detail": str(detail["detail"]), "code": code}

    return response
