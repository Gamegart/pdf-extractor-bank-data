import pdfplumber
import csv
import re
import glob
import os
if __package__:
    from .date_utils import statement_period_from_filename, year_for_transaction_month
else:
    from date_utils import statement_period_from_filename, year_for_transaction_month

def categorizar_y_limpiar(description, is_income):
    """Asigna la categoría de BudgetBakers basándose en palabras clave."""
    desc_upper = description.upper()

    if "PAGO DEL RESUMEN" in desc_upper or "PAGO DE TARJETA" in desc_upper:
        return "Transfer", description
    if is_income or any(k in desc_upper for k in ["NOMINA", "SPEI RECIBIDO", "TRANSFERENCIA RECIBIDA", "DEPOSITO"]):
        return "Income", description
    if any(k in desc_upper for k in ["OXXO", "7-ELEVEN"]):
        return "Food & Drinks", description
    if any(k in desc_upper for k in ["STARBUCKS", "CAFFENIO", "CAFE", "BAR"]):
        return "Bar, cafe", description
    if any(k in desc_upper for k in ["RESTAURANT", "ALITAS", "PIZZA", "BURGER", "CARLS JR", "KFC", "WINGS STOP"]):
        return "Restaurant, fast-food", description
    if any(k in desc_upper for k in ["SORIANA", "WALMART", "HEB", "COSTCO", "SAM'S"]):
        return "Groceries", description
    if any(k in desc_upper for k in ["F AHORRO", "FARMACIA", "BENAVIDES", "CETAPHIL", "NEUTROGENA"]):
        return "Health and beauty", description
    if any(k in desc_upper for k in ["GASOL", "PEMEX", "BP", "SHELL", "G500"]):
        return "Fuel", description
    if any(k in desc_upper for k in ["TALLER", "REFACCIONES", "SERVICIO AUTO", "AUTOSHOW"]):
        return "Vehicle maintenance", description
    if any(k in desc_upper for k in ["TELMEX", "IZZI", "TOTALPLAY", "INTERNET"]):
        return "Internet", description
    if any(k in desc_upper for k in ["TELCEL", "AT&T", "MOVISTAR", "RECARGA"]):
        return "Telephony, mobile phone", description
    if any(k in desc_upper for k in ["STEAM", "PLAYSTATION", "XBOX", "NINTENDO"]):
        return "Software, apps, games", description
    if any(k in desc_upper for k in ["SPOTIFY"]):
        return "Spotify", description
    if any(k in desc_upper for k in ["NETFLIX", "DISNEY", "HBO", "PRIME VIDEO", "CINEPOLIS", "CINEMEX"]):
        return "Cine, tv, streaming", description
    if any(k in desc_upper for k in ["PULL&BEAR", "H&M", "ZARA", "VANS"]):
        return "Clothes & Footwear", description
    if any(k in desc_upper for k in ["AMAZON", "MERCADO PAGO", "MERPAGO", "MERCADOLIBRE"]):
        return "Shopping", description
    if any(k in desc_upper for k in ["UBER", "DIDIMOVIL", "TAXI"]):
        return "Taxi", description
    if any(k in desc_upper for k in ["COMISION", "INTERESES", "IVA"]):
        return "Financial expenses", description

    return "Others", description

