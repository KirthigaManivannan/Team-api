"""Application errors. Each carries an HTTP status code and a user-readable message."""


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class FileError(AppError):
    status_code = 400


class OCRError(AppError):
    status_code = 422


class PDFError(AppError):
    status_code = 422


class EmailError(AppError):
    status_code = 422


class LLMError(AppError):
    status_code = 502
