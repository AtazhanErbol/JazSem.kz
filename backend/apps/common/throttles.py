from rest_framework.throttling import ScopedRateThrottle


class AuthoringScopedRateThrottle(ScopedRateThrottle):
    """Give authenticated course authors a bounded upload budget of their own."""

    def allow_request(self, request, view):
        user = getattr(request, "user", None)
        self.authoring_staff = bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) in {"ADMIN", "TEACHER"}
        )
        return super().allow_request(request, view)

    def get_rate(self):
        if self.authoring_staff and self.scope in {"upload", "upload_grant"}:
            self.scope = f"staff_{self.scope}"
        return super().get_rate()
