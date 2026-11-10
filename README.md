# DataBridge (Converter & Validator)

Утилита для конвертации табличных данных различных форматов в Apache Parquet и их валидации по JSON-схеме.

## Возможности

1. **Конвертация файлов в Parquet:**
   - Поддерживаемые форматы: `csv`, `json`, `xml`, `xlsx`, `xls`.
   - Автоматическое определение разделителей для CSV.
   - Сжатие Snappy по умолчанию.
2. **Валидация Parquet по JSON-схеме:**
   - Поддерживаемые типы данных: `integer`, `float`, `string`, `boolean`, `date`.
   - Проверка обязательности (`required`).
   - Проверка уникальности значений (`unique`).
   - Диапазоны числовых значений (`min`, `max`).
   - Длина строк (`min_length`, `max_length`).
   - Форматы дат (`format`, например `YYYY-MM-DD`).
   - Проверка по регулярным выражениям (`pattern`).

## Быстрый старт

### 1. Конвертация файла

```python
from src import File, FileConverter

file = File("data/raw/Example.xlsx")
parquet_path = FileConverter.convert_to_parquet(file, output_dir="data/processed")
print(f"Сохранен Parquet: {parquet_path}")
```

### 2. Валидация Parquet

```python
from src import ParquetValidator

result = ParquetValidator.validate("data/processed/Example.parquet", "schema.json")
if result:
    print("Данные валидны!")
else:
    print(result.summary())
```
