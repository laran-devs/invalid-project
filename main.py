from pathlib import Path
from src import File, FileConverter


def main():
    base_dir = Path(__file__).resolve().parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"

    # Конвертация конкретного Excel-файла
    sample_file_path = raw_dir / "Example.xlsx"
    if sample_file_path.exists():
        file = File(sample_file_path)
        print(f"Обработка: {file}")

        # Для Excel разделитель не нужен:
        result_path = FileConverter.convert_to_parquet(
            file,
            output_dir=processed_dir,
            # sheet_name=0  # при необходимости можно указать имя или индекс листа
        )
        print(f"Сохранен Parquet: {result_path}")


if __name__ == "__main__":
    main()