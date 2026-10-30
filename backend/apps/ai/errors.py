"""Safe failure codes; provider messages may contain private request details."""


class GenerationFailure(ValueError):
    def __init__(self, code, message="", *, usage=None):
        super().__init__(message or code)
        self.code = code
        self.usage = usage


def rejected_request(error):
    """Only explicit client-side rejections prove generation did not execute."""
    if error.status_code not in {400, 401, 403, 404, 422, 429}:
        return None
    codes = {
        "credit_balance_exhausted": "AI_CREDITS_EXHAUSTED",
        "organization_spend_limit_exceeded": "AI_SPEND_LIMIT_REACHED",
        "project_spend_limit_exceeded": "AI_SPEND_LIMIT_REACHED",
        "organization_usage_limit_exceeded": "AI_PROVIDER_QUOTA_EXHAUSTED",
        "insufficient_quota": "AI_PROVIDER_QUOTA_EXHAUSTED",
    }
    defaults = {
        400: "AI_REQUEST_REJECTED",
        401: "AI_AUTH_FAILED",
        403: "AI_ACCESS_DENIED",
        404: "AI_MODEL_UNAVAILABLE",
        422: "AI_REQUEST_REJECTED",
        429: "AI_RATE_LIMITED",
    }
    return GenerationFailure(codes.get(error.code, defaults[error.status_code]))
