# helpers functions used across the entire project.
from datetime import datetime, timezone

# add time stamps to print statements for debugging purposes
def log(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}")