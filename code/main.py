from scraper import run
import subprocess
import sys
import threading
from pathlib import Path
import time

base_dir = Path(__file__).resolve().parent.parent

if __name__ == '__main__':
    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(5)
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(base_dir / "code" / "dashboard.py")])