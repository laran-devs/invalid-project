from pathlib import Path
from typing import Optional, Union


class File:
    """Инкапсулирует метаданные файла на диске."""

    SUPPORTED_FORMATS = {"csv", "json", "xml", "xlsx", "xls"}

    def __init__(self, path: Union[str, Path], file_format: Optional[str] = None):
        self.path = Path(path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.path}")

        raw_format = file_format or self.path.suffix.lstrip(".").lower()
        if raw_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Неподдерживаемый формат: '{raw_format}'. "
                f"Допустимые форматы: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )
        self.format = raw_format

    def __repr__(self) -> str:
        return f"File(name='{self.path.name}', format='{self.format}')"