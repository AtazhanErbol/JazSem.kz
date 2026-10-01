"""Error diagnostics without request bodies, tokens, answers or local variables."""

from urllib.parse import urlsplit, urlunsplit


def scrub_event(event, hint):
    request = event.get("request", {})
    url = urlsplit(request.get("url", ""))
    event["request"] = {
        "method": request.get("method"),
        "url": urlunsplit((url.scheme, url.hostname or "", url.path, "", "")),
    }
    for key in ("user", "extra", "breadcrumbs", "logentry", "message", "contexts"):
        event.pop(key, None)
    for exception in event.get("exception", {}).get("values", []):
        exception["value"] = "Details omitted; correlate using request_id."
        for frame in exception.get("stacktrace", {}).get("frames", []):
            for key in ("vars", "pre_context", "context_line", "post_context"):
                frame.pop(key, None)
    return event
