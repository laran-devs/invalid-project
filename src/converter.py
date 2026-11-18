import json
from pathlib import Path
from typing import Dict, List, Optional, Union
import pandas as pd
from .models import File


class FileConverter:
    """Автоматический конвертер между табличными форматами данных."""

    SUPPORTED_OUTPUT_FORMATS = {"csv", "json", "xml", "xlsx"}

    @staticmethod
    def load_config(config: Optional[Union[str, Path, dict]] = None) -> dict:
        """Загружает настройки из config.json или переданного пути/словаря."""
        defaults = {
            "save_intermediate_parquet": True,
            "intermediate_dir": "data/processed",
            "output_dir": "data/output",
            "schema_path": "schema.json",
        }
        if config is None:
            default_path = Path("config.json")
            if default_path.exists():
                with open(default_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    defaults.update(cfg)
            return defaults

        if isinstance(config, (str, Path)):
            path = Path(config)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    defaults.update(cfg)
            return defaults

        if isinstance(config, dict):
            defaults.update(config)
            return defaults

        raise TypeError("Конфигурация должна быть путем к JSON-файлу или словарем")

    @staticmethod
    def _apply_single_transform(series: pd.Series, transform_name: str) -> pd.Series:
        """Применяет отдельное правило трансформации к колонке."""
        norm_name = transform_name.strip().lower()

        if norm_name in ("trim", "strip"):
            return series.map(lambda x: x.strip() if isinstance(x, str) else x)

        elif norm_name in ("lowercase", "lower"):
            return series.map(lambda x: x.lower() if isinstance(x, str) else x)

        elif norm_name in ("uppercase", "upper"):
            return series.map(lambda x: x.upper() if isinstance(x, str) else x)

        elif norm_name in ("timestamp_to_date", "to_date"):
            def _to_date(val):
                if pd.isna(val) or val is None or val == "":
                    return val
                try:
                    num = float(val)
                    unit = "ms" if num > 1e11 else "s"
                    return pd.to_datetime(num, unit=unit).strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    try:
                        return pd.to_datetime(val).strftime("%Y-%m-%d")
                    except Exception:
                        return val

            return series.map(_to_date)

        else:
            raise ValueError(
                f"Неизвестная трансформация: '{transform_name}'. "
                f"Допустимые: trim, strip, lowercase, lower, uppercase, upper, timestamp_to_date"
            )

    @classmethod
    def apply_transformations(
        cls,
        df: pd.DataFrame,
        schema: Union[str, Path, dict],
    ) -> pd.DataFrame:
        """Применяет трансформации (trim, case, timestamp_to_date) по правилам из схемы."""
        if isinstance(schema, (str, Path)):
            path = Path(schema)
            if not path.exists():
                return df
            with open(path, "r", encoding="utf-8") as f:
                schema_dict = json.load(f)
        elif isinstance(schema, dict):
            schema_dict = schema
        else:
            return df

        fields = schema_dict.get("fields", [])
        df = df.copy()

        for fld in fields:
            name = fld.get("name")
            target_name = fld.get("target_name")
            col = name if name in df.columns else (target_name if target_name in df.columns else None)
            if not col:
                continue

            transforms = fld.get("transform") or fld.get("transforms") or fld.get("transformations")
            if not transforms:
                continue

            if isinstance(transforms, str):
                transforms = [transforms]

            for tr in transforms:
                df[col] = cls._apply_single_transform(df[col], tr)

        return df

    @staticmethod
    def get_column_mappings(schema: Union[str, Path, dict]) -> Dict[str, str]:
        """Извлекает словарь маппинга {name: target_name} из схемы."""
        if isinstance(schema, (str, Path)):
            path = Path(schema)
            if not path.exists():
                return {}
            with open(path, "r", encoding="utf-8") as f:
                schema_dict = json.load(f)
        elif isinstance(schema, dict):
            schema_dict = schema
        else:
            return {}

        fields = schema_dict.get("fields", [])
        return {
            fld["name"]: fld["target_name"]
            for fld in fields
            if "name" in fld and fld.get("target_name")
        }

    @classmethod
    def apply_column_mappings(
        cls,
        df: pd.DataFrame,
        schema: Union[str, Path, dict],
    ) -> pd.DataFrame:
        """Переименовывает колонки DataFrame в соответствии с target_name из схемы."""
        mappings = cls.get_column_mappings(schema)
        if mappings:
            return df.rename(columns=mappings)
        return df

    @staticmethod
    def read_to_dataframe(file: File) -> pd.DataFrame:
        """Считывает файл поддерживаемого входного формата в DataFrame."""
        match file.format:
            case "csv":
                return pd.read_csv(
                    file.path,
                    sep=None,
                    engine="python",
                    encoding="utf-8-sig",
                )

            case "json":
                return pd.read_json(file.path)

            case "xml":
                return pd.read_xml(file.path)

            case "xlsx":
                return pd.read_excel(file.path, sheet_name=0, engine="openpyxl")

            case "xls":
                try:
                    return pd.read_excel(file.path, sheet_name=0, engine="xlrd")
                except ImportError:
                    return pd.read_excel(file.path, sheet_name=0)

            case _:
                raise ValueError(
                    f"Неподдерживаемый формат для чтения: '{file.format}'. "
                    f"Допустимые входные форматы: {', '.join(sorted(File.SUPPORTED_FORMATS))}"
                )

    @classmethod
    def write_dataframe(
        cls,
        df: pd.DataFrame,
        target_path: Union[str, Path],
        target_format: Optional[str] = None,
    ) -> Path:
        """Записывает DataFrame в указанный целевой формат."""
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
                # Внутренняя запись в Parquet (для промежуточного сохранения)
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

    @classmethod
    def convert(
        cls,
        file: File,
        target_format: str,
        output_dir: Optional[Union[str, Path]] = None,
        output_name: Optional[str] = None,
        config: Optional[Union[str, Path, dict]] = None,
        schema: Optional[Union[str, Path, dict]] = None,
        save_intermediate_parquet: Optional[bool] = None,
        apply_transforms: bool = True,
        apply_mapping: bool = True,
    ) -> Path:
        """
        Конвертирует входной файл в один из выходных форматов (csv, json, xml, xlsx).
        Последовательность конвейера:
        1. Чтение исходного файла
        2. Применение трансформаций (trim, uppercase/lowercase, timestamp_to_date)
        3. Промежуточное сохранение в Parquet (если включено в конфиге)
        4. Маппинг колонок (target_name)
        5. Сохранение в итоговый формат в output_dir
        """
        target_fmt = target_format.lstrip(".").lower()

        if target_fmt == "parquet":
            raise ValueError(
                "Формат 'parquet' является исключительно промежуточным "
                "и недоступен в качестве целевого формата. "
                f"Допустимые выходные форматы: {', '.join(sorted(cls.SUPPORTED_OUTPUT_FORMATS))}"
            )

        if target_fmt not in cls.SUPPORTED_OUTPUT_FORMATS:
            if target_fmt == "xls":
                raise ValueError(
                    "Запись в устаревший формат '.xls' не поддерживается. "
                    "Для Excel используйте формат '.xlsx'."
                )
            raise ValueError(
                f"Неподдерживаемый целевой формат: '{target_fmt}'. "
                f"Допустимые выходные форматы: {', '.join(sorted(cls.SUPPORTED_OUTPUT_FORMATS))}"
            )

        cfg = cls.load_config(config)

        should_save_parquet = (
            save_intermediate_parquet
            if save_intermediate_parquet is not None
            else cfg.get("save_intermediate_parquet", True)
        )

        df = cls.read_to_dataframe(file)
        schema_to_use = schema or cfg.get("schema_path", "schema.json")

        # 1. Трансформации данных
        if apply_transforms and schema_to_use:
            df = cls.apply_transformations(df, schema_to_use)

        # 2. Промежуточный Parquet (сохраняется с исходными именами, но трансформированными данными)
        if should_save_parquet:
            inter_dir = Path(cfg.get("intermediate_dir", "data/processed")).resolve()
            inter_path = inter_dir / f"{file.path.stem}.parquet"
            cls.write_dataframe(df, inter_path, "parquet")

        # 3. Маппинг колонок (переименование по target_name из schema.json)
        if apply_mapping and schema_to_use:
            df = cls.apply_column_mappings(df, schema_to_use)

        # 4. Сохранение в итоговый формат
        out_dir = Path(output_dir or cfg.get("output_dir", "data/output")).resolve()
        filename = output_name or f"{file.path.stem}.{target_fmt}"
        target_path = out_dir / filename

        return cls.write_dataframe(df, target_path, target_fmt)

    @classmethod
    def convert_to_parquet(
        cls,
        file: File,
        output_dir: Optional[Union[str, Path]] = None,
        output_name: Optional[str] = None,
    ) -> Path:
        """Конвертирует переданный File в Parquet (сохранено для обратной совместимости)."""
        target_dir = Path(output_dir or "data/processed").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = output_name or f"{file.path.stem}.parquet"
        target_path = target_dir / filename
        df = cls.read_to_dataframe(file)
        return cls.write_dataframe(df, target_path, "parquet")
