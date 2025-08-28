# Team 404 – Wi‑Fi Intel (Week 6)

## What this does
- `report/generate_report.py`: builds a PDF report (ReportLab) from a CSV scan export.
- `web/app.py`: tiny Flask UI to browse SSIDs and view observed MACs.

## CSV format
Columns: `timestamp, ssid, bssid, channel, rssi`

## Quickstart
```bash
python -m venv .venv
# activate venv
pip install -r requirements.txt
python report/generate_report.py --in data/sample_scan.csv --out reports/wifi_report.pdf
python web/app.py
```