def extraer_movimientos(pdf_path):
    records = []

    statement_year, statement_month = statement_period_from_filename(pdf_path, default_year=2026)

    # Regex TDC: "11/07 Compra en MERCADO PAGO 1 14 de 24 $770.79"
    regex_tdc = re.compile(r'(\d{2}/\d{2})\s+(.*?)\s+(-?\s*\$\s*[\d,]+\.\d{2})')

    # Regex Wallet: "02/ene/2026 15:28:50 Cargo - Pago Mi att a app ta 139787166285 -$ 200.00"
    regex_wallet = re.compile(r'(\d{2}/[a-z]{3}/\d{4})\s+\d{2}:\d{2}:\d{2}\s+(.*?)\s+([+-]\s*\$\s*[\d,]+\.\d{2})', re.IGNORECASE)
    meses_str = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # layout=True mantiene la estructura de la línea intacta
            text = page.extract_text(layout=True)
            if not text: continue

            for line in text.split('\n'):

                # --- INTENTO 1: Formato Tarjeta de Crédito ---
                match_tdc = regex_tdc.search(line)
                if match_tdc and "Saldo a meses" not in line:
                    dia, mes = match_tdc.group(1).split('/')
                    desc_raw = match_tdc.group(2).strip()
                    monto_raw = match_tdc.group(3)

                    transaction_year = year_for_transaction_month(
                        int(mes), statement_year, statement_month
                    )
                    date_formatted = f"{transaction_year}-{int(mes):02d}-{int(dia):02d} 12:00:00"
                    monto_limpio = re.sub(r'[^\d\.-]', '', monto_raw.replace(' ', ''))

                    # Invertir el signo (Compras negativo, Pagos positivo)
                    if '-' in monto_limpio:
                        amount = monto_limpio.replace('-', '')
                    else:
                        amount = f"-{monto_limpio}"

                    cat, desc_final = categorizar_y_limpiar(desc_raw, '-' in monto_limpio)

                    records.append({
                        'date': date_formatted, 'amount': amount,
                        'payee': desc_final, 'category': cat,
                        'account': 'Mercado Pago TDC', 'note': desc_final
                    })
                    continue

                # --- INTENTO 2: Formato Wallet ---
                match_wallet = regex_wallet.search(line)
                if match_wallet:
                    # Ignorar los rendimientos de Mercado Lending para mantener limpio el balance
                    if 'Programa Loyalty' in line:
                        continue

                    fecha_str = match_wallet.group(1)
                    desc_raw = match_wallet.group(2).strip()
                    monto_raw = match_wallet.group(3)

                    dia, mes_texto, anio = fecha_str.split('/')
                    mes = meses_str.get(mes_texto.lower(), 1)
                    date_formatted = f"{anio}-{mes:02d}-{int(dia):02d} 12:00:00"

                    amount = re.sub(r'[^\d\.-]', '', monto_raw.replace(' ', ''))
                    cat, desc_final = categorizar_y_limpiar(desc_raw, not amount.startswith('-'))

                    records.append({
                        'date': date_formatted, 'amount': amount,
                        'payee': desc_final, 'category': cat,
                        'account': 'Mercado Pago Wallet', 'note': desc_final
                    })

    return records

def guardar_registros_csv(records, csv_path):
    if not records:
        return 0

    records = sorted(records, key=lambda r: r['date'])
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'amount', 'payee', 'category', 'account', 'note'])
        writer.writeheader()
        writer.writerows(records)

    return len(records)

def procesar_mercado_pago(pdf_path, csv_path):
    return guardar_registros_csv(extraer_movimientos(pdf_path), csv_path)

def procesar_todos_en_un_csv(pdf_paths, csv_path):
    records = []
    for pdf_path in pdf_paths:
        records.extend(extraer_movimientos(pdf_path))
    return guardar_registros_csv(records, csv_path)

def main():
    archivos_pdf = glob.glob("*.pdf")
    if not archivos_pdf:
        print("No se encontraron archivos PDF en esta carpeta.")
        return

    while True:
        modo_salida = input("Elige el formato de salida: [1] CSV por PDF, [2] un solo CSV: ").strip()
        if modo_salida in ("1", "2"):
            break
        print("Opción no válida. Escribe 1 o 2.")

    if modo_salida == "1":
        for archivo in archivos_pdf:
            nombre_csv = f"Wallet_MP_{archivo.replace('.pdf', '.csv')}"
            total_movimientos = procesar_mercado_pago(archivo, nombre_csv)
            if total_movimientos > 0:
                print(f"Procesado: {archivo} -> {total_movimientos} registros en {nombre_csv}")
    else:
        nombre_csv = "Wallet_MP_Todos.csv"
        total_movimientos = procesar_todos_en_un_csv(archivos_pdf, nombre_csv)
        if total_movimientos > 0:
            print(f"Procesados {len(archivos_pdf)} PDF -> {total_movimientos} registros en {nombre_csv}")
        else:
            print("No se encontraron movimientos en los PDF.")


if __name__ == "__main__":
    main()
