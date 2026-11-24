from pathlib import Path
from typing import Dict, Type, Union
import pandas as pd
from .base import BaseReader
from .csv_reader import CSVReader
from .json_reader import JSONReader
from .xml_reader import XMLReader
from .excel_reader import ExcelReader


class ReaderFactory:
    _readers: Dict[str, Type[BaseReader]] = {
        ".csv": CSVReader,
        ".json": JSONReader,
        ".xml": XMLReader,
        ".xlsx": ExcelReader,
        ".xls": ExcelReader,
    }

    @classmethod
    def register_reader(cls, extension: str, reader_cls: Type[BaseReader]) -> None:
        ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        cls._readers[ext] = reader_cls

    @classmethod
    def get_reader(cls, path: Union[str, Path]) -> BaseReader:
        p = Path(path)
        ext = p.suffix.lower()
        reader_cls = cls._readers.get(ext)
        if not reader_cls:
            supported = ", ".join(sorted(cls._readers.keys()))
            raise ValueError(f"Неподдерживаемый формат файла: '{ext}'. Поддерживаемые: {supported}")
        return reader_cls()

    @classmethod
    def read(cls, path: Union[str, Path]) -> pd.DataFrame:
        p = Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Файл не найден: {p}")
        if p.suffix.lower() == ".parquet":
            return pd.read_parquet(p)
        reader = cls.get_reader(p)
        return reader.read(p)
