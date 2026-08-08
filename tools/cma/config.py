import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Config:
    SPARK_API_KEY = os.getenv("SPARK_API_KEY", "")
    SPARK_API_SECRET = os.getenv("SPARK_API_SECRET", "")
    SPARK_ACCESS_TOKEN = os.getenv("SPARK_ACCESS_TOKEN", "")
    SPARK_MLS_ID = os.getenv("SPARK_MLS_ID", "BMLS")
    SPARK_API_BASE_URL = os.getenv("SPARK_API_BASE_URL", "https://sparkapi.com/v1")

    AGENT_NAME = os.getenv("AGENT_NAME", "Joe Desane")
    BROKERAGE = os.getenv("BROKERAGE", "LPT Realty")
    AGENT_PHONE = os.getenv("AGENT_PHONE", "")
    AGENT_EMAIL = os.getenv("AGENT_EMAIL", "joe@tplcollective.ai")

    @classmethod
    def has_spark_credentials(cls) -> bool:
        return bool(cls.SPARK_ACCESS_TOKEN or (cls.SPARK_API_KEY and cls.SPARK_API_SECRET))
