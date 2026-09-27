import os
import re
import unicodedata


MONTHS = {
    "enero": 1, "ene": 1, "january": 1, "jan": 1,
    "febrero": 2, "feb": 2, "february": 2,
    "marzo": 3, "mar": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4, "apr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6, "june": 6,
    "julio": 7, "jul": 7, "july": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "septiembre": 9, "setiembre": 9, "sep": 9, "sept": 9, "september": 9,
    "octubre": 10, "oct": 10, "october": 10,
    "noviembre": 11, "nov": 11, "november": 11,
    "diciembre": 12, "dic": 12, "december": 12, "dec": 12,
}
MONTH_PATTERN = re.compile(
    r"(?<![a-z])(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")(?![a-z])"
)


def statement_period_from_filename(pdf_path, default_year):
    filename = os.path.basename(pdf_path)
    normalized = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii").lower()
    year_match = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", normalized)
    month_match = MONTH_PATTERN.search(normalized)
    year = int(year_match.group()) if year_match else default_year
    month = MONTHS.get(month_match.group()) if month_match else None
    return year, month


def year_for_transaction_month(transaction_month, statement_year, statement_month):
    if statement_month is not None and transaction_month > statement_month:
        return statement_year - 1
    return statement_year