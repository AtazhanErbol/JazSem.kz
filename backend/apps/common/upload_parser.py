from rest_framework.parsers import FormParser, JSONParser, MultiPartParser


class DirectUploadParser(JSONParser):
    media_type = "application/vnd.jazsem.upload+json"

    def parse(self, stream, media_type=None, parser_context=None):
        # APIView imports default parsers during its own class initialization.
        from .direct_uploads import consume_uploads

        body = super().parse(stream, media_type, parser_context)
        return consume_uploads(body, parser_context["request"])


UPLOAD_PARSERS = [JSONParser, FormParser, MultiPartParser, DirectUploadParser]
