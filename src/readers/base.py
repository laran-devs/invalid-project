from abc import ABC, abstractmethod
from pathlib import Path
import pandas as pd


class BaseReader(ABC):

    @abstractmethod
    def read(self, path: Path) -> pd.DataFrame:
        pass
