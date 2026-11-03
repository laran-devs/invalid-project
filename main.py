"""Демонстрация совместной работы модулей DataBridge:

1. Инкапсуляция метаданных файлов через класс File (src.models)
2. Чтение данных из 4 форматов (CSV, JSON, XML, Excel) через FileConverter (src.converter)
3. Валидация структуры и значений через ValidationEngine (src.validators)
4. Конвертация валидных данных в формат Apache Parquet
5. Валидация полученного Parquet-файла для подтверждения целостности
6. Корректная обработка и отчетность при обнаружении ошибок
"""

import sys
from pathlib import Path
import pandas as pd

from src.models import File
from src.converter import FileConverter
from src.validators import ValidationEngine, ValidationSchema


def setup_console_encoding() -> None:
    """Обеспечивает корректное отображение кириллицы в Windows-консоли."""
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def process_and_validate_file(
    file_path: Path,
    engine: ValidationEngine,
    processed_dir: Path,
) -> None:
    print(f"\n{'=' * 65}")
    print(f"Файл: {file_path.name}")
    print(f"{'=' * 65}")

    # 1. Чтение файла через класс File
    try:
        file = File(file_path)
        print(f" [1] Метаданные файла: {file}")
    except Exception as e:
        print(f" [!] Ошибка инициализации File: {e}")
        return

    # 2. Чтение файла в DataFrame через FileConverter
    try:
        df = FileConverter.read_to_dataframe(file)
        print(f" [2] Успешно прочитано через FileConverter ({len(df)} строк, {len(df.columns)} колонок)")
    except Exception as e:
        print(f" [!] Ошибка чтения файла через FileConverter: {e}")
        return

    # 3. Валидация данных через ValidationEngine
    print(" [3] Запуск валидации данных по схеме:")
    result = engine.validate_dataframe(df, start_row_index=2)
    result.print_summary()

    # 4. Обработка результата валидации
    if result.is_valid:
        print(" [4] Данные валидны. Запуск конвертации в Parquet...")
        parquet_path = FileConverter.convert_to_parquet(
            file,
            output_dir=processed_dir,
            output_name=f"{file_path.stem}.parquet",
        )
        print(f"     -> Сохранен Parquet: {parquet_path}")

        # 5. Проверка полученного Apache Parquet файла валидатором
        df_parquet = pd.read_parquet(parquet_path)
        parquet_validation = engine.validate_dataframe(df_parquet, start_row_index=2)
        print(f" [5] Валидация результирующего Parquet ({len(df_parquet)} записей): "
              f"{'УСПЕШНО (целостность подтверждена)' if parquet_validation.is_valid else 'ОШИБКА'}")
    else:
        print(" [4] Внимание: Файл содержит ошибки валидации!")
        print("     -> Запись в результирующий Parquet отменена (битые данные не сохраняются).")


def main():
    setup_console_encoding()
    base_dir = Path(__file__).resolve().parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    schema_path = base_dir / "samples" / "schema.yaml"

    print("=================================================================")
    print("      DataBridge: Проверка связки File -> Converter -> Validator ")
    print("=================================================================")

    # Загрузка схемы валидации
    if not schema_path.exists():
        print(f"Файл схемы не найден: {schema_path}")
        return

    schema = ValidationSchema.from_file(schema_path)
    engine = ValidationEngine(schema)
    print(f"Схема правил загружена: {schema_path.name}")
    print(f"Проверяемые поля: {', '.join(schema.fields.keys())}")

    # Список файлов для проверки: 4 валидных формата (CSV, JSON, XML, Excel) + 1 невалидный
    test_files = [
        raw_dir / "test_data.csv",
        raw_dir / "test_data.json",
        raw_dir / "test_data.xml",
        raw_dir / "test_data.xlsx",
        base_dir / "samples" / "invalid.csv",
    ]

    for file_path in test_files:
        if file_path.exists():
            process_and_validate_file(file_path, engine, processed_dir)
        else:
            print(f"\n[!] Файл не найден: {file_path}")

    print("\n" + "=" * 65)
    print("Тестирование связки всех компонентов завершено.")
    print("=" * 65)


if __name__ == "__main__":
    main()
