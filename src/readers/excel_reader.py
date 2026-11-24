from pathlib import Path
import pandas as pd
from .base import BaseReader


class ExcelReader(BaseReader):

    def read(self, path: Path) -> pd.DataFrame:
        p = Path(path).resolve()
        ext = p.suffix.lower()
        if ext == ".xlsx":
            return pd.read_excel(p, sheet_name=0, engine="openpyxl")
        elif ext == ".xls":
            try:
                return pd.read_excel(p, sheet_name=0, engine="xlrd")
            except ImportError:
                return pd.read_excel(p, sheet_name=0)
        return pd.read_excel(p, sheet_name=0)
