import os
import re
import pdfplumber
import pandas as pd

# --- CONFIGURATION ---
DEFAULT_ACCOUNT_NAME = "Credit Card"
DEFAULT_TIME = "12:00 PM"

def categorize_transaction(description):
    desc = description.upper()
    categories = {
        'Food & Drinks': ['CAFFENIO', 'CINEPOLIS', 'UBER EATS', 'UBER', 'RESTAURANT', 'CAFE', 'OXXO', 'KFC'],
        'Shopping': ['MERCADO LIBRE', 'PULL&BEAR', 'PULL AND BEAR', 'H&M', 'VANS', 'ADIDAS', 'AMAZON', 'WALMART', 'COSTCO'],
        'Software, apps, games': ['STEAM', 'APPLE MUSIC', 'GOOGLE', 'NINTENDO', 'PLAYSTATION', 'XSOLLA', 'ITUNES', 'PAYPAL *COMPONENTES'],
        'Financial expenses': ['COMISION', 'INTERES', 'ANUALIDAD', 'IVA'],
    }

    for category, keywords in categories.items():
        if any(keyword in desc for keyword in keywords):
            return category
    return 'Others'

def parse_bbva_date(date_str):
    """Convert a BBVA date to the shared YYYY-MM-DD HH:MM:SS format."""
    date_str = date_str.upper().strip()
    months = {'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06',
              'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'}

    parts = re.split(r'[/ \-]', date_str)
    if len(parts) >= 3:
        day = parts[0].zfill(2)
        month = parts[1]
        year = parts[2]

        if month in months:
            month = months[month]
        elif month.isdigit():
            month = month.zfill(2)

        return f"{year}-{month}-{day} 12:00:00"
    return ""

def clean_amount(amount_str):
    """Parses amount and assigns sign. + is a charge (negative), - is a payment (positive)"""
    if not amount_str:
        return 0.0
    clean_str = re.sub(r'[^\d\.\-\+]', '', amount_str)
    try:
        val = abs(float(clean_str))
        if '-' in amount_str:
            return val # Income/Payment
        else:
            return -val # Expense/Charge
    except ValueError:
        return 0.0

def parse_pdf(filepath):
    transactions = []
    parsing_state = False

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split('\n'):
                line_upper = line.upper().strip()

                if "ABONOS REGULARES" in line_upper or "NO A MESES" in line_upper:
                    parsing_state = True
                    continue
                elif "TOTAL CARGOS" in line_upper or "TOTAL ABONOS" in line_upper:
                    parsing_state = False
                    continue

                if not parsing_state:
                    continue

                date_match = re.match(r'^\s*(\d{2}[/ \-][A-Za-z]{3}[/ \-]\d{4})', line)
                if not date_match:
                    continue

                parsed_date = parse_bbva_date(date_match.group(1))
                remaining_line = line[len(date_match.group(0)):].strip()
                remaining_line = re.sub(r'^\s*\d{2}[/ \-][A-Za-z]{3}[/ \-]\d{4}\s*', '', remaining_line)

                amount_match = re.search(r'([+-]\s*\$?\s*[\d,]+\.\d{2})', remaining_line)
                if amount_match:
                    amount_str = amount_match.group(1)
                else:
                    amounts = re.findall(r'[\d,]+\.\d{2}', remaining_line)
                    amount_str = amounts[-1] if amounts else "0.00"

                amount = clean_amount(amount_str)
                desc = remaining_line
                if amount_match:
                    desc = desc.replace(amount_match.group(1), '')

                desc = re.sub(r'[\$%]', '', desc)
                desc = re.sub(r'\s+', ' ', desc).strip()

                if amount < 0.0:
                    transactions.append({
                        "Date": parsed_date,
                        "Amount": amount,
                        "Payee": desc,
                        "Category": categorize_transaction(desc),
                        "Account": DEFAULT_ACCOUNT_NAME,
                        "Note": desc
                    })

    return transactions


def process_pdfs(directory):
    pdf_files = [f for f in os.listdir(directory) if f.lower().endswith('.pdf')]

    if not pdf_files:
        print("No PDF files found in the directory.")
        return

    for filename in pdf_files:
        filepath = os.path.join(directory, filename)
        print(f"Processing: {filename}")
        transactions = parse_pdf(filepath)

        if transactions:
            df = pd.DataFrame(transactions)
            csv_filename = filename.replace('.pdf', '_BudgetBakers.csv')
            df.to_csv(csv_filename, index=False, encoding='utf-8')
            print(f"Saved {len(transactions)} transactions to {csv_filename}")
        else:
            print(f"No valid transactions found in {filename}.")

if __name__ == "__main__":
    current_directory = os.getcwd()
    process_pdfs(current_directory)
