#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

# ---- ReportLab imports (keep ALL of these at the TOP) ----
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
# -----------------------------------------------------------


def load_scan(csv_path: Path) -> pd.DataFrame:
    """Load and normalize the scan CSV."""
    df = pd.read_csv(csv_path)
    expected = ["timestamp", "ssid", "bssid", "channel", "rssi"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV is missing columns: {missing}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["ssid"] = df["ssid"].fillna("").astype(str)
    df["bssid"] = df["bssid"].fillna("").astype(str)
    df["channel"] = df["channel"].astype(str)
    df["rssi"] = pd.to_numeric(df["rssi"], errors="coerce")
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per BSSID (MAC)."""
    g = df.groupby("bssid", dropna=False)
    out = g.agg(
        frames=("bssid", "size"),
        first_seen=("timestamp", "min"),
        last_seen=("timestamp", "max"),
        min_rssi=("rssi", "min"),
        avg_rssi=("rssi", "mean"),
        max_rssi=("rssi", "max"),
    ).reset_index()

    ssids = g["ssid"].agg(lambda s: ", ".join(sorted({x for x in s if x})))
    chans = g["channel"].agg(lambda s: ", ".join(sorted({str(x) for x in s if str(x)})))
    out["ssids"] = ssids.values
    out["channels"] = chans.values
    out = out.sort_values(["frames", "bssid"], ascending=[False, True])
    return out


def _header_footer(canvas, doc, title, subtitle):
    """Standard header/footer for each page."""
    canvas.saveState()
    w, h = A4
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(20 * mm, h - 15 * mm, title)
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(w - 20 * mm, h - 14.5 * mm, subtitle)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(csv_path: Path, out_pdf: Path, meta: dict):
    df = load_scan(csv_path)
    summary = summarize(df)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Tiny", fontSize=8, leading=10))

    doc = SimpleDocTemplate(
        str(out_pdf),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=25 * mm,
        bottomMargin=18 * mm,
    )

    story = []

    # ----- Title block -----
    title = meta.get("title", "Wireless Intelligence Report")
    project = meta.get("project", "Team 404 – Week 6 Prototype")
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    story += [
        Paragraph(f"<b>{title}</b>", styles["Title"]),
        Spacer(1, 6),
        Paragraph(f"{project}<br/>Generated: {when}", styles["Normal"]),
        Spacer(1, 12),
    ]

    # ----- Summary -----
    unique_macs = summary.shape[0]
    unique_ssids = df["ssid"].replace("", pd.NA).dropna().nunique()
    total_frames = int(df.shape[0])
    story += [
        Paragraph(
            f"<b>Summary</b>: {unique_macs} unique MACs across {unique_ssids} SSIDs • "
            f"{total_frames} frames observed.",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]

    # ----- Parameters block (directly under Summary) -----
    def fmt_ts(ts):
        return ts.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(ts) else ""

    min_ts = fmt_ts(df["timestamp"].min())
    max_ts = fmt_ts(df["timestamp"].max())

    params_rows = [
        ["Data file", Path(csv_path).name],
        ["Records", f"{total_frames}"],
        ["Unique SSIDs", f"{unique_ssids}"],
        ["Time range", f"{min_ts} → {max_ts}"],
        ["Filter SSID", meta.get("filter_ssid", "(none)")],
        ["App version", meta.get("app_version", "0.1.0")],
    ]

    params_tbl = Table(params_rows, colWidths=[30 * mm, None])
    params_tbl.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story += [Paragraph("<b>Parameters</b>", styles["Heading3"]), Spacer(1, 4), params_tbl, Spacer(1, 12)]

    # ----- MAC table -----
    table_header = [
        "#",
        "MAC (BSSID)",
        "SSID(s)",
        "Frames",
        "First Seen",
        "Last Seen",
        "Min RSSI",
        "Avg RSSI",
        "Max RSSI",
        "Ch",
    ]
    rows = [table_header]

    for i, row in enumerate(summary.itertuples(index=False), start=1):
        rows.append(
            [
                i,
                row.bssid or "(unknown)",
                (row.ssids or "")[:40],
                int(row.frames),
                fmt_ts(row.first_seen),
                fmt_ts(row.last_seen),
                f"{row.min_rssi:.0f}" if pd.notna(row.min_rssi) else "",
                f"{row.avg_rssi:.1f}" if pd.notna(row.avg_rssi) else "",
                f"{row.max_rssi:.0f}" if pd.notna(row.max_rssi) else "",
                row.channels,
            ]
        )

    tbl = Table(rows, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ("ALIGN", (6, 1), (-2, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightyellow]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story += [Paragraph("<b>Observed MAC Addresses</b>", styles["Heading2"]), Spacer(1, 6), tbl]

    # Build
    subtitle = meta.get("subtitle", "Prototype report generated from Wi-Fi scan CSV")
    doc.build(
        story,
        onFirstPage=lambda c, d: _header_footer(c, d, title, subtitle),
        onLaterPages=lambda c, d: _header_footer(c, d, title, subtitle),
    )


def main():
    ap = argparse.ArgumentParser(description="Generate Wi-Fi PDF report from CSV")
    ap.add_argument("--in", dest="in_csv", required=True, help="Path to scan CSV")
    ap.add_argument("--out", dest="out_pdf", default="reports/wifi_report.pdf")
    ap.add_argument("--title", default="Wireless Intelligence Report")
    ap.add_argument("--project", default="Team 404 – Week 6 Prototype")
    ap.add_argument("--subtitle", default="Prototype report generated from Wi-Fi scan CSV")
    ap.add_argument("--filter-ssid", default="")
    ap.add_argument("--app-version", default="0.1.0")
    args = ap.parse_args()

    out = Path(args.out_pdf)
    out.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "title": args.title,
        "project": args.project,
        "subtitle": args.subtitle,
        "filter_ssid": args.filter_ssid,
        "app_version": args.app_version,
    }
    build_pdf(Path(args.in_csv), out, meta)
    print(f"✅ Report written to: {out.resolve()}")


if __name__ == "__main__":
    main()
