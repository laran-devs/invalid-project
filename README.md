# DataBridge CLI

Консольная утилита для конвертации табличных данных, валидации, трансформаций и анализа датасетов.

## Установка CLI

Для того чтобы команда `databridge` была доступна в терминале, установите проект в режиме разработки:

```bash
pip install -e .
```

Либо вызывайте через Python:
```bash
python main.py <команда> [параметры]
```

---

## Команды CLI

### 1. Конвертация данных (`convert`)

Конвертирует файл в один из поддерживаемых целевых форматов (`csv`, `json`, `xml`, `xlsx`) с автоматическим применением трансформаций и маппинга колонок из схемы. Некорректные записи отсекаются в `errors.csv`.

```bash
# Базовый запуск (схема schema.json используется по умолчанию):
databridge convert data/raw/valid_csv.csv --to json

# С явным указанием схемы и пути сохранения:
databridge convert data/raw/valid_csv.csv --to json --config schema.json --output data/output/result.json
```

---

### 2. Валидация данных (`validate`)

Проверяет входной файл на соответствие правилам из JSON-схеме. Возвращает код `0`, если данные валидны, и код `1`, если обнаружены ошибки.

```bash
# Валидация файла по схеме:
databridge validate data/raw/valid_csv.csv --config schema.json

# Валидация с генерацией HTML-отчета:
databridge validate data/raw/invalid_csv.csv --config schema.json --report report.html
```

---

### 3. Статистика и профилирование (`stats`)

Выводит сводку о структуре датасета: типы данных, число заполненных значений, процент пропусков, количество уникальных значений и числовые параметры (min, max, avg).

```bash
databridge stats data/raw/valid_csv.csv
```

---

## Конфигурация

### `schema.json`
Определяет контракт данных: типы, ограничения валидации, трансформации (`trim`, `uppercase`/`lowercase`, `timestamp_to_date`) и маппинг имён (`target_name`):

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

### `config.json`
Определяет глобальные настройки среды:

```json
{
  "save_intermediate_parquet": true,
  "intermediate_dir": "data/processed",
  "output_dir": "data/output",
  "schema_path": "schema.json"
}
```
