import os
import sys
from pathlib import Path
from typing import List, Optional
import json

from src import File, FileConverter, ParquetValidator


def clear_screen() -> None:
    """Очищает экран консоли кроссплатформенно."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(subtitle: str = "") -> None:
    """Выводит фиксированную шапку приложения."""
    clear_screen()
    print("┌" + "─" * 68 + "┐")
    print("│" + "DATABRIDGE CONSOLE".center(68) + "│")
    print("│" + "Конвертация, валидация и трансформация данных".center(68) + "│")
    if subtitle:
        print("├" + "─" * 68 + "┤")
        print("│  " + subtitle.ljust(66) + "│")
    print("└" + "─" * 68 + "┘")


def format_size(size_bytes: int) -> str:
    """Форматирует размер файла в человекочитаемый вид."""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    return f"{size_bytes / (1024 * 1024):.1f} МБ"


def get_raw_files(raw_dir: Path) -> List[Path]:
    """Возвращает список поддерживаемых файлов в папке data/raw/."""
    if not raw_dir.exists():
        return []
    valid_exts = {f".{fmt}" for fmt in File.SUPPORTED_FORMATS}
    return sorted(
        [f for f in raw_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_exts],
        key=lambda f: f.name.lower(),
    )


def screen_convert_single(base_dir: Path, cfg: dict) -> None:
    """Экран: пошаговая конвертация одного файла."""
    raw_dir = base_dir / cfg.get("raw_dir", "data/raw")
    files = get_raw_files(raw_dir)

    print_header("Главная > Конвертация файла > Шаг 1: Выбор файла")

    if not files:
        print("\n  [!] В папке data/raw/ не найдено файлов.")
        print("  Вы можете ввести путь к файлу вручную.")
    else:
        print("\n  Файлы в data/raw/:")
        for idx, f in enumerate(files, 1):
            size_str = format_size(f.stat().st_size)
            print(f"   [{idx}] {f.name:<28} ({size_str}, {f.suffix.lstrip('.').upper()})")

    print(f"\n   [M] Ввести путь к файлу вручную")
    print(f"   [0] Назад в главное меню")
    print("\n" + "─" * 70)

    choice = input("  Выберите файл [номер или 0]: ").strip()
    if choice == "0":
        return

    selected_path: Optional[Path] = None
    if choice.lower() == "m" or not files:
        manual_path = input("  Введите полный или относительный путь к файлу: ").strip().strip('"')
        candidate = Path(manual_path)
        if not candidate.exists():
            input(f"\n  [ERROR] Файл не найден: {candidate}\n  Нажмите Enter...")
            return
        selected_path = candidate
    elif choice.isdigit() and 1 <= int(choice) <= len(files):
        selected_path = files[int(choice) - 1]
    else:
        input("\n  [ERROR] Неверный выбор. Нажмите Enter...")
        return

    # Шаг 2: Выбор целевого формата
    print_header(f"Главная > Конвертация файла > Шаг 2: Целевой формат для {selected_path.name}")
    print(f"\n  Выбран файл: {selected_path.name} ({selected_path.suffix.lstrip('.').upper()})")
    print("\n  Выберите формат для сохранения:")
    formats = sorted(list(FileConverter.SUPPORTED_OUTPUT_FORMATS))
    for idx, fmt in enumerate(formats, 1):
        print(f"   [{idx}] {fmt.upper()} (.{fmt})")
    print(f"\n   [0] Отмена (вернуться в главное меню)")
    print("\n" + "─" * 70)

    fmt_choice = input("  Выберите формат [1-4, 0]: ").strip()
    if fmt_choice == "0":
        return
    if not (fmt_choice.isdigit() and 1 <= int(fmt_choice) <= len(formats)):
        input("\n  [ERROR] Неверный выбор формата. Нажмите Enter...")
        return

    target_format = formats[int(fmt_choice) - 1]

    # Шаг 3: Выполнение пайплайна
    print_header("Главная > Конвертация файла > Выполнение конвейера")
    print(f"\n  Файл:   {selected_path.name}")
    print(f"  Формат: {target_format.upper()}\n")

    try:
        file_obj = File(selected_path)
        print("  [+] Чтение исходного файла...")
        df = FileConverter.read_to_dataframe(file_obj)
        print(f"      Прочитано строк: {len(df)}, колонок: {len(df.columns)}")

        schema_path = base_dir / cfg.get("schema_path", "schema.json")

        # Трансформации
        if schema_path.exists():
            print("  [+] Применение трансформаций по схеме (trim, case, to_date)...")
            df = FileConverter.apply_transformations(df, schema_path)

        # Промежуточный Parquet
        if cfg.get("save_intermediate_parquet", True):
            inter_dir = base_dir / cfg.get("intermediate_dir", "data/processed")
            inter_path = inter_dir / f"{selected_path.stem}.parquet"
            FileConverter.write_dataframe(df, inter_path, "parquet")
            print(f"  [+] Сохранен промежуточный Parquet: {inter_path.relative_to(base_dir)}")

            # Валидация промежуточного Parquet
            if schema_path.exists():
                print("  [+] Валидация данных по schema.json...")
                val_res = ParquetValidator.validate(inter_path, schema_path)
                if val_res.is_valid:
                    print("      Результат валидации: УСПЕШНО (0 ошибок)")
                else:
                    print(f"      [!] Найдено ошибок валидации: {len(val_res.errors)}")
                    for err in val_res.errors[:3]:
                        print(f"          - {err}")
                    if len(val_res.errors) > 3:
                        print(f"          ... и еще {len(val_res.errors) - 3} ошибок")

        # Маппинг колонок
        if schema_path.exists():
            print("  [+] Маппинг колонок (target_name)...")
            df = FileConverter.apply_column_mappings(df, schema_path)

        # Экспорт в итоговый формат
        out_dir = base_dir / cfg.get("output_dir", "data/output")
        out_path = out_dir / f"{selected_path.stem}.{target_format}"
        FileConverter.write_dataframe(df, out_path, target_format)
        print(f"  [+] Экспорт в {target_format.upper()}: {out_path.relative_to(base_dir)}")

        print("\n" + "=" * 70)
        print(f"  [OK] УСПЕШНО ЗАВЕРШЕНО!")
        print(f"  Результат: {out_path.resolve()}")
        print(f"  Размер:    {format_size(out_path.stat().st_size)}")
        print("=" * 70)

    except Exception as e:
        print("\n" + "=" * 70)
        print(f"  [ERROR] Ошибка при обработке: {e}")
        print("=" * 70)

    input("\n  Нажмите Enter для возврата в главное меню...")


def screen_batch_convert(base_dir: Path, cfg: dict) -> None:
    """Экран: пакетная конвертация всех файлов из data/raw/."""
    raw_dir = base_dir / cfg.get("raw_dir", "data/raw")
    files = get_raw_files(raw_dir)

    print_header("Главная > Пакетная конвертация")

    if not files:
        input("\n  [!] В папке data/raw/ нет файлов для обработки.\n  Нажмите Enter...")
        return

    print(f"\n  Найдено файлов для пакетной обработки: {len(files)}")
    for idx, f in enumerate(files, 1):
        print(f"   {idx}. {f.name} ({f.suffix.lstrip('.').upper()})")

    print("\n  Выберите целевой формат для ВСЕХ файлов:")
    formats = sorted(list(FileConverter.SUPPORTED_OUTPUT_FORMATS))
    for idx, fmt in enumerate(formats, 1):
        print(f"   [{idx}] {fmt.upper()} (.{fmt})")
    print(f"\n   [0] Отмена")
    print("\n" + "─" * 70)

    fmt_choice = input("  Выберите формат [1-4, 0]: ").strip()
    if fmt_choice == "0" or not (fmt_choice.isdigit() and 1 <= int(fmt_choice) <= len(formats)):
        return

    target_format = formats[int(fmt_choice) - 1]

    print_header(f"Главная > Пакетная конвертация > Выполнение в формат {target_format.upper()}")
    print(f"\n  Обработка {len(files)} файлов...\n")

    success_count = 0
    for idx, file_path in enumerate(files, 1):
        try:
            file_obj = File(file_path)
            out = FileConverter.convert(file_obj, target_format=target_format, config=cfg)
            print(f"  [{idx}/{len(files)}] [OK] {file_path.name:<26} -> {out.name}")
            success_count += 1
        except Exception as e:
            print(f"  [{idx}/{len(files)}] [FAIL] {file_path.name:<24} Ошибка: {e}")

    print("\n" + "=" * 70)
    print(f"  ИТОГ: Успешно обработано {success_count} из {len(files)} файлов.")
    print("=" * 70)
    input("\n  Нажмите Enter для возврата в главное меню...")


def screen_validate_only(base_dir: Path, cfg: dict) -> None:
    """Экран: прямая валидация файла по schema.json."""
    raw_dir = base_dir / cfg.get("raw_dir", "data/raw")
    processed_dir = base_dir / cfg.get("intermediate_dir", "data/processed")
    schema_path = base_dir / cfg.get("schema_path", "schema.json")

    print_header("Главная > Валидация файла по схеме")

    candidates = []
    if raw_dir.exists():
        candidates.extend([f for f in raw_dir.iterdir() if f.is_file()])
    if processed_dir.exists():
        candidates.extend([f for f in processed_dir.iterdir() if f.is_file() and f.suffix == ".parquet"])

    if not candidates:
        input("\n  [!] Нет доступных файлов для проверки.\n  Нажмите Enter...")
        return

    print(f"\n  Схема: {schema_path.name}\n")
    print("  Доступные файлы:")
    for idx, f in enumerate(candidates[:15], 1):
        parent_name = f.parent.name
        print(f"   [{idx}] {f.name:<28} (папка: {parent_name})")

    print(f"\n   [0] Назад")
    print("\n" + "─" * 70)

    choice = input("  Выберите файл [номер или 0]: ").strip()
    if choice == "0" or not (choice.isdigit() and 1 <= int(choice) <= len(candidates)):
        return

    selected_file = candidates[int(choice) - 1]

    print_header(f"Главная > Валидация > {selected_file.name}")
    print(f"\n  Проверка файла: {selected_file.name}")
    print(f"  Схема:          {schema_path.name}\n")

    try:
        if selected_file.suffix.lower() == ".parquet":
            result = ParquetValidator.validate(selected_file, schema_path)
        else:
            file_obj = File(selected_file)
            df = FileConverter.read_to_dataframe(file_obj)
            result = ParquetValidator.validate(df, schema_path)

        print("  " + "=" * 66)
        print("  " + result.summary().replace("\n", "\n  "))
        print("  " + "=" * 66)
    except Exception as e:
        print(f"\n  [ERROR] Ошибка при валидации: {e}")

    input("\n  Нажмите Enter для возврата в главное меню...")


def screen_settings(base_dir: Path, cfg_path: Path) -> None:
    """Экран: просмотр и изменение настроек config.json."""
    while True:
        cfg = FileConverter.load_config(cfg_path)
        inter_on = cfg.get("save_intermediate_parquet", True)
        inter_status = "ВКЛЮЧЕНО" if inter_on else "ВЫКЛЮЧЕНО"

        print_header("Главная > Настройки (config.json)")
        print("\n  ТЕКУЩИЕ ПАРАМЕТРЫ:")
        print(f"   [1] Сохранять промежуточный Parquet:   [{inter_status}]")
        print(f"       Папка промежуточных файлов:        {cfg.get('intermediate_dir')}")
        print(f"       Папка итоговых файлов:             {cfg.get('output_dir')}")
        print(f"       Файл схемы по умолчанию:           {cfg.get('schema_path')}")
        print(f"\n   [0] Назад в главное меню")
        print("\n" + "─" * 70)

        choice = input("  Выберите действие: ").strip()
        if choice == "0":
            break
        elif choice == "1":
            cfg["save_intermediate_parquet"] = not inter_on
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)


def main():
    base_dir = Path(__file__).resolve().parent
    cfg_path = base_dir / "config.json"

    # Поддержка запуска с аргументами командной строки: python main.py <file> -f <format>
    if len(sys.argv) > 1:
        import argparse

        parser = argparse.ArgumentParser(description="DataBridge CLI: конвертация и валидация данных.")
        parser.add_argument("file", help="Путь к исходному файлу")
        parser.add_argument("-f", "--format", required=True, choices=["csv", "json", "xml", "xlsx"], help="Целевой формат")
        parser.add_argument("-o", "--output-dir", default=None, help="Директория сохранения")
        args = parser.parse_args()

        file_obj = File(args.file)
        out = FileConverter.convert(file_obj, target_format=args.format, output_dir=args.output_dir)
        print(f"[OK] Сохранено: {out}")
        return

    # Интерактивный экранный режим (TUI)
    while True:
        cfg = FileConverter.load_config(cfg_path)
        inter_status = "ВКЛ" if cfg.get("save_intermediate_parquet", True) else "ВЫКЛ"

        print_header()
        print(f"  Промежуточный Parquet: [{inter_status}] | Выход: {cfg.get('output_dir')}")
        print("\n  ГЛАВНОЕ МЕНЮ:")
        print("   [1] Конвертировать файл (пошаговый режим)")
        print("   [2] Пакетная конвертация всех файлов из data/raw/")
        print("   [3] Валидация файла по schema.json")
        print("   [4] Настройки (config.json)")
        print("   [0] Выход из программы")
        print("\n" + "─" * 70)

        choice = input("  Выберите пункт меню [1-4, 0]: ").strip()

        if choice == "1":
            screen_convert_single(base_dir, cfg)
        elif choice == "2":
            screen_batch_convert(base_dir, cfg)
        elif choice == "3":
            screen_validate_only(base_dir, cfg)
        elif choice == "4":
            screen_settings(base_dir, cfg_path)
        elif choice == "0" or choice.lower() in ("q", "exit"):
            clear_screen()
            print("\n  Работа программы завершена.\n")
            break


if __name__ == "__main__":
    main()
