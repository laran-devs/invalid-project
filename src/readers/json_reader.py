from pathlib import Path
import pandas as pd
from .base import BaseReader


class JSONReader(BaseReader):

    def read(self, path: Path) -> pd.DataFrame:
        p = Path(path).resolve()
        return pd.read_json(p)
