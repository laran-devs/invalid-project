from pathlib import Path
import pandas as pd
from .base import BaseReader


class XMLReader(BaseReader):

    def read(self, path: Path) -> pd.DataFrame:
        p = Path(path).resolve()
        return pd.read_xml(p)
