"""Модульные тесты для движка валидации данных DataBridge."""

import tempfile
import unittest
from pathlib import Path

from src.validators import (
    FieldSchema,
    LengthRule,
    PatternRule,
    RangeRule,
    RequiredRule,
    SchemaError,
    TypeRule,
    UniqueRule,
    ValidationEngine,
    ValidationResult,
    ValidationSchema,
)
from src.validators.rules import is_empty_value, parse_date


class TestRules(unittest.TestCase):
    """Тестирование базовых правил валидации."""

    def test_required_rule(self):
        rule = RequiredRule(required=True)
        # Валидные значения
        self.assertIsNone(rule.validate("test", {"f": "test"}, "f", 1))
        self.assertIsNone(rule.validate(0, {"f": 0}, "f", 1))
        self.assertIsNone(rule.validate(False, {"f": False}, "f", 1))

        # Невалидные значения
        err = rule.validate(None, {"f": None}, "f", 2)
        self.assertIsNotNone(err)
        self.assertIn('обязательно для заполнения', err.message)

        err_empty = rule.validate("   ", {"f": "   "}, "f", 3)
        self.assertIsNotNone(err_empty)

        err_missing = rule.validate(None, {}, "f", 4)
        self.assertIsNotNone(err_missing)

    def test_type_rule_integer(self):
        rule = TypeRule("integer")
        self.assertIsNone(rule.validate(42, {}, "age", 1))
        self.assertIsNone(rule.validate("42", {}, "age", 1))
        self.assertIsNone(rule.validate("-10", {}, "age", 1))
        self.assertIsNone(rule.validate(42.0, {}, "age", 1))

        # Ошибки
        self.assertIsNotNone(rule.validate(True, {}, "age", 1))  # bool не int
        self.assertIsNotNone(rule.validate("abc", {}, "age", 1))
        self.assertIsNotNone(rule.validate("42.5", {}, "age", 1))

    def test_type_rule_float(self):
        rule = TypeRule("float")
        self.assertIsNone(rule.validate(3.14, {}, "score", 1))
        self.assertIsNone(rule.validate("3.14", {}, "score", 1))
        self.assertIsNone(rule.validate("3,14", {}, "score", 1))  # поддержка запятой
        self.assertIsNone(rule.validate(100, {}, "score", 1))

        self.assertIsNotNone(rule.validate("not-a-number", {}, "score", 1))
        self.assertIsNotNone(rule.validate(True, {}, "score", 1))

    def test_type_rule_boolean(self):
        rule = TypeRule("boolean")
        self.assertIsNone(rule.validate(True, {}, "is_active", 1))
        self.assertIsNone(rule.validate(False, {}, "is_active", 1))
        self.assertIsNone(rule.validate("true", {}, "is_active", 1))
        self.assertIsNone(rule.validate("False", {}, "is_active", 1))
        self.assertIsNone(rule.validate("1", {}, "is_active", 1))
        self.assertIsNone(rule.validate("0", {}, "is_active", 1))
        self.assertIsNone(rule.validate("yes", {}, "is_active", 1))
        self.assertIsNone(rule.validate("нет", {}, "is_active", 1))

        self.assertIsNotNone(rule.validate("maybe", {}, "is_active", 1))
        self.assertIsNotNone(rule.validate(10, {}, "is_active", 1))

    def test_type_rule_date(self):
        rule = TypeRule("date", date_format="YYYY-MM-DD")
        self.assertIsNone(rule.validate("1999-01-15", {}, "birth_date", 1))
        self.assertIsNotNone(rule.validate("1999/01/15", {}, "birth_date", 1))  # несоответствие формату
        self.assertIsNotNone(rule.validate("2026-99-99", {}, "birth_date", 1))
        self.assertIsNotNone(rule.validate("invalid-date", {}, "birth_date", 1))

        # Формат DD.MM.YYYY
        rule_ru = TypeRule("date", date_format="DD.MM.YYYY")
        self.assertIsNone(rule_ru.validate("15.01.1999", {}, "birth_date", 1))
        self.assertIsNotNone(rule_ru.validate("1999-01-15", {}, "birth_date", 1))

    def test_range_rule_numbers(self):
        rule = RangeRule(min_value=16, max_value=100)
        self.assertIsNone(rule.validate(16, {}, "age", 1))  # граничное
        self.assertIsNone(rule.validate(100, {}, "age", 1)) # граничное
        self.assertIsNone(rule.validate(25, {}, "age", 1))
        self.assertIsNone(rule.validate("50", {}, "age", 1))

        # Ошибки
        err_min = rule.validate(15, {}, "age", 2)
        self.assertIsNotNone(err_min)
        self.assertIn("вне диапазона (15)", err_min.message)

        err_max = rule.validate(200, {}, "age", 3)
        self.assertIsNotNone(err_max)
        self.assertIn("вне диапазона (200)", err_max.message)

    def test_range_rule_dates(self):
        rule = RangeRule(
            min_value="2000-01-01",
            max_value="2020-12-31",
            field_type="date",
            date_format="YYYY-MM-DD",
        )
        self.assertIsNone(rule.validate("2010-05-15", {}, "date", 1))
        self.assertIsNotNone(rule.validate("1995-12-31", {}, "date", 2))
        self.assertIsNotNone(rule.validate("2025-01-01", {}, "date", 3))

    def test_pattern_rule(self):
        rule = PatternRule(pattern=r"^[^@]+@[^@]+\.[^@]+$")
        self.assertIsNone(rule.validate("ivan@mail.ru", {}, "email", 1))
        self.assertIsNone(rule.validate("test.user+tag@domain.co.uk", {}, "email", 1))

        err = rule.validate("maria.mail.ru", {}, "email", 5)
        self.assertIsNotNone(err)
        self.assertEqual(err.rule, "pattern")
        self.assertIn('поле "email" не соответствует формату', err.message)

    def test_length_rule(self):
        rule = LengthRule(min_length=3, max_length=10)
        self.assertIsNone(rule.validate("hello", {}, "name", 1))
        self.assertIsNone(rule.validate("123", {}, "name", 1))
        self.assertIsNone(rule.validate("1234567890", {}, "name", 1))

        err_min = rule.validate("hi", {}, "name", 2)
        self.assertIsNotNone(err_min)
        self.assertEqual(err_min.rule, "min_length")

        err_max = rule.validate("this is way too long string", {}, "name", 3)
        self.assertIsNotNone(err_max)
        self.assertEqual(err_max.rule, "max_length")

    def test_unique_rule(self):
        rule = UniqueRule(unique=True)
        self.assertIsNone(rule.validate(1, {}, "id", 1))
        self.assertIsNone(rule.validate(2, {}, "id", 2))
        self.assertIsNone(rule.validate(3, {}, "id", 3))

        # Повтор 1
        err = rule.validate(1, {}, "id", 6)
        self.assertIsNotNone(err)
        self.assertEqual(err.rule, "unique")
        self.assertIn("дубликат со строкой 1", err.message)

        # Сброс
        rule.reset()
        self.assertIsNone(rule.validate(1, {}, "id", 10))


