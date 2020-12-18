class PackageNotFound(Exception):
    """We asked for package metadata from PyPI and it wasn't available"""

    def __init__(self, package_name: str) -> None:
        super().__init__()
        self.package_name = package_name

    def __str__(self) -> str:
        return f"{self.package_name} no longer exists on PyPI"


class StaleMetadata(Exception):
    """We attempted to retreive metadata from PyPI, but it was stale."""

    def __init__(self, package_name: str, attempts: int) -> None:
        super().__init__()
        self.package_name = package_name
        self.attempts = attempts

    def __str__(self) -> str:
        return f"Stale serial for {self.package_name} after {self.attempts} attempts"


class ConnectionTimeout(Exception):
    """PyPi did not respond in time to our request for package metadata"""

    def __init__(self, package_name: str, attempts: int) -> None:
        super().__init__()
        self.package_name = package_name
        self.attempts = attempts

    def __str__(self) -> str:
        return (
            f"Connection timeout for {self.package_name} after {self.attempts} attempts"
        )
