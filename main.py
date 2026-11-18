import argparse
import sys
from pathlib import Path
from src import File, FileConverter, ParquetValidator, get_dataframe_stats


def handle_convert(args) -> int:
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"Ошибка: входной файл не найден: {input_path}", file=sys.stderr)
        return 1

    file_obj = File(input_path)
    output_path = Path(args.output) if args.output else None
    schema_file = args.config if args.config else "schema.json"

    try:
        saved_file, errors_file, val_result = FileConverter.convert_pipeline(
            file=file_obj,
            target_format=args.to,
            schema_path=schema_file,
            output_path=output_path,
        )

        out_name = saved_file.name if saved_file else None
        err_name = errors_file.name if errors_file else None

        print(val_result.summary(output_file=out_name, errors_file=err_name))
        return 0
    except Exception as e:
        print(f"Ошибка при конвертации: {e}", file=sys.stderr)
        return 1


def handle_validate(args) -> int:
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"Ошибка: файл не найден: {input_path}", file=sys.stderr)
        return 1

    schema_file = args.config if args.config else "schema.json"
    if not Path(schema_file).exists():
        print(f"Ошибка: файл схемы не найден: {schema_file}", file=sys.stderr)
        return 1

    try:
        if input_path.suffix.lower() == ".parquet":
            val_result = ParquetValidator.validate(input_path, schema_file)
        else:
            file_obj = File(input_path)
            df = FileConverter.read_to_dataframe(file_obj)
            val_result = ParquetValidator.validate(df, schema_file)

        report_name = None
        if args.report:
            report_path = Path(args.report)
            val_result.generate_html_report(report_path)
            report_name = report_path.name

        print(val_result.summary(report_file=report_name))
        return 0 if val_result.is_valid else 1
    except Exception as e:
        print(f"Ошибка при валидации: {e}", file=sys.stderr)
        return 1


def handle_stats(args) -> int:
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"Ошибка: файл не найден: {input_path}", file=sys.stderr)
        return 1

    try:
        file_obj = File(input_path)
        df = FileConverter.read_to_dataframe(file_obj)
        file_size = input_path.stat().st_size
        print(get_dataframe_stats(df, file_size=file_size))
        return 0
    except Exception as e:
        print(f"Ошибка при анализе файла: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="databridge",
        description="DataBridge: утилита конвертации, валидации и анализа табличных данных.",
    )
    subparsers = parser.add_subparsers(dest="command")

    p_convert = subparsers.add_parser("convert", help="Конвертация файла в целевой формат")
    p_convert.add_argument("file", help="Входной файл (csv, json, xml, xlsx, xls)")
    p_convert.add_argument("--to", required=True, choices=["csv", "json", "xml", "xlsx"], help="Целевой формат")
    p_convert.add_argument("--config", default="schema.json", help="Путь к файлу схемы JSON (по умолчанию: schema.json)")
    p_convert.add_argument("--output", "-o", default=None, help="Путь для сохранения результата")

    p_validate = subparsers.add_parser("validate", help="Валидация файла по схеме")
    p_validate.add_argument("file", help="Файл для проверки")
    p_validate.add_argument("--config", default="schema.json", help="Путь к файлу схемы JSON (по умолчанию: schema.json)")
    p_validate.add_argument("--report", "-r", default=None, help="Путь для генерации HTML-отчета")

    p_stats = subparsers.add_parser("stats", help="Профилирование данных файла")
    p_stats.add_argument("file", help="Файл для анализа")

    return parser


def cli() -> None:
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.command == "convert":
        sys.exit(handle_convert(args))
    elif args.command == "validate":
        sys.exit(handle_validate(args))
    elif args.command == "stats":
        sys.exit(handle_stats(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    cli()