class TestSchemaAndEngine(unittest.TestCase):
    """Тестирование схемы валидации и движка правил."""

    def setUp(self):
        self.schema_dict = {
            "fields": [
                {"name": "id", "type": "integer", "required": True, "unique": True},
                {"name": "name", "type": "string", "required": True, "min_length": 2},
                {"name": "email", "type": "string", "required": True, "pattern": r"^[^@]+@[^@]+\.[^@]+$"},
                {"name": "age", "type": "integer", "min": 16, "max": 100},
                {"name": "birth_date", "type": "date", "format": "YYYY-MM-DD"},
            ]
        }
        self.engine = ValidationEngine(self.schema_dict)

    def test_validation_schema_parsing(self):
        schema = ValidationSchema.from_dict(self.schema_dict)
        self.assertEqual(len(schema.fields_list), 5)
        self.assertTrue(schema.fields["id"].required)
        self.assertTrue(schema.fields["id"].unique)
        self.assertEqual(schema.fields["age"].min, 16)
        self.assertEqual(schema.fields["age"].max, 100)

    def test_invalid_schema_handling(self):
        with self.assertRaises(SchemaError):
            ValidationSchema.from_dict({"not_fields": []})

        with self.assertRaises(SchemaError):
            ValidationSchema.from_dict({"fields": [{"name": "id", "type": "unsupported_type"}]})

    def test_engine_valid_dataset(self):
        records = [
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 2, "name": "Мария", "email": "maria@mail.ru", "age": 30, "birth_date": "1994-05-20"},
        ]
        res = self.engine.validate_records(records)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.total_records, 2)
        self.assertEqual(res.valid_count, 2)
        self.assertEqual(res.errors_count, 0)
        self.assertEqual(len(res.errors), 0)

    def test_engine_invalid_sample_dataset(self):
        """Проверка эталонного набора данных из ТЗ (Неделя 2 / пример)."""
        records = [
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 2, "name": "Мария", "email": "maria.mail.ru", "age": 30, "birth_date": "1994-05-20"},
            {"id": 3, "name": "Пётр", "email": "petr@mail.ru", "age": 200, "birth_date": "2000-03-10"},
            {"id": 4, "name": "", "email": "empty@mail.ru", "age": 22, "birth_date": "2002-07-01"},
            {"id": 5, "name": "Анна", "email": "anna@mail.ru", "age": "abc", "birth_date": "2001-11-11"},
            {"id": 1, "name": "Дубликат", "email": "dup@mail.ru", "age": 35, "birth_date": "1989-01-01"},
        ]
        res = self.engine.validate_records(records, start_row_index=1)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.total_records, 6)
        self.assertEqual(res.valid_count, 1)  # только первая запись валидна
        self.assertEqual(len(res.invalid_records), 5)

        # Проверяем ошибки конкретных строк
        errors_by_row = res.errors_by_row
        # Строка 2: email не соответствует формату
        self.assertTrue(any(e.field == "email" and e.rule == "pattern" for e in errors_by_row[2]))
        # Строка 3: age вне диапазона (200)
        self.assertTrue(any(e.field == "age" and e.rule == "range" for e in errors_by_row[3]))
        # Строка 4: name обязательно
        self.assertTrue(any(e.field == "name" and e.rule == "required" for e in errors_by_row[4]))
        # Строка 5: age не integer
        self.assertTrue(any(e.field == "age" and e.rule == "type" for e in errors_by_row[5]))
        # Строка 6: id не уникален
        self.assertTrue(any(e.field == "id" and e.rule == "unique" for e in errors_by_row[6]))

    def test_summary_format(self):
        records = [
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 2, "name": "Мария", "email": "maria.mail.ru", "age": 30, "birth_date": "1994-05-20"},
            {"id": 3, "name": "Пётр", "email": "petr@mail.ru", "age": 200, "birth_date": "2000-03-10"},
        ]
        res = self.engine.validate_records(records, start_row_index=4)
        summary = res.summary()

        self.assertIn("Всего записей: 3", summary)
        self.assertIn("Успешно обработано: 1", summary)
        self.assertIn("Ошибок: 2", summary)
        self.assertIn('Строка 5: поле "email" не соответствует формату', summary)
        self.assertIn('Строка 6: поле "age" вне диапазона (200)', summary)

    def test_export_errors_dict_list(self):
        records = [{"id": 1, "name": "", "email": "bad", "age": "nan", "birth_date": None}]
        res = self.engine.validate_records(records, start_row_index=10)
        errors_list = res.to_errors_dict_list()
        self.assertGreater(len(errors_list), 0)
        item = errors_list[0]
        self.assertIn("row", item)
        self.assertIn("field", item)
        self.assertIn("value", item)
        self.assertIn("rule", item)
        self.assertIn("message", item)
        self.assertEqual(item["row"], 10)

    def test_yaml_and_json_schema_loading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "schema.json"
            yaml_path = Path(tmpdir) / "schema.yaml"

            import json
            json_path.write_text(json.dumps(self.schema_dict), encoding="utf-8")
            yaml_path.write_text(
                """fields:
  - name: id
    type: integer
    required: true
  - name: age
    type: integer
    min: 18
""",
                encoding="utf-8",
            )

            schema_j = ValidationSchema.from_file(json_path)
            self.assertEqual(len(schema_j.fields_list), 5)

            schema_y = ValidationSchema.from_file(yaml_path)
            self.assertEqual(len(schema_y.fields_list), 2)
            self.assertEqual(schema_y.fields["age"].min, 18)

    def test_edge_cases(self):
        # 1. Пустой датасет
        res = self.engine.validate_records([])
        self.assertTrue(res.is_valid)
        self.assertEqual(res.total_records, 0)
        self.assertEqual(res.valid_count, 0)

        # 2. Неизвестные поля в записи не ломают валидацию
        records = [
            {
                "id": 10,
                "name": "Тест",
                "email": "test@mail.ru",
                "age": 20,
                "birth_date": "2000-01-01",
                "unknown_field_1": "abc",
                "extra_data": 12345,
            }
        ]
        res = self.engine.validate_records(records)
        self.assertTrue(res.is_valid)

        # 3. Необязательное поле пропущено (age и birth_date не required)
        records_partial = [
            {"id": 20, "name": "Тест 2", "email": "test2@mail.ru"}
        ]
        res_partial = self.engine.validate_records(records_partial)
        self.assertTrue(res_partial.is_valid)


if __name__ == "__main__":
    unittest.main()
