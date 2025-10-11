from pathlib import Path

from pydantic import BaseModel


class Config(BaseModel, frozen=True):
    base_directory: Path = Path("./tick_vault")
    fetch_max_retry_attempts: int = 3
    fetch_base_retry_delay: float = 1.0
    worker_per_proxy: int = 10
    worker_queue_timeout: float = 60.0

    @property
    def save_directory(self) -> Path:
        return self.base_directory / "downloads"

    @property
    def metadata_db_path(self) -> Path:
        return self.base_directory / "metadata.db"


CONFIG = Config()
