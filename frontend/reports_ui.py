"""Markup and chart for the three Historical Analysis slides."""

from html import escape

import plotly.graph_objects as go

from activity_data import MONTH_LABELS
from reports_data import RECORD_COLUMNS


def number(value):
    return "N/A" if value is None else f"{value:,.1f}".removesuffix(".0")


def percent(value, signed=False):
    if value is None:
        return "N/A"
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def indicators_html(summary):
    deviation = summary["deviation"]
    status = ("Historical baseline unavailable" if deviation is None else
              "Above the historical norm" if deviation > 0 else
              "Below the historical norm" if deviation < 0 else "At the historical norm")
    cards = (
        ("Current activity", number(summary["total"]), "Detected hotspots"),
        ("Historical average", number(summary["historical_total"]), "Same period in previous years"),
        ("Deviation from the mean", percent(deviation, signed=True), status),
        ("Largest deviation recorded", percent(summary["largest_deviation"]), "Monthly deviation from the historical average"),
    )
    return '<div class="historical-indicators">' + ''.join(
        f'<section class="historical-metric"><h3>{title}</h3><strong>{value}</strong><p>{note}</p></section>'
        for title, value, note in cards) + '</div>'


def anomalies_html(summary):
    incidents = summary["incidents"]
    parts = [f'<div class="anomaly-heading"><h2>Anomaly identification</h2>'
             f'<span class="incident-count">{len(incidents)} incidents</span></div>',
             '<div class="anomaly-list" tabindex="0" aria-label="Monthly anomalies">']
    if not incidents:
        message = ("No earlier demonstration years are available for comparison." if summary["average"] is None
                   else "No anomalies found for this selection.")
        parts.append(f'<div class="historical-empty">{message}</div>')
    for row in incidents:
        above = row["new_activity"] or row["deviation"] > 0
        color = "above" if above else "below"
        label = "New activity" if row["new_activity"] else "Above average" if above else "Below average"
        deviation = "New activity" if row["new_activity"] else percent(row["deviation"], signed=True)
        width = 100 if row["new_activity"] else min(100, abs(row["deviation"]))
        parts.append(f'''<article class="anomaly-item {color}">
<div class="anomaly-item-heading"><h3>{row['name']} {summary['year']}</h3><span>{label}</span></div>
<strong>{deviation}</strong><p>{number(row['current'])} hotspots detected · Historical average: {number(row['average'])}</p>
<div class="anomaly-track" aria-hidden="true"><span style="width:{width:.2f}%"></span></div></article>''')
    parts.append('</div>')
    return ''.join(parts)


def comparison_figure(summary):
    figure = go.Figure()
    series = [(str(summary["year"]), summary["current"], "#e6ff00")]
    if summary["average"] is not None:
        series.append(("Historical average", summary["average"], "#2d9bff"))
    for name, values, color in series:
        figure.add_trace(go.Scatter(
            x=MONTH_LABELS, y=values, name=name, mode="lines+markers",
            line={"color": color, "width": 2.5},
            marker={"size": 6, "color": "#303646", "line": {"color": color, "width": 2}},
            hovertemplate=f"{name} · %{{x}}: %{{y:,.1f}} hotspots<extra></extra>",
        ))
    figure.update_layout(
        autosize=True, paper_bgcolor="#303646", plot_bgcolor="#303646",
        font={"family": "Barlow, Arial", "size": 14, "color": "#fdfbfd"},
        margin={"l": 36, "r": 14, "t": 8, "b": 32},
        legend={"orientation": "h", "x": 0, "y": 1.15},
        xaxis={"showgrid": False, "fixedrange": True, "zeroline": False},
        yaxis={"rangemode": "tozero", "gridcolor": "#3c4454", "zerolinecolor": "#3c4454", "fixedrange": True},
        hovermode="x unified", hoverlabel={"bgcolor": "#09163b"},
    )
    return figure


def records_html(page):
    headers = ''.join(f'<th scope="col">{escape(label)}</th>' for label in RECORD_COLUMNS)
    rows = []
    for record in page["rows"]:
        values = [record[0], f"{record[1]:.4f}", f"{record[2]:.4f}", *record[3:]]
        rows.append('<tr>' + ''.join(f'<td>{escape(str(value)) if value is not None else "N/A"}</td>' for value in values) + '</tr>')
    if not rows:
        rows.append('<tr><td colspan="8" class="historical-empty">No demonstration records for this selection.</td></tr>')
    return f'''<div class="record-meta"><span>{page['total']:,} records found</span><span>Page {page['page'] + 1} of {page['pages']}</span></div>
<div class="detection-table-scroll" tabindex="0" aria-label="Detection record table"><table class="detection-table">
<caption class="sr-only">Synthetic detection records, newest first. All timestamps are UTC.</caption>
<thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class="record-meta">Showing {page['start']:,}–{page['end']:,} of {page['total']:,}</div>'''
