class AtlasError(Exception):
    status_code = 500
    code = "internal_error"
    public_message = "The request could not be completed."


class NotFound(AtlasError):
    status_code = 404
    code = "not_found"
    public_message = "The requested resource was not found."


class InvalidInput(AtlasError):
    status_code = 400
    code = "invalid_input"
    public_message = "The supplied input could not be processed."


class CapacityExceeded(AtlasError):
    status_code = 413
    code = "capacity_exceeded"
    public_message = "The configured document, chunk, or upload limit was exceeded."


class BudgetExceeded(AtlasError):
    status_code = 422
    code = "budget_exceeded"
    public_message = "The request exceeded its configured agent budget."


class ProviderUnavailable(AtlasError):
    status_code = 503
    code = "provider_unavailable"
    public_message = "A required provider is unavailable. Please retry later."
