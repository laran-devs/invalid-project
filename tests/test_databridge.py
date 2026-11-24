import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd

from src.models import File
from src.readers import ReaderFactory, CSVReader, JSONReader, XMLReader, ExcelReader
from src.validators import (
    ValidationEngine,
    ValidationResult,
    load_schema,
    check_required,
    check_unique,
    check_type,
    check_range,
    check_length,
    check_pattern,
)
from src.converters import (
    ConversionPipeline,
    FileConverter,
    DataWriter,
    apply_transformations,
    apply_column_mappings,
)
from src.reporters import HTMLReporter, StatsReporter, format_bytes
from src.stats import get_dataframe_stats
from src.cli.parser import build_parser


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
        res = ValidationEngine.validate(df, self.schema)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.valid_count, 2)
        self.assertEqual(len(res.invalid_indices), 0)

    def test_validator_required_rule(self):
        df = pd.DataFrame([
            {"id": 1, "name": "   ", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"}
        ])
        res = ValidationEngine.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(0, res.invalid_indices)

    def test_validator_unique_rule(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 1, "name": "Петр", "email": "petr@mail.ru", "age": 30, "birth_date": "1990-01-01"},
        ])
        res = ValidationEngine.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(1, res.invalid_indices)

    def test_validator_integer_type_rule(self):
        df = pd.DataFrame([
            {"id": "not_an_int", "name": "Иван", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"}
        ])
        res = ValidationEngine.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(0, res.invalid_indices)

    def test_validator_pattern_rule(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "bad_email_format", "age": 25, "birth_date": "1999-01-15"}
        ])
        res = ValidationEngine.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertIn(0, res.invalid_indices)

    def test_validator_min_max_range(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "age": 120, "birth_date": "1999-01-15"},
            {"id": 2, "name": "Мария", "email": "maria@mail.ru", "age": 10, "birth_date": "1999-01-15"},
        ])
        res = ValidationEngine.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.invalid_indices), 2)

    def test_validator_string_length(self):
        df = pd.DataFrame([
            {"id": 1, "name": "A", "email": "ivan@mail.ru", "age": 25, "birth_date": "1999-01-15"},
            {"id": 2, "name": "x" * 60, "email": "maria@mail.ru", "age": 30, "birth_date": "1999-01-15"},
        ])
        res = ValidationEngine.validate(df, self.schema)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.invalid_indices), 2)

    def test_transformation_trim_and_case(self):
        df = pd.DataFrame([
            {"name": "   иван   ", "email": "  IVAN@MAIL.RU  "}
        ])
        res_df = apply_transformations(df, self.schema)
        self.assertEqual(res_df.loc[0, "name"], "ИВАН")
        self.assertEqual(res_df.loc[0, "email"], "ivan@mail.ru")

    def test_transformation_timestamp_to_date(self):
        df = pd.DataFrame([
            {"birth_date": 916358400}
        ])
        res_df = apply_transformations(df, self.schema)
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
        res_df = apply_transformations(df, schema_dict)
        self.assertEqual(res_df.loc[0, "status"], "Active")
        self.assertEqual(res_df.loc[1, "status"], "Inactive")

    def test_column_mapping(self):
        df = pd.DataFrame([
            {"id": 1, "name": "Иван", "email": "ivan@mail.ru", "birth_date": "1999-01-15"}
        ])
        mapped_df = apply_column_mappings(df, self.schema)
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

            saved_out, saved_err, val_res = ConversionPipeline.convert_pipeline(
                file=in_file,
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
            HTMLReporter.generate(val_res, report_path)
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

    def test_reader_factory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            csv_f = tmp_path / "test.csv"
            csv_f.write_text("a,b\n1,2", encoding="utf-8")
            df = ReaderFactory.read(csv_f)
            self.assertEqual(len(df), 1)
            self.assertEqual(list(df.columns), ["a", "b"])

    def test_schema_loader_yaml(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            yaml_f = tmp_path / "schema.yaml"
            yaml_f.write_text("fields:\n  - name: test_col\n    type: integer\n", encoding="utf-8")
            loaded = load_schema(yaml_f)
            self.assertIn("fields", loaded)
            self.assertEqual(loaded["fields"][0]["name"], "test_col")

    def test_validator_boolean_type(self):
        schema = {"fields": [{"name": "is_active", "type": "boolean"}]}
        df = pd.DataFrame([{"is_active": True}, {"is_active": "false"}, {"is_active": "invalid_val"}])
        res = ValidationEngine.validate(df, schema)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.valid_count, 2)
        self.assertIn(2, res.invalid_indices)

    def test_validator_float_type(self):
        schema = {"fields": [{"name": "score", "type": "float"}]}
        df = pd.DataFrame([{"score": "3.14"}, {"score": "2,5"}, {"score": "abc"}])
        res = ValidationEngine.validate(df, schema)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.valid_count, 2)
        self.assertIn(2, res.invalid_indices)

    def test_validator_date_range(self):
        schema = {
            "fields": [
                {
                    "name": "bdate",
                    "type": "date",
                    "format": "YYYY-MM-DD",
                    "min": "2000-01-01",
                    "max": "2020-12-31",
                }
            ]
        }
        df = pd.DataFrame([
            {"bdate": "2010-05-15"},
            {"bdate": "1990-01-01"},
            {"bdate": "2025-01-01"},
        ])
        res = ValidationEngine.validate(df, schema)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.valid_count, 1)
        self.assertEqual(len(res.invalid_indices), 2)

    def test_cli_parser_commands(self):
        parser = build_parser()
        args = parser.parse_args(["convert", "input.csv", "--to", "json", "--config", "schema.yaml", "--output", "out.json"])
        self.assertEqual(args.command, "convert")
        self.assertEqual(args.file, "input.csv")
        self.assertEqual(args.to, "json")
        self.assertEqual(args.config, "schema.yaml")
        self.assertEqual(args.output, "out.json")

        args_val = parser.parse_args(["validate", "input.json", "--config", "schema.yaml", "--report", "rep.html"])
        self.assertEqual(args_val.command, "validate")
        self.assertEqual(args_val.file, "input.json")
        self.assertEqual(args_val.report, "rep.html")

        args_st = parser.parse_args(["stats", "input.csv"])
        self.assertEqual(args_st.command, "stats")
        self.assertEqual(args_st.file, "input.csv")


if __name__ == "__main__":
    unittest.main()
