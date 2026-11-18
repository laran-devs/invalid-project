# DataBridge (Converter, Transformer & Validator)

Утилита для конвертации табличных данных, валидации, трансформации и маппинга полей.

## Возможности

1. **Конвертация форматов данных:**
   * **Входные форматы:** `csv`, `json`, `xml`, `xlsx`, `xls`.
   * **Выходные форматы:** `csv`, `json`, `xml`, `xlsx` (сохраняются в `data/output/`).
   * **Промежуточный Parquet:** сохраняется в `data/processed/` при включённой настройке `"save_intermediate_parquet": true` в [`config.json`](config.json).
2. **Трансформации данных (в [`schema.json`](schema.json)):**
   * Обрезка пробелов: `"trim"` / `"strip"`.
   * Приведение к регистру: `"uppercase"` / `"upper"` и `"lowercase"` / `"lower"`.
   * Вычисление даты из timestamp: `"timestamp_to_date"`.
3. **Маппинг колонок (в [`schema.json`](schema.json)):**
   * Переименование полей в целевом файле через свойство `"target_name"`.
4. **Валидация по JSON-схеме:**
   * Типы данных: `integer`, `float`, `string`, `boolean`, `date`.
   * Обязательность (`required`), уникальность (`unique`).
   * Диапазоны (`min`, `max`), длина строк (`min_length`, `max_length`), регулярные выражения (`pattern`).

## Конфигурация

### 1. `config.json` (настройки среды)
```json
{
  "save_intermediate_parquet": true,
  "intermediate_dir": "data/processed",
  "output_dir": "data/output",
  "schema_path": "schema.json"
}
```

### 2. `schema.json` (контракт данных: валидация, трансформации, маппинг)
```json
{
  "fields": [
    {
      "name": "id",
      "type": "integer",
      "required": true,
      "unique": true
    },
    {
      "name": "name",
      "target_name": "full_name",
      "type": "string",
      "required": true,
      "transform": ["trim", "uppercase"]
    },
    {
      "name": "email",
      "type": "string",
      "required": true,
      "pattern": "^[^@]+@[^@]+\\.[^@]+$",
      "transform": ["trim", "lowercase"]
    },
    {
      "name": "birth_date",
      "target_name": "dob",
      "type": "date",
      "format": "YYYY-MM-DD",
      "transform": "timestamp_to_date"
    }
  ]
}
```

## Быстрый старт

```python
from src import File, FileConverter, ParquetValidator

# 1. Конвертация с трансформациями и маппингом:
file = File("data/raw/valid_csv.csv")
output_path = FileConverter.convert(file, target_format="json")
print(f"Итоговый файл: {output_path}")

# 2. Валидация промежуточного Parquet:
result = ParquetValidator.validate("data/processed/valid_csv.parquet", "schema.json")
if result:
    print("Данные валидны!")
else:
    print(result.summary())
```
