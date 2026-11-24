from pathlib import Path
from typing import Optional, Set, Union
import pandas as pd


class DataWriter:
    SUPPORTED_OUTPUT_FORMATS: Set[str] = {"csv", "json", "xml", "xlsx", "parquet"}

    @classmethod
    def write(
        cls,
        df: pd.DataFrame,
        target_path: Union[str, Path],
        target_format: Optional[str] = None,
    ) -> Path:
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        fmt = (target_format or target.suffix.lstrip(".")).lower()

        match fmt:
            case "csv":
                df.to_csv(target, index=False, encoding="utf-8-sig")

            case "json":
                df.to_json(
                    target,
                    orient="records",
                    force_ascii=False,
                    indent=2,
                    date_format="iso",
                )

            case "xml":
                df.to_xml(
                    target,
                    index=False,
                    root_name="data",
                    row_name="row",
                    encoding="utf-8",
                )

            case "xlsx":
                df.to_excel(target, index=False, engine="openpyxl")

            case "parquet":
                df.to_parquet(
                    target,
                    engine="pyarrow",
                    compression="snappy",
                    index=False,
                )

            case "xls":
                raise ValueError(
                    "Запись в устаревший формат '.xls' не поддерживается. "
                    "Для Excel используйте формат '.xlsx'."
                )

            case _:
                raise ValueError(
                    f"Неподдерживаемый формат для записи: '{fmt}'. "
                    f"Допустимые форматы: {', '.join(sorted(cls.SUPPORTED_OUTPUT_FORMATS))}"
                )

        return target
