import csv
from datetime import datetime
import io
from pathlib import Path
import socket
import tempfile
import threading
from urllib.request import urlopen
import uuid
import webbrowser
import zipfile

from flask import Flask, abort, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from parsers import BBVA_TDC_PDFx, BBVA_TDD_PDFx, MP_TDC_PDFx


CSV_FIELDS = ["date", "amount", "payee", "category", "account", "note"]
PARSERS = {
    "mercado_pago": ("Mercado Pago (TDC / Wallet)", MP_TDC_PDFx.extraer_movimientos),
    "bbva_tdc": ("BBVA (TDC)", BBVA_TDC_PDFx.parse_pdf),
    "bbva_tdd": ("BBVA (TDD / Estado de cuenta)", BBVA_TDD_PDFx.parse_pdf),
}
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
DOWNLOADS = {}


def normalize_record(record):
    normalized = {}
    for field in CSV_FIELDS:
        value = record.get(field)
        if value is None:
            value = record.get(field.title(), "")
        if field == "amount" and isinstance(value, float):
            value = f"{value:.2f}"
        normalized[field] = value if value is not None else ""
    return normalized


def sort_date(record):
    value = str(record.get("date", "")).strip()
    for date_format in ("%d/%m/%Y %I:%M %p", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.max


def records_to_csv(records):
    records = sorted(records, key=sort_date)
    csv_file = io.StringIO(newline="")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(records)
    return csv_file.getvalue().encode("utf-8-sig")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", parsers=PARSERS, output_mode="separate")

    output_mode = request.form.get("output_mode", "separate")
    uploads = [
        (parser_key, upload)
        for parser_key in PARSERS
        for upload in request.files.getlist(f"pdfs_{parser_key}")
        if upload and upload.filename
    ]
    if not uploads:
        return render_template(
            "index.html",
            parsers=PARSERS,
            output_mode=output_mode,
            errors=["Choose at least one PDF to process."],
        )

    records_by_pdf = []
    combined_records = []
    errors = []
    processed_count = 0

    with tempfile.TemporaryDirectory(prefix="pdf-statement-") as temp_dir:
        for index, (parser_key, upload) in enumerate(uploads, start=1):
            original_name = secure_filename(upload.filename)
            if not original_name.lower().endswith(".pdf"):
                errors.append(f"{upload.filename}: file is not a PDF.")
                continue

            pdf_path = Path(temp_dir) / f"{index}_{original_name}"
            upload.save(pdf_path)
            try:
                parser = PARSERS[parser_key][1]
                records = [normalize_record(record) for record in parser(str(pdf_path))]
                processed_count += 1
                if records:
                    combined_records.extend(records)
                    csv_name = f"{index:02d}_{parser_key}_{Path(original_name).stem}_BudgetBakers.csv"
                    records_by_pdf.append((secure_filename(csv_name), records_to_csv(records)))
            except Exception as error:
                errors.append(f"{original_name}: {error}")

    result = None
    if output_mode == "combined" and combined_records:
        payload = records_to_csv(combined_records)
        filename = "transactions_all.csv"
        mimetype = "text/csv; charset=utf-8"
    elif output_mode == "separate" and records_by_pdf:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for filename, payload in records_by_pdf:
                zip_file.writestr(filename, payload)
        payload = archive.getvalue()
        filename = "transactions_separate.zip"
        mimetype = "application/zip"
    else:
        payload = None
        filename = ""
        mimetype = ""

    if payload is not None:
        DOWNLOADS.clear()
        token = uuid.uuid4().hex
        DOWNLOADS[token] = (filename, mimetype, payload)
        result = {
            "file_count": len(records_by_pdf) if output_mode == "separate" else processed_count,
            "transaction_count": len(combined_records),
            "filename": filename,
            "download_url": url_for("download", token=token),
        }
    elif not errors:
        errors.append("No transactions were found in the selected PDFs.")

    return render_template(
        "index.html",
        parsers=PARSERS,
        output_mode=output_mode,
        result=result,
        errors=errors,
    )


@app.route("/download/<token>")
def download(token):
    download_item = DOWNLOADS.get(token)
    if download_item is None:
        abort(404)
    filename, mimetype, payload = download_item
    return send_file(
        io.BytesIO(payload),
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )


def find_running_app_port():
    for port in range(5000, 5100):
        try:
            with urlopen(f"http://127.0.0.1:{port}/", timeout=0.4) as response:
                if b"<title>PDF Statement Extractor</title>" in response.read(8192):
                    return port
        except OSError:
            continue
    return None


def find_available_port():
    for port in range(5000, 5100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    raise RuntimeError("No available local port found between 5000 and 5099.")


def main():
    existing_port = find_running_app_port()
    if existing_port is not None:
        address = f"http://127.0.0.1:{existing_port}"
        print(f"PDF Statement Extractor is already running at {address}")
        webbrowser.open(address)
        return

    port = find_available_port()
    address = f"http://127.0.0.1:{port}"
    threading.Timer(1, lambda: webbrowser.open(address)).start()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()