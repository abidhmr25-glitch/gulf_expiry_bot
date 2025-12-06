import os

# When running on Render, we will set DEMO_MODE=1 in environment.
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"

# Choose which data file to use.
# - On your PC (no DEMO_MODE)  -> use data.json  (your real data)
# - On Render (DEMO_MODE=1)    -> use data_demo.json (public demo data)
DATA_FILE = "data_demo.json" if DEMO_MODE else "data.json"
