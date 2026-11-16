"""Gera amostra sintética versionada; não baixa dados NASA."""
import csv
from pathlib import Path

def main():
    target = Path(__file__).resolve().parents[1]/"data/sample/hotspots.csv"
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("w",encoding="utf-8",newline="") as stream:
        out = csv.writer(stream)
        out.writerow(["sensor","satellite","acq_date","acq_time","latitude","longitude","confidence","frp"])
        for year in range(2020,2026):
            for month in range(1,13):
                for lat,lon in [(-22.9064,-47.0616),(-3.119,-60.0217)]:
                    for sensor in ("MODIS","VIIRS"):
                        count = 1+int((6 if 7<=month<=10 else 2)*(1+(year-2020)*.18))*(2 if sensor=="VIIRS" else 1)
                        for k in range(count):
                            out.writerow([sensor,"T" if sensor=="MODIS" else "N20",f"{year}-{month:02d}-{4+k%22:02d}","1200",f"{lat+(k//22)*.02:.5f}",lon,"80" if sensor=="MODIS" else "n",12.0])
    print(target)

if __name__ == "__main__":
    main()
