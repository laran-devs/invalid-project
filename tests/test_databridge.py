import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd

from src.models import File
from src.converter import FileConverter
from src.validator import ParquetValidator, ValidationResult
from src.stats import get_dataframe_stats


class TestDataBridge(unittest.TestCase):

    def setUp(self):
        self.schema = {
            "fields": [
                {
                    "name": "id",
                    "type": "integer",
                    "required": True,
                    "unique": True,
                },
                {
                    "name": "name",
                    "target_name": "full_name",
                    "type": "string",
                    "required": True,
                    "min_length": 2,
                    "max_length": 50,
                    "transform": ["trim", "uppercase"],
                },
                {
                    "name": "email",
                    "type": "string",
                    "required": True,
                    "pattern": r"^[^@]+@[^@]+\.[^@]+$",
                    "transform": ["trim", "lowercase"],
                },
                {
                    "name": "age",
                    "type": "integer",
                    "min": 16,
                    "max": 100,
                },
                {
                    "name": "birth_date",
                    "target_name": "dob",
                    "type": "date",
                    "format": "YYYY-MM-DD",
                    "transform": "timestamp_to_date",
                },
            ]
        }

    def test_file_model_valid(self):
        with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
            f = File(tmp.name)
            self.assertEqual(f.format, "csv")

    def test_file_model_unsupported_format(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            with self.assertRaises(ValueError):
                File(tmp.name)

    def test_validator_valid_dataset(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 2, "name": "Мария", "email": "maria@mail.ru", "age": 30, "birth_date": "1994-05-20"},
        ])
        res = ParquetValidator.validate(df, self.schema)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.valid_count, 2)
        self.assertEqual(len(res.invalid_indices), 0)

    def test_validator_required_rule(self):
        df = pd.DataFrame([
            {"id": 1, "name": "   ", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"}
        ])
        res = ParquetValidator.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(0, res.invalid_indices)

    def test_validator_unique_rule(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 1, "name": "Петр", "email": "petr@mail.ru", "age": 30, "birth_date": "1990-01-01"},
        ])
        res = ParquetValidator.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(1, res.invalid_indices)

    def test_validator_integer_type_rule(self):
        df = pd.DataFrame([
            {"id": "not_an_int", "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"}
        ])
        res = ParquetValidator.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(0, res.invalid_indices)

    def test_validator_pattern_rule(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "bad_email_format", "age": 25, "birth_date": "1999-01-15"}
        ])
        res = ParquetValidator.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(0, res.invalid_indices)

    def test_validator_min_max_range(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 120, "birth_date": "1999-01-15"},
            {"id": 2, "name": "Мария", "email": "maria@mail.ru", "age": 10, "birth_date": "1999-01-15"},
        ])
        res = ParquetValidator.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.invalid_indices), 2)

    def test_validator_string_length(self):
        df = pd.DataFrame([
            {"id": 1, "name": "A", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 2, "name": "x" * 60, "email": "maria@mail.ru", "age": 30, "birth_date": "1999-01-15"},
        ])
        res = ParquetValidator.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.invalid_indices), 2)

    def test_transformation_trim_and_case(self):
        df = pd.DataFrame([
            {"name": "   иван   ", "email": "  IVAN@MAIL.RU  "}
        ])
        res_df = FileConverter.apply_transformations(df, self.schema)
        self.assertEqual(res_df.loc[0, "name"], "ИВАН")
        self.assertEqual(res_df.loc[0, "email"], "ivan@mail.ru")

    def test_transformation_timestamp_to_date(self):
        df = pd.DataFrame([
            {"birth_date": 916358400}
        ])
        res_df = FileConverter.apply_transformations(df, self.schema)
        self.assertEqual(res_df.loc[0, "birth_date"], "1999-01-15")

    def test_transformation_dictionary_replace(self):
        schema_dict = {
            "fields": [
                {
                    "name": "status",
                    "transform": {"replace": {"A": "Active", "I": "Inactive"}},
                }
            ]
        }
        df = pd.DataFrame([{"status": "A"}, {"status": "I"}])
        res_df = FileConverter.apply_transformations(df, schema_dict)
        self.assertEqual(res_df.loc[0, "status"], "Active")
        self.assertEqual(res_df.loc[1, "status"], "Inactive")

    def test_column_mapping(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "birth_date": "1999-01-15"}
        ])
        mapped_df = FileConverter.apply_column_mappings(df, self.schema)
        self.assertIn("full_name", mapped_df.columns)
        self.assertIn("dob", mapped_df.columns)
        self.assertNotIn("name", mapped_df.columns)
        self.assertNotIn("birth_date", mapped_df.columns)

    def test_convert_pipeline_splitting_valid_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "input.csv"
            out_file = tmp_path / "output.json"
            schema_file = tmp_path / "schema.json"

            schema_file.write_text(json.dumps(self.schema), encoding="utf-8")
            df = pd.DataFrame([
                {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
                {"id": 2, "name": "", "email": "bad_email", "age": 200, "birth_date": "1999-01-15"},
            ])
            df.to_csv(in_file, index=False)

            saved_out, saved_err, val_res = FileConverter.convert_pipeline(
                file=File(in_file),
                target_format="json",
                schema_path=schema_file,
                output_path=out_file,
            )

            self.assertTrue(saved_out.exists())
            self.assertTrue(saved_err.exists())
            self.assertEqual(val_res.total_records, 2)
            self.assertEqual(val_res.valid_count, 1)

            valid_data = json.loads(saved_out.read_text(encoding="utf-8"))
            self.assertEqual(len(valid_data), 1)
            self.assertEqual(valid_data[0]["full_name"], "ИВАН")

            err_df = pd.read_csv(saved_err)
            self.assertEqual(len(err_df), 1)
            self.assertEqual(err_df.loc[0, "id"], 2)

    def test_html_report_generation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "report.html"
            val_res = ValidationResult(
                total_records=2,
                valid_count=1,
                invalid_indices={1},
                errors=['Строка 2: поле "age" вне диапазона'],
                errors_table=[{
                    "row": 2,
                    "field": "age",
                    "value": 200,
                    "rule": "range",
                    "message": 'поле "age" вне диапазона',
                }],
            )
            val_res.generate_html_report(report_path)
            self.assertTrue(report_path.exists())
            html_content = report_path.read_text(encoding="utf-8")
            self.assertIn("Отчёт валидации данных", html_content)
            self.assertIn("200", html_content)

    def test_dataframe_stats(self):
        df = pd.DataFrame([
            {"id": 1, "val": 10.5},
            {"id": 2, "val": 20.5},
        ])
        stats_text = get_dataframe_stats(df, file_size=1024)
        self.assertIn("DATA STATISTICS", stats_text)
        self.assertIn("Строк (Rows):        2", stats_text)
        self.assertIn("Колонок (Columns):   2", stats_text)
        self.assertIn("1.0 KB", stats_text)


if __name__ == "__main__":
    unittest.main()
