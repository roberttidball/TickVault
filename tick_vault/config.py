from pathlib import Path
from pydantic import BaseModel


class Config(BaseModel, frozen=True):
    fetch_max_retry_attempts: int = 3
    fetch_base_retry_delay: float = 1.0
    save_directory: Path = Path("./downloads")
    metadata_db_path: Path = Path("./metadata.db")


CONFIG = Config()
