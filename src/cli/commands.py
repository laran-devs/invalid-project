import sys
from pathlib import Path
from ..readers import ReaderFactory
from ..validators import ValidationEngine
from ..converters import ConversionPipeline
from ..reporters import HTMLReporter, StatsReporter


def handle_convert(args) -> int:
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"Ошибка: входной файл не найден: {input_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else None
    schema_file = args.config if args.config else "schema.json"

    try:
        saved_file, errors_file, val_result = ConversionPipeline.convert_pipeline(
            file=input_path,
            target_format=args.to,
            schema_path=schema_file,
            output_path=output_path,
            report_path=args.report,
        )

        out_name = saved_file.name if saved_file else None
        err_name = errors_file.name if errors_file else None
        rep_name = Path(args.report).name if args.report else None

        print(val_result.summary(output_file=out_name, errors_file=err_name, report_file=rep_name))
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
        val_result = ValidationEngine.validate(input_path, schema_file)

        report_name = None
        if args.report:
            report_path = Path(args.report)
            HTMLReporter.generate(val_result, report_path)
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
        print(StatsReporter.report_file(input_path))
        return 0
    except Exception as e:
        print(f"Ошибка при анализе файла: {e}", file=sys.stderr)
        return 1
