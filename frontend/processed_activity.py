"""Activity adapter: observed daily cells and harmonized annual comparisons."""
from calendar import monthrange
from datetime import date, timedelta
import activity_data as demo
from activity_data import MONTH_NAMES, MONTH_LABELS, SERIES_COLORS, SENSORS, HEAT_COLORS
from processed_data import dataset_status, available_years, daily_data, monthly_analysis, harmonize_monthly


def years():
    return available_years() or demo.AVAILABLE_YEARS


def _sensors(sensors):
    selected = list(sensors or SENSORS)
    if not set(selected).issubset(SENSORS):
        raise ValueError("Unknown sensor.")
    return selected


def daily_activity(year, filters=None, sensors=None):
    if dataset_status()["demo"]:
        return demo.daily_activity(year, filters, sensors)
    daily = daily_data(filters, _sensors(sensors))
    monthly, _ = harmonize_monthly(daily, (date(year,1,1), date(year,12,31)))
    result = {}
    factor = monthly.attrs.get("calibration_factor") or 1.0
    for row in monthly.itertuples():
        sensor = "MODIS" if row.method == "MODIS reference" else "VIIRS"
        selected = daily[(daily.sensor == sensor) & daily.acq_date.str.startswith(row.month)]
        scale = factor if row.method == "VIIRS calibrated" else 1.0
        result.update({date.fromisoformat(day.acq_date): float(day.cells)*scale for day in selected.itertuples()})
    return result


def annual_series(year, filters=None, sensors=None):
    if dataset_status()["demo"]:
        return demo.annual_series(year, filters, sensors)
    daily = daily_activity(year, filters, sensors)
    return [sum(n for day,n in daily.items() if day.month==m) if any(day.month==m for day in daily) else None for m in range(1,13)]


def calendar_cells(year, month=0, filters=None, sensors=None):
    if dataset_status()["demo"]:
        return demo.calendar_cells(year, month, filters, sensors)
    counts = daily_activity(year,filters,sensors)
    start = date(year,month or 1,1)
    end = date(year,month,monthrange(year,month)[1]) if month else date(year,12,31)
    origin = start-timedelta(days=(start.weekday()+1)%7)
    return [dict(date=day,count=counts.get(day),week=(day-origin).days//7,weekday=(day.weekday()+1)%7,
                 unit="cell-days") for day in (start+timedelta(days=i) for i in range((end-start).days+1))]


def heat_legend(counts):
    values = [n for n in counts if n is not None]
    if dataset_status()["demo"]:
        return demo.heat_legend(values)
    maximum = max(values, default=0)
    step = maximum/6 if maximum else 1.0
    return [dict(color=color,low=round(i*step,2),high=round((i+1)*step,2),step=step,continuous=True)
            for i,color in enumerate(HEAT_COLORS)]


def annual_summary(year, filters=None, sensors=None):
    if dataset_status()["demo"]:
        return demo.annual_summary(year,filters,sensors)
    values = annual_series(year,filters,sensors)
    previous = annual_series(year-1,filters,sensors)
    comparable = all((a is None)==(b is None) for a,b in zip(values,previous))
    total, baseline = sum(n or 0 for n in values),sum(n or 0 for n in previous)
    monthly, _ = monthly_analysis((date(year,1,1),date(year,12,31)),filters,_sensors(sensors))
    older, _ = monthly_analysis((date(year-1,1,1),date(year-1,12,31)),filters,_sensors(sensors))
    calibrated = not monthly.empty and monthly.calibrated.all() and not older.empty and older.calibrated.all()
    peak = max(range(10),key=lambda i:sum(n or 0 for n in values[i:i+3]))
    return dict(year=year,series=values,total=total,
                growth=round((total/baseline-1)*100,1) if comparable and baseline and calibrated else None,
                peak_period=f"{MONTH_NAMES[peak]} to {MONTH_NAMES[peak+2]}" if total else "No data",
                unit="Cell-days")


def month_summary(year,month,filters=None,sensors=None):
    if dataset_status()["demo"]:
        return demo.month_summary(year,month,filters,sensors)
    counts = daily_activity(year,filters,sensors)
    days = [(date(year,month,d),counts.get(date(year,month,d))) for d in range(1,monthrange(year,month)[1]+1)]
    total = sum(n or 0 for _,n in days)
    annual = sum(counts.values())
    return dict(year=year,month=month,days=days,total=total,annual_share=round(total/annual*100,1) if annual else 0,
                growth=None,confidence=None,unit="Cell-days")
