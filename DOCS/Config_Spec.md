# Спецификация конфигурационного файла схемы: DataBridge

## 1. Общие сведения
Конфигурация схемы определяет правила валидации структуры и типов данных, а также правила трансформации и переименования полей.
Схема может быть описана как в формате **JSON**, так и в **YAML**.

Корневой элемент конфигурации — объект, содержащий массив `fields`.

---

## 2. Параметры описания полей (`fields`)

| Параметр | Тип | Обязательный | Описание |
|---|---|---|---|
| `name` | `string` | Да | Исходное имя колонки во входном файле. |
| `target_name` | `string` | Нет | Новое имя колонки в результирующем файле (маппинг). |
| `type` | `string` | Нет | Ожидаемый тип данных: `integer`, `float`, `string`, `boolean`, `date`. |
| `required` | `boolean` | Нет | Если `true`, поле не должно быть пустым (`null`, пустая строка, пробелы). |
| `unique` | `boolean` | Нет | Если `true`, значения в столбце должны быть уникальны. |
| `min` | `number` / `string` | Нет | Минимально допустимое числовое значение или минимальная дата. |
| `max` | `number` / `string` | Нет | Максимально допустимое числовое значение или максимальная дата. |
| `min_length` | `integer` | Нет | Минимальная длина строкового значения. |
| `max_length` | `integer` | Нет | Максимальная длина строкового значения. |
| `pattern` | `string` | Нет | Регулярное выражение (RegEx) для проверки формата строки. |
| `format` | `string` | Нет | Формат для типа `date` (по умолчанию `YYYY-MM-DD`). |
| `transform` | `string` / `list` / `dict` | Нет | Одно или несколько правил трансформации значения. |

---

## 3. Доступные трансформации (`transform`)

1. **`trim` / `strip`**: удаление начальных и конечных пробельных символов.
2. **`uppercase` / `upper`**: перевод текста в верхний регистр.
3. **`lowercase` / `lower`**: перевод текста в нижний регистр.
4. **`timestamp_to_date`**: перевод Unix-timestamp в строковую дату `YYYY-MM-DD`.
5. **Словарная замена (`replace`)**:
   ```yaml
   transform:
     replace:
       "M": "Мужской"
       "F": "Женский"
   ```

---

## 4. Примеры спецификаций

### 4.1. Пример в формате YAML (`schema.yaml`)
```yaml
fields:
  - name: id
    type: integer
    required: true
    unique: true

  - name: name
    target_name: full_name
    type: string
    required: true
    min_length: 2
    max_length: 50
    transform:
      - trim
      - uppercase

  - name: email
    type: string
    required: true
    pattern: "^[^@]+@[^@]+\\.[^@]+$"
    transform:
      - trim
      - lowercase

  - name: age
    type: integer
    min: 16
    max: 100

  - name: birth_date
    target_name: dob
    type: date
    format: "YYYY-MM-DD"
    transform: timestamp_to_date
```

### 4.2. Пример в формате JSON (`schema.json`)
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
      "min_length": 2,
      "max_length": 50,
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
      "name": "age",
      "type": "integer",
      "min": 16,
      "max": 100
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
