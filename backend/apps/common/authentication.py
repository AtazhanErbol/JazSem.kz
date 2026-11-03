from rest_framework.authentication import SessionAuthentication as DRFSessionAuthentication


class SessionAuthentication(DRFSessionAuthentication):
    def enforce_csrf(self, request):
        from .upload_parser import DirectUploadParser

        if request.content_type == DirectUploadParser.media_type:
            # CSRF checks POST before its header fallback. Parsing a direct
            # upload there would access request.user while authentication is
            # still running, and could consume tickets before CSRF succeeds.
            # Django's HttpRequest does not parse this JSON media type as a
            # form, so the normal origin/cookie/header checks finish first.
            request = request._request
        return super().enforce_csrf(request)
