"""Rebuild the epoch-vs-accuracy chart and report.html for a training run.

    python tools/plot_training.py runs/first_try

Reads epochs.csv / evaluations.csv, so it works on a finished run and on one
that is still training. Needs matplotlib for the chart (pip install matplotlib).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "pyro_pete_game"))


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        raise SystemExit(__doc__)
    from ml.report import write_report, CHART
    path = write_report(sys.argv[1])
    print("wrote", path)
    print("chart:", os.path.join(sys.argv[1], CHART))


if __name__ == "__main__":
    main()
