from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite+aiosqlite:///{Path(__file__).parent.parent.parent / 'data' / 'media_refinery.sqlite'}"
    INPUT_DIR: str = str(Path(__file__).parent.parent.parent / 'input')
    OUTPUT_DIR: str = str(Path(__file__).parent.parent.parent / 'output')
    STAGING_DIR: str = str(Path(__file__).parent.parent.parent / 'staging')

    class Config:
        env_file = ".env"

settings = Settings()
