import os

# If DEMO_MODE=1 → use data_demo.json
# If DEMO_MODE=0 or missing → use data.json
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
DATA_FILE = "data_demo.json" if DEMO_MODE else "data.json"
