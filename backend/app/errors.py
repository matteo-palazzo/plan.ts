class AppError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class InvalidInput(AppError):
    status_code = 422


class Unavailable(AppError):
    status_code = 503


class InsufficientStorage(AppError):
    status_code = 507
