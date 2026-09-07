# Quantifying the Impact of Unnecessary Locks

This folder contains the results of Experiment 2, aimed at quantifying the performance impact of unnecessary locks.

## Folder Structure

- `images/`: Graphs generated from CloudLab tests.
- `runner.py`: Automated benchmark execution script.
- `analyze.py`: Graph generation script.
- `results.csv`: Raw experiment data.

## How to Run

1. Install dependencies: `pip install pandas matplotlib`
2. Run measurements: `python runner.py`
3. Generate plots: `python analyze.py`
