# NasaChallenge2026

A Python and Streamlit application for visualizing and analyzing MODIS and VIIRS fire hotspot data.

## Requirements

- Python with `pip` and `venv` support, available through the `python` command.
- Internet access on the first run to install dependencies.
- A terminal open at the project root, where `run.py` is located.


## Run the project

In PowerShell, from the project directory:

```powershell
python --version
python run.py
```

The launcher creates `frontend/.venv`, installs `frontend/requirements.txt`, checks dependencies, and starts Streamlit. You do not need to activate the virtual environment or change the PowerShell execution policy. The first run may take a while because of dependency downloads.

Open the address shown in the terminal, usually <http://localhost:8501>. Keep the terminal open while using the application; press `Ctrl+C` to stop it.

------------------------------------------------------------------------------------
By default, the application looks for Parquet parts in:

```text
backend/data/processed/
  modis/2020/brazil/part-001.parquet
  viirs/2020/brazil/part-001.parquet
```

If these files already exist, simply run `python run.py`; there is no need to import them again. Without published parts, the application uses synthetic demo data. When real data is available, select a region and period covered by the files; selections with no records remain empty.



## Team Members & Contributions

| Member | Role | Contributions |
|---|---|---|
| Karen Yuzawa | UI/UX Designer | Wireframes, prototyping and interface design |
| Kelly Yuzawa | Developer | Frontend implementation and data integration |
| Nancy Yuzawa | Developer | Backend and data integration |
