"""CLI-команда для валидации файлов данных по схеме."""

import argparse
import csv
import sys
from pathlib import Path

from .engine import ValidationEngine
from .schema import ValidationSchema


def run_cli(args: list = None) -> int:
    # Настройка вывода UTF-8 для корректного отображения кириллицы в Windows консоли
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="DataBridge Validator: проверка файлов данных на соответствие схеме правил."
    )
    parser.add_argument("input", help="Путь к файлу данных для валидации (CSV, JSON, Excel, XML)")
    parser.add_argument(
        "--config", "-c", required=True, help="Путь к файлу схемы валидации (YAML или JSON)"
    )
    parser.add_argument(
        "--errors-out", "-e", default=None, help="Путь для сохранения списка ошибок (например, errors.csv)"
    )

    parsed = parser.parse_args(args)

    input_path = Path(parsed.input)
    config_path = Path(parsed.config)

    if not input_path.exists():
        print(f"Ошибка: входной файл не найден: {input_path}", file=sys.stderr)
        return 2

    if not config_path.exists():
        print(f"Ошибка: файл конфигурации не найден: {config_path}", file=sys.stderr)
        return 2

    try:
        schema = ValidationSchema.from_file(config_path)
        engine = ValidationEngine(schema)
        result = engine.validate_file(input_path)
    except Exception as e:
        print(f"Ошибка обработки: {e}", file=sys.stderr)
        return 3

    # Вывод сводки
    result.print_summary()

    # Сохранение ошибок в CSV, если запрошено
    if parsed.errors_out and result.errors:
        out_err_path = Path(parsed.errors_out)
        out_err_path.parent.mkdir(parents=True, exist_ok=True)
        errors_data = result.to_errors_dict_list()
        with open(out_err_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["row", "field", "value", "rule", "message"])
            writer.writeheader()
            writer.writerows(errors_data)
        print(f"Ошибки сохранены: {out_err_path}")

    return 0 if result.is_valid else 1


if __name__ == "__main__":
    sys.exit(run_cli())
