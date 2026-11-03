from pathlib import Path
from typing import Optional, Union
import pandas as pd
from .models import File


class FileConverter:
    """Автоматический конвертер файлов в Parquet с фиксированными параметрами по умолчанию."""

    @staticmethod
    def read_to_dataframe(file: File) -> pd.DataFrame:
        """Считывает файл с безопасными настройками по умолчанию."""
        match file.format:
            case "csv":
                # sep=None + engine='python' заставляют pandas автоматически
                # распознать разделитель (, ; \t |) по первым строкам файла
                return pd.read_csv(
                    file.path,
                    sep=None,
                    engine="python",
                    encoding="utf-8-sig"  # корректно читает UTF-8 с BOM и обычный UTF-8
                )

            case "json":
                # Ожидается стандартный массив объектов: [{"col1": val, ...}, ...]
                return pd.read_json(file.path)

            case "xml":
                # Читает плоские записи тегов второго уровня
                return pd.read_xml(file.path)

            case "xlsx" | "xls":
                # Всегда читает первый активный лист
                return pd.read_excel(file.path, sheet_name=0)

            case _:
                raise ValueError(f"Неподдерживаемый формат: {file.format}")

    @classmethod
    def convert_to_parquet(
        cls,
        file: File,
        output_dir: Optional[Union[str, Path]] = None,
        output_name: Optional[str] = None,
    ) -> Path:
        """Конвертирует переданный File в Parquet со стандартным сжатием Snappy."""
        target_dir = Path(output_dir).resolve() if output_dir else file.path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = output_name or f"{file.path.stem}.parquet"
        target_path = target_dir / filename

        df = cls.read_to_dataframe(file)

        df.to_parquet(
            target_path,
            engine="pyarrow",
            compression="snappy",
            index=False
        )

        return target_path