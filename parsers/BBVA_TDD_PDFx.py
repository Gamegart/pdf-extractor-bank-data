import pdfplumber
import csv
import re
import glob
import os
if __package__:
    from .date_utils import statement_period_from_filename, year_for_transaction_month
else:
    from date_utils import statement_period_from_filename, year_for_transaction_month

MESES_ESPANOL = {
    'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
}
def categorizar_y_limpiar(description, is_income):
    """Analiza la descripción para extraer un Payee limpio y asignar la categoría más precisa."""
    desc_upper = description.upper()

    # 1. Ingresos (Income)
    if is_income or any(k in desc_upper for k in ["NOMINA", "SPEI RECIBIDO", "TEF RECIBIDO", "DEPOSITO", "FONDO DE AHORRO"]):
        return "Income", description

    # 2. Alimentación, Comida y Bebidas (Food & Drinks / Bar, cafe / Restaurant, fast-food)
    if any(k in desc_upper for k in ["OXXO", "7-ELEVEN", "OXXO"]):
        return "Food & Drinks", description
    if any(k in desc_upper for k in ["STARBUCKS", "CAFFENIO", "CAFE", "BAR"]):
        return "Bar, cafe", description
    if any(k in desc_upper for k in ["RESTAURANT", "ALITAS", "PIZZA", "BURGER", "CARLS JR", "DOMINOS", "LITTLE CAESAR", "KFC", "MCDONALDS", "WINGS STOP"]):
        return "Restaurant, fast-food", description

    # 3. Supermercados y Despensa (Groceries)
    if any(k in desc_upper for k in ["SORIANA", "WALMART", "HEB", "COSTCO", "SAM'S", "BIRDMAN"]):
        return "Groceries", description

    # 4. Salud y Belleza / Farmacia (Health and beauty / Drug-store, chemist)
    if any(k in desc_upper for k in ["F AHORRO", "FARMACIA", "BENAVIDES", "CETAPHIL", "NEUTROGENA"]):
        return "Health and beauty", description

    # 5. Vehículo (Fuel / Vehicle maintenance / Monthly Car Payment)
    if any(k in desc_upper for k in ["GASOL", "PEMEX", "BP", "SHELL", "G500", "VALERO"]):
        return "Fuel", description
    if any(k in desc_upper for k in ["TALLER", "REFACCIONES", "SERVICIO AUTO"]):
        return "Vehicle maintenance", description
    if any(k in desc_upper for k in ["PRESTAMO", "ABONO", "AUTO"]):
        return "Monthly Car Payment", description

    # 6. Comunicación y Tecnología (Internet / Telephony, mobile phone / Communication, PC)
    if any(k in desc_upper for k in ["TELMEX", "IZZI", "TOTALPLAY", "INTERNET"]):
        return "Internet", description
    if any(k in desc_upper for k in ["TELCEL", "AT&T", "MOVISTAR", "RECARGA"]):
        return "Telephony, mobile phone", description

    # 7. Entretenimiento, Software y Juegos (Software, apps, games / Cine, tv, streaming / Spotify)
    if any(k in desc_upper for k in ["STEAM", "PLAYSTATION", "XBOX", "NINTENDO", "FIREWATCH", "BEAT SABER"]):
        return "Software, apps, games", description
    if any(k in desc_upper for k in ["SPOTIFY"]):
        return "Spotify", description
    if any(k in desc_upper for k in ["NETFLIX", "DISNEY", "HBO", "MUBI", "PRIME VIDEO"]):
        return "Cine, tv, streaming", description
    if any(k in desc_upper for k in ["CINEPOLIS", "CINEMEX", "TICKET"]):
        return "Cinema", description

    # 8. Compras y Ropa (Shopping / Clothes & Footwear / Electronics, accessories)
    if any(k in desc_upper for k in ["PULL&BEAR", "H&M", "ZARA", "VANS", "CALCETINES", "BOXERS", "CAMISA"]):
        return "Clothes & Footwear", description
    if any(k in desc_upper for k in ["OCULUS", "MONITOR", "TECLADO", "MOUSE"]):
        return "Electronics, accessories", description
    if any(k in desc_upper for k in ["AMAZON", "MERCADO PAGO", "MERPAGO", "MERCADO LIBRE"]):
        return "Shopping", description

    # 9. Transporte (Taxi)
    if any(k in desc_upper for k in ["UBER", "DIDIMOVIL", "TAXI"]):
        return "Taxi", description

    # 10. Gastos Financieros
    if any(k in desc_upper for k in ["COMISION", "INTERESES", "IVA", "ISR"]):
        return "Financial expenses", description

    return "Others", description

def ordenar_por_fecha_registros(records):
    return sorted(records, key=lambda row: row.get('date', ''))


