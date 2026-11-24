from pathlib import Path
from typing import Optional, Union
import pandas as pd
from .base import BaseReader


class CSVReader(BaseReader):

    def __init__(self, sep: Optional[str] = None, header: Optional[Union[int, str]] = "infer"):
        self.sep = sep
        self.header = header

    def read(self, path: Path) -> pd.DataFrame:
        p = Path(path).resolve()
        return pd.read_csv(
            p,
            sep=self.sep,
            engine="python",
            encoding="utf-8-sig",
            header=self.header,
        )
