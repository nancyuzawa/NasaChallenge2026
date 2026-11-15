"""Calendário e cartões da página de atividade."""

from html import escape

from activity_data import HEAT_COLORS, MONTH_LABELS
from ui import icon


def calendar_html(cells, legend):
    weeks = max(cell["week"] for cell in cells) + 1
    first_day = cells[0]["date"].replace(month=1, day=1)
    last_day = first_day.replace(month=12, day=31)
    year_weeks = ((last_day - first_day).days + (first_day.weekday() + 1) % 7) // 7 + 1
    focused = len({cell["date"].month for cell in cells}) == 1
    frame_class = "calendar-canvas calendar-canvas--month" if focused else "calendar-canvas"
    parts = [f'<div class="{frame_class}" style="--calendar-ratio:{(year_weeks + 1) / 8:.4f};--calendar-year-weeks:{year_weeks}">',
             f'<div class="activity-heatmap" role="grid" aria-label="Daily fire hotspots calendar" aria-rowcount="8" aria-colcount="{weeks + 1}" style="--calendar-weeks:{weeks}">',
             '<div class="calendar-row" role="row">']
    seen_months = set()
    for cell in cells:
        day = cell["date"]
        if day.month not in seen_months:
            last_week = max(item["week"] for item in cells if item["date"].month == day.month)
            parts.append(f'<span class="calendar-month" role="columnheader" style="grid-column:{cell["week"] + 2} / {last_week + 3};grid-row:1">{MONTH_LABELS[day.month - 1]}</span>')
            seen_months.add(day.month)
    parts.append('</div>')
    step = legend[0]["step"]
    for row, (label, name) in enumerate(zip(("S", "M", "T", "W", "T", "F", "S"),
                                           ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"))):
        parts.append(f'<div class="calendar-row" role="row"><span class="calendar-weekday" role="rowheader" aria-label="{name}" style="grid-column:1;grid-row:{row + 2}">{label}</span>')
        for cell in cells:
            if cell["weekday"] != row:
                continue
            day, count = cell["date"], cell["count"]
            level = int(min(5, max(0, (count or 0) / step if legend[0].get("continuous") else ((count or 0) - 1) // step)))
            title = f"{day:%d/%m/%Y}: {count:,} {cell.get('unit', 'hotspots')}" if count is not None else f"{day:%d/%m/%Y}: No observations"
            color = HEAT_COLORS[level] if count is not None else "#687080"
            parts.append(f'<span class="calendar-day" role="gridcell" title="{title}" aria-label="{title}" data-date="{day.isoformat()}" style="grid-column:{cell["week"] + 2};grid-row:{row + 2};--day-color:{color}"></span>')
        parts.append('</div>')
    parts.append('</div></div>')
    return ''.join(parts)


def month_metrics_html(summary):
    growth = summary["growth"]
    growth_label = "Change from the previous month"
    if growth is not None:
        growth_label = "Increase from the previous month" if growth >= 0 else "Decrease from the previous month"
    growth_value = f"{abs(growth):g}%" if growth is not None else "N/A"
    cards = [
        ("fire", "orange", f'{summary["total"]:,}', summary.get("unit", "Fire hotspots")),
        ("pie", "orange", f'{summary["annual_share"]:g}%', "of the year's total"),
        ("trend", "red" if growth is None or growth >= 0 else "green", growth_value, growth_label),
        ("pie", "green", "N/A", "Confidence not aggregated" if summary.get("unit") else "Confidence unavailable in demo data"),
    ]
    items = ''.join(f'<article class="month-metric"><span class="month-metric-icon {color}">{icon(name, 48)}</span>'
                    f'<div><strong>{value}</strong><span>{label}</span></div></article>'
                    for name, color, value, label in cards)
    return f'<section class="month-metrics" aria-label="Month summary">{items}</section>'


def legend_html(legend, unit="hotspots"):
    rows = ''.join(f'<div class="calendar-legend-item"><span class="heat-swatch" style="background:{item["color"]}"></span>'
                   f'<span>{item["low"]:,} – {item["high"]:,} {unit}</span></div>' for item in legend)
    return f'<aside class="calendar-legend"><h3>Legend</h3>{rows}</aside>'


def chart_heading(summaries, colors):
    items = ''.join(f'<span><i style="background:{color}"></i>{summary["year"]}</span>' for summary, color in zip(summaries, colors))
    return f'<div class="annual-chart-heading"><strong>Annual Comparison</strong><div class="series-legend">{items}</div></div>'


def key_periods_html(summaries, colors):
    items = ''.join(f'<div class="key-period"><i style="background:{color}"></i><div><strong>{summary["year"]}</strong>'
                    f'<span>{escape(summary["peak_period"])}</span></div></div>' for summary, color in zip(summaries, colors))
    return f'<aside class="key-periods"><h3>Key Periods</h3><div class="key-period-list" tabindex="0" role="region" aria-label="Key periods by year">{items}</div></aside>'


def summary_html(summaries, colors):
    cards = []
    for summary, color in zip(summaries, colors):
        total = f'{summary["total"]:,}'
        growth = summary["growth"]
        note = f'↗ {growth:g}%' if growth is not None else ('Base year' if summary["total"] else 'No data')
        cards.append(f'<article class="year-card"><div class="year-card-label"><i style="background:{color}"></i>{summary["year"]}</div>'
                     f'<div class="year-card-footer"><div class="year-card-total"><strong>{total}</strong><span>{summary.get("unit", "Hotspots")}</span></div>'
                     f'<span class="year-growth">{note}</span></div></article>')
    return f'<section class="annual-summary"><h3>Yearly summary</h3><div class="year-cards" style="--summary-count:{len(cards)}">{"".join(cards)}</div></section>'
