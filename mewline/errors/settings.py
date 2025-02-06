class ExecutableNotFoundError(ImportError):
    """Raised when an executable is not found."""

    def __init__(self, executable_name: str):
        super().__init__(
            f"Executable {executable_name}"
            f" not found. Please install it using your package"
            " manager."
        )
