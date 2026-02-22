from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pdfplumber
import re
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": None}
    )


@app.post("/upload", response_class=HTMLResponse)
async def upload_invoice(request: Request, file: UploadFile = File(...)):

    contents = await file.read()
    temp_path = "temp.pdf"

    with open(temp_path, "wb") as f:
        f.write(contents)

    text = ""
    with pdfplumber.open(temp_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    print("\n========== EXTRACTED TEXT ==========\n")
    print(text)
    print("\n====================================\n")

    invoice_value = "Not found"
    date_value = "Not found"
    subtotal = 0.0
    vat = 0.0
    total_amount = 0.0

    # -------- Invoice Number --------
    invoice_match = re.search(
        r"(Tax\s*Invoice\s*#|Invoice\s*No\.?|Invoice\s*Number)\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
        text,
        re.IGNORECASE
    )

    if invoice_match:
        invoice_value = invoice_match.group(2)

    # -------- Date (FIXED) --------
    date_match = re.search(
        r"Invoice\s*Date\s*[:\-]?\s*([A-Za-z0-9\-\(\)\/]+)",
        text,
        re.IGNORECASE
    )

    if date_match:
        date_value = date_match.group(1).strip()
    else:
        # fallback: look for standalone DATE format like DATE 14/10/2018
        fallback_date = re.search(
            r"\bDATE\s*[:\-]?\s*([0-9\/\-]+)",
            text,
            re.IGNORECASE
        )
        if fallback_date:
            date_value = fallback_date.group(1)

    # -------- SPECIAL CASE: "Total in : AED ..." --------
    total_in_match = re.search(
        r"Total\s*in\s*:\s*AED\s*([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)",
        text,
        re.IGNORECASE
    )

    if total_in_match:
        subtotal = float(total_in_match.group(1))
        vat = float(total_in_match.group(2))
        total_amount = float(total_in_match.group(3))

    # -------- Fallback: Try keyword search --------
    else:
        for line in text.split("\n"):

            if re.search(r"sub\s*total", line, re.IGNORECASE):
                value = re.search(r"[\d,]+\.\d{2,3}", line)
                if value:
                    subtotal = float(value.group().replace(",", ""))

            elif re.search(r"vat", line, re.IGNORECASE):
                value = re.search(r"[\d,]+\.\d{2,3}", line)
                if value:
                    vat = float(value.group().replace(",", ""))

            elif re.search(r"grand\s*total|total\s*amount|^total", line, re.IGNORECASE):
                value = re.search(r"[\d,]+\.\d{2,3}", line)
                if value:
                    total_amount = float(value.group().replace(",", ""))

    result = {
        "Invoice Number": invoice_value,
        "Date": date_value,
        "Subtotal": f"{subtotal:,.3f}" if subtotal else "Not found",
        "VAT (5%)": f"{vat:,.3f}" if vat else "Not found",
        "Total Amount": f"{total_amount:,.3f}" if total_amount else "Not found"
    }

    if os.path.exists(temp_path):
        os.remove(temp_path)

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": result}
    )
