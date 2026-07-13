class ContractViolationError(Exception):
    """Raised when an API contract is violated (e.g., Pydantic validation failure)."""
    0

class IPCWALError(Exception):
    """Raised when an IPC lock fails or WAL write fails."""
    0
