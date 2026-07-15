class TelemetryUploadError(Exception):
    """遥测上传失败。"""

    def __init__(self, message: str, retryable: bool = True, status_code=None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
