import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="databridge",
        description="DataBridge: утилита конвертации, валидации и анализа табличных данных.",
    )
    subparsers = parser.add_subparsers(dest="command")

    p_convert = subparsers.add_parser("convert", help="Конвертация файла в целевой формат")
    p_convert.add_argument("file", help="Входной файл (csv, json, xml, xlsx, xls)")
    p_convert.add_argument("--to", required=True, choices=["csv", "json", "xml", "xlsx"], help="Целевой формат")
    p_convert.add_argument("--config", default="schema.json", help="Путь к файлу схемы JSON/YAML (по умолчанию: schema.json)")
    p_convert.add_argument("--output", "-o", default=None, help="Путь для сохранения результата")
    p_convert.add_argument("--report", "-r", default=None, help="Путь для генерации HTML-отчета")

    p_validate = subparsers.add_parser("validate", help="Валидация файла по схеме")
    p_validate.add_argument("file", help="Файл для проверки")
    p_validate.add_argument("--config", default="schema.json", help="Путь к файлу схемы JSON/YAML (по умолчанию: schema.json)")
    p_validate.add_argument("--report", "-r", default=None, help="Путь для генерации HTML-отчета")

    p_stats = subparsers.add_parser("stats", help="Профилирование данных файла")
    p_stats.add_argument("file", help="Файл для анализа")

    return parser
