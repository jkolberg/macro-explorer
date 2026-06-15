import subprocess
import sys
from pathlib import Path


def run_step(context):
    # run quarto render as a subprocess to generate the dashboard HTML file
    BASE_DIR = Path(__file__).resolve().parents[2]
    print(BASE_DIR)
    command = ['quarto', 'render', str(BASE_DIR / 'macro_explorer' / 'forecast_dashboard.qmd')]
    subprocess.run(command, check=True)
    return context