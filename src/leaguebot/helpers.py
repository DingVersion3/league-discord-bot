# helpers functions used across the entire project.
from datetime import datetime
from zoneinfo import ZoneInfo

# add time stamps to print statements for debugging purposes
def log(message: str) -> None:
    stamp = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{stamp}] {message}")