def parse_pdf(pdf_path):
    row_pattern = re.compile(r'^\s*(\d{2}/[A-Z]{3})\s+(\d{2}/[A-Z]{3})\s+(.*?)\s+([\d,]+\.\d{2})')

    records = []
    current_record = None
    cargo_col_center = 80
    abono_col_center = 100

    ignore_keywords = [
        "BBVA", "Estado de Cuenta", "Libretón", "PAGINA",
        "No. de Cuenta", "No. de Cliente", "Le informamos",
        "en nuestra página", "La GAT", "Detalle de Movimientos",
        "FECHA OPER", "SALDO", "---", "Av. Paseo"
    ]

    stop_parsing = False

    file_year, file_month = statement_period_from_filename(pdf_path, default_year=2025)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if stop_parsing:
                break

            text = page.extract_text(layout=True)
            if not text:
                continue

            for line in text.split('\n'):
                if "Total de Movimientos" in line or "TOTAL IMPORTE" in line:
                    stop_parsing = True
                    break

                if "CARGOS" in line and "ABONOS" in line and "DESCRIPCION" in line:
                    cargo_col_center = line.find("CARGOS") + (len("CARGOS") / 2)
                    abono_col_center = line.find("ABONOS") + (len("ABONOS") / 2)
                    continue

                if any(kw in line for kw in ignore_keywords) or not line.strip():
                    continue

                match = row_pattern.search(line)
                if match:
                    if current_record:
                        desc_limpia = re.sub(r'\s+', ' ', current_record['note']).strip()
                        current_record['note'] = desc_limpia
                        current_record['payee'] = desc_limpia
                        cat, _ = categorizar_y_limpiar(desc_limpia, not current_record['amount'].startswith('-'))
                        current_record['category'] = cat

                    fecha_oper = match.group(1)
                    dia_str, mes_str = fecha_oper.split('/')
                    txn_day = int(dia_str)
                    txn_month = MESES_ESPANOL.get(mes_str.upper(), file_month)

                    txn_year = year_for_transaction_month(txn_month, file_year, file_month)

                    date_formatted = f"{txn_year}-{txn_month:02d}-{txn_day:02d} 12:00:00"

                    desc_raw = match.group(3).strip()
                    monto_str = match.group(4)
                    monto_limpio = monto_str.replace(',', '')
                    monto_center = match.start(4) + (len(monto_str) / 2)

                    if abs(monto_center - cargo_col_center) < abs(monto_center - abono_col_center):
                        amount = f"-{monto_limpio}"
                    else:
                        amount = f"{monto_limpio}"

                    current_record = {
                        'date': date_formatted,
                        'amount': amount,
                        'payee': '',
                        'category': '',
                        'account': 'BBVA/Bañorte',
                        'note': desc_raw
                    }
                    records.append(current_record)

                elif current_record:
                    clean_line = re.sub(r'RFC:.*', '', line)
                    clean_line = re.sub(r'Referencia.*', '', clean_line, flags=re.IGNORECASE).strip()

                    if clean_line and not re.match(r'^[\d,]+\.\d{2}', clean_line):
                        current_record['note'] += f" {clean_line}"

    if current_record:
        desc_limpia = re.sub(r'\s+', ' ', current_record['note']).strip()
        current_record['note'] = desc_limpia
        current_record['payee'] = desc_limpia
        cat, _ = categorizar_y_limpiar(desc_limpia, not current_record['amount'].startswith('-'))
        current_record['category'] = cat

    return ordenar_por_fecha_registros(records)


def extraer_estado_cuenta_wallet(pdf_path, csv_path):
    ordered_records = parse_pdf(pdf_path)
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'amount', 'payee', 'category', 'account', 'note'])
        writer.writeheader()
        writer.writerows(ordered_records)

    return len(ordered_records)

def main():
    archivos_pdf = glob.glob("*.pdf")

    if not archivos_pdf:
        print("No se encontraron archivos PDF en esta carpeta.")
        return

    merge_choice = input("¿Quieres guardar todo en un solo CSV? (Y/N): ").strip().lower()

    if merge_choice == 'y':
        combined_rows = []
        for archivo in archivos_pdf:
            temp_csv = f".__tmp_{os.path.basename(archivo).replace('.pdf', '.csv')}"
            try:
                total_movimientos = extraer_estado_cuenta_wallet(archivo, temp_csv)
                if total_movimientos > 0:
                    with open(temp_csv, mode='r', newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        combined_rows.extend(reader)
                os.remove(temp_csv)
            except Exception as e:
                print(f"❌ Error en {archivo}: {e}")

        if combined_rows:
            combined_rows = ordenar_por_fecha_registros(combined_rows)
            combined_csv = "Wallet_Fmt_All.csv"
            with open(combined_csv, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['date', 'amount', 'payee', 'category', 'account', 'note'])
                writer.writeheader()
                writer.writerows(combined_rows)
            print(f"\n✅ CSV combinado generado: {combined_csv}")
        else:
            print("\n⚠️ No se encontraron registros para combinar.")
    else:
        print(f"Se encontraron {len(archivos_pdf)} archivos PDF. Procesando con formato BudgetBakers...\n")
        for archivo in archivos_pdf:
            nombre_csv = f"Wallet_Fmt_{archivo.replace('.pdf', '.csv')}"
            try:
                total_movimientos = extraer_estado_cuenta_wallet(archivo, nombre_csv)
                if total_movimientos > 0:
                    print(f"✅ Éxito: {archivo} -> {total_movimientos} registros.")
                else:
                    print(f"⚠️ Vacío: {archivo} -> Sin registros.")
            except Exception as e:
                print(f"❌ Error en {archivo}: {e}")

        print("\n¡Archivos listos con la estructura exacta!")


if __name__ == "__main__":
    main()
