"""Calendário e cartões da página de atividade."""

from html import escape

from activity_data import HEAT_COLORS, MONTH_LABELS


def calendar_html(cells, legend):
    weeks = max(cell["week"] for cell in cells) + 1
    focused = len({cell["date"].month for cell in cells}) == 1
    frame_class = "calendar-canvas calendar-canvas--month" if focused else "calendar-canvas"
    parts = [f'<div class="{frame_class}" style="--calendar-ratio:{(weeks + 1) / 8:.4f}">',
             f'<div class="activity-heatmap" role="grid" aria-label="Daily fire hotspots calendar" aria-rowcount="8" aria-colcount="{weeks + 1}" style="--calendar-weeks:{weeks}">',
             '<div class="calendar-row" role="row">']
    seen_months = set()
    for cell in cells:
        day = cell["date"]
        if day.month not in seen_months:
            parts.append(f'<span class="calendar-month" role="columnheader" style="grid-column:{cell["week"] + 2};grid-row:1">{MONTH_LABELS[day.month - 1]}</span>')
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
            level = min(5, max(0, (count - 1) // step))
            title = f"{day:%d/%m/%Y}: {count:,} hotspots"
            parts.append(f'<span class="calendar-day" role="gridcell" title="{title}" aria-label="{title}" data-date="{day.isoformat()}" style="grid-column:{cell["week"] + 2};grid-row:{row + 2};--day-color:{HEAT_COLORS[level]}"></span>')
        parts.append('</div>')
    parts.append('</div></div>')
    return ''.join(parts)


def legend_html(legend):
    rows = ''.join(f'<div class="calendar-legend-item"><span class="heat-swatch" style="background:{item["color"]}"></span>'
                   f'<span>{item["low"]:,} – {item["high"]:,} hotspots</span></div>' for item in legend)
    return f'<aside class="calendar-legend"><h3>Legend</h3>{rows}</aside>'


def chart_heading(summaries, colors):
    items = ''.join(f'<span><i style="background:{color}"></i>{summary["year"]}</span>' for summary, color in zip(summaries, colors))
    return f'<div class="annual-chart-heading"><strong>Annual Comparison</strong><div class="series-legend">{items}</div></div>'


def key_periods_html(summaries, colors):
    items = ''.join(f'<div class="key-period"><i style="background:{color}"></i><div><strong>{summary["year"]}</strong>'
                    f'<span>{escape(summary["peak_period"])}</span></div></div>' for summary, color in zip(summaries, colors))
    return f'<aside class="key-periods"><h3>Key Periods</h3>{items}</aside>'


def summary_html(summaries, colors):
    cards = []
    for summary, color in zip(summaries, colors):
        total = f'{summary["total"]:,}'
        growth = summary["growth"]
        note = f'↗ {growth:g}%' if growth is not None else ('Base year' if summary["total"] else 'No data')
        cards.append(f'<article class="year-card"><div class="year-card-label"><i style="background:{color}"></i>{summary["year"]}</div>'
                     f'<div class="year-card-footer"><div class="year-card-total"><strong>{total}</strong><span>Hotspots</span></div>'
                     f'<span class="year-growth">{note}</span></div></article>')
    return f'<section class="annual-summary"><h3>Yearly summary</h3><div class="year-cards" style="--summary-count:{len(cards)}">{"".join(cards)}</div></section>'
