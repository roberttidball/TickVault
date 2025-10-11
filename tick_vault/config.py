from pathlib import Path

from pydantic import BaseModel, model_validator


class Config(BaseModel, frozen=True):
    base_directory: Path = Path("./tick_vault")
    fetch_max_retry_attempts: int = 3
    fetch_base_retry_delay: float = 1.0
    worker_per_proxy: int = 10
    worker_queue_timeout: float = 60.0
    metadata_update_batch_timeout: float = 1.0
    metadata_update_batch_size: int = 100

    @model_validator(mode='after')
    def validate_timeouts(self) -> 'Config':
        """Ensure batch timeout is less than worker queue timeout."""
        if self.metadata_update_batch_timeout >= self.worker_queue_timeout:
            raise ValueError(
                f"metadata_update_batch_timeout ({self.metadata_update_batch_timeout}) "
                f"must be less than worker_queue_timeout ({self.worker_queue_timeout})"
            )
        return self

    @property
    def save_directory(self) -> Path:
        return self.base_directory / "downloads"

    @property
    def metadata_db_path(self) -> Path:
        return self.base_directory / "metadata.db"


CONFIG = Config()
