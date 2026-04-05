class DownloadMethodFailed(Exception):
    pass


class KingfisherException(Exception):
    """User-facing exception with a clean error description and optional inner exception."""
    def __init__(self, error_description, inner=None):
        self.error_description = error_description
        self.inner = inner
        super().__init__(error_description)
