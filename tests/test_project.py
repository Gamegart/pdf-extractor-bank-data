import csv
import io
import unittest
from unittest.mock import patch

import app as web_app
from parsers import BBVA_TDC_PDFx, BBVA_TDD_PDFx, MP_TDC_PDFx
from parsers.date_utils import statement_period_from_filename, year_for_transaction_month


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self, layout=False):
        return self.text


class FakePdf:
    def __init__(self, text):
        self.pages = [FakePage(text)]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class ParserDateTests(unittest.TestCase):
    def test_statement_period_supports_english_and_spanish_names(self):
        self.assertEqual(statement_period_from_filename("Enero 2020 TDC.pdf", 2026), (2020, 1))
        self.assertEqual(statement_period_from_filename("January 2023.pdf", 2026), (2023, 1))
        self.assertEqual(statement_period_from_filename("Diciembre 2023.pdf", 2026), (2023, 12))

    def test_december_in_january_statement_uses_previous_year(self):
        self.assertEqual(year_for_transaction_month(12, 2020, 1), 2019)
        self.assertEqual(year_for_transaction_month(12, 2023, 1), 2022)
        self.assertEqual(year_for_transaction_month(1, 2023, 1), 2023)

    def test_mercado_pago_tdc_assigns_previous_year(self):
        text = "31/12 Compra ejemplo $100.00\n01/01 Compra ejemplo $20.00"
        with patch.object(MP_TDC_PDFx.pdfplumber, "open", return_value=FakePdf(text)):
            records = MP_TDC_PDFx.extraer_movimientos("MP TDC Enero 2020.pdf")

        self.assertEqual([record["date"] for record in records], [
            "2019-12-31 12:00:00",
            "2020-01-01 12:00:00",
        ])

    def test_bbva_debit_assigns_previous_year(self):
        text = "01/DIC 02/DIC SUPERMERCADO 45.67"
        with patch.object(BBVA_TDD_PDFx.pdfplumber, "open", return_value=FakePdf(text)):
            records = BBVA_TDD_PDFx.parse_pdf("Enero 2023 TDD.pdf")

        self.assertEqual(records[0]["date"], "2022-12-01 12:00:00")

    def test_bbva_credit_date_contains_explicit_year(self):
        self.assertEqual(BBVA_TDC_PDFx.parse_bbva_date("31-DIC-2020"), "2020-12-31 12:00:00")


class ExportTests(unittest.TestCase):
    def test_combined_csv_normalizes_and_sorts_dates(self):
        records = [
            web_app.normalize_record({"date": "2020-01-01 12:00:00", "payee": "January"}),
            web_app.normalize_record({"Date": "31/12/2019 12:00 PM", "Payee": "December", "Amount": -5.0}),
        ]

        output = web_app.records_to_csv(records).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(output)))

        self.assertEqual(list(rows[0]), web_app.CSV_FIELDS)
        self.assertEqual([row["payee"] for row in rows], ["December", "January"])

    def test_ui_is_available(self):
        response = web_app.app.test_client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BBVA (TDC)", response.data)
        self.assertIn(b"One combined CSV", response.data)


if __name__ == "__main__":
    unittest.main()