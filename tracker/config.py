import os
from dotenv import load_dotenv

load_dotenv()

DEMO_MODE: bool = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")

if DEMO_MODE:
    FORDPASS_EMAIL = ""
    FORDPASS_PASSWORD = ""
    FORDPASS_VIN = "DEMO0000000000000"
else:
    FORDPASS_EMAIL: str = os.environ["FORDPASS_EMAIL"]
    FORDPASS_PASSWORD: str = os.environ["FORDPASS_PASSWORD"]
    FORDPASS_VIN: str = os.getenv("FORDPASS_VIN", "")

POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "180"))
TRIP_TIMEOUT_MINUTES: int = int(os.getenv("TRIP_TIMEOUT_MINUTES", "10"))
MOVEMENT_THRESHOLD_METERS: float = float(os.getenv("MOVEMENT_THRESHOLD_METERS", "50"))
DB_PATH: str = os.getenv("DB_PATH", "fordtracker.db")
