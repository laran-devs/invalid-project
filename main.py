from pathlib import Path
from src import File, FileConverter, ParquetValidator


def main():
    base_dir = Path(__file__).resolve().parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    schema_path = base_dir / "schema.json"

    if not schema_path.exists():
        print(f"Ошибка: файл схемы не найден по пути {schema_path}")
        return

    # Список форматов и соответствующих тестовых файлов
    test_files = sorted(
        [f for f in raw_dir.iterdir() if f.name.startswith(("valid_", "invalid_"))],
        key=lambda f: (f.suffix, f.name)
    )

    if not test_files:
        print(f"В папке {raw_dir} не найдено тестовых файлов.")
        return

    print("=" * 70)
    print("  ТЕСТИРОВАНИЕ КОНВЕРТАЦИИ В PARQUET И ВАЛИДАЦИИ ПО JSON-СХЕМЕ")
    print("=" * 70)
    print(f"Схема валидации: {schema_path.name}\n")

    passed_count = 0
    total_count = len(test_files)

    for test_file in test_files:
        is_expected_valid = test_file.name.startswith("valid_")
        expected_label = "ВАЛИДНЫЙ" if is_expected_valid else "НЕВАЛИДНЫЙ"
        print(f"Файл: {test_file.name} [{expected_label}]")

        try:
            # 1. Конвертация в Parquet
            file_obj = File(test_file)
            parquet_path = FileConverter.convert_to_parquet(file_obj, output_dir=processed_dir)
            print(f"  [+] Конвертация в Parquet: УСПЕШНО -> {parquet_path.name}")

            # 2. Валидация Parquet по JSON-схеме
            result = ParquetValidator.validate(parquet_path, schema_path)

            if is_expected_valid:
                if result.is_valid:
                    print(f"  [+] Валидация: УСПЕШНО (ошибок нет, как и ожидалось)")
                    passed_count += 1
                else:
                    print(f"  [-] Валидация: ОШИБКА (ожидался валидный файл, но найдены ошибки):")
                    for err in result.errors:
                        print(f"      - {err}")
            else:
                if not result.is_valid:
                    print(f"  [+] Валидация: УСПЕШНО (найдено {len(result.errors)} ошибок, как и ожидалось):")
                    for err in result.errors[:3]:
                        print(f"      - {err}")
                    if len(result.errors) > 3:
                        print(f"      ... и ещё {len(result.errors) - 3} ошибок")
                    passed_count += 1
                else:
                    print(f"  [-] Валидация: ОШИБКА (ожидались ошибки, но файл прошел как валидный!)")

        except Exception as e:
            print(f"  [-] Исключение при обработке: {e}")

        print("-" * 70)

    print(f"\nИТОГ: {passed_count} из {total_count} тестов успешно пройдено.")


if __name__ == "__main__":
    main()
