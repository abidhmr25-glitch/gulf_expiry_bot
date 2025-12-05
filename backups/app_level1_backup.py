from datetime import datetime, date
import json
import os

from fpdf import FPDF
import gradio as gr

# ---------- CONFIG ----------

DATA_FILE = "data.json"

DOC_TYPES = [
    "Emirates ID",
    "Visa",
    "Driving License",
    "Passport",
    "Car Insurance",
    "Tenancy Contract",
]


# ---------- DATA HELPERS ----------

def load_data():
    """Load saved document data from JSON file."""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    """Save document data to JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def parse_date(dstr: str):
    """
    Convert a string 'YYYY-MM-DD' to a date object.
    Returns None if format is wrong.
    """
    if not dstr:
        return None
    try:
        return datetime.strptime(dstr.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def days_until(expiry: date) -> int:
    """Return how many days from today until expiry (can be negative if expired)."""
    today = date.today()
    return (expiry - today).days


# ---------- CORE LOGIC ----------

def update_documents(
    emirates_id_exp, emirates_id_rem,
    visa_exp, visa_rem,
    license_exp, license_rem,
    passport_exp, passport_rem,
    insurance_exp, insurance_rem,
    tenancy_exp, tenancy_rem,
):
    """
    This function is called when user clicks the button.
    It:
      - reads all inputs
      - validates them
      - saves to data.json
      - builds a summary text
      - creates a PDF
      - returns (summary_text, pdf_file_path)
    """

    # 1. Pack raw inputs in a dict for easy looping
    raw_inputs = {
        "Emirates ID": (emirates_id_exp, emirates_id_rem),
        "Visa": (visa_exp, visa_rem),
        "Driving License": (license_exp, license_rem),
        "Passport": (passport_exp, passport_rem),
        "Car Insurance": (insurance_exp, insurance_rem),
        "Tenancy Contract": (tenancy_exp, tenancy_rem),
    }

    data = {}
    errors = []

    # 2. Validate each document
    for doc_type, (date_str, reminder_str) in raw_inputs.items():
        # skip empty ones (user may not fill all)
        if not date_str:
            continue

        expiry_date = parse_date(date_str)
        if not expiry_date:
            errors.append(f"{doc_type}: invalid date (use YYYY-MM-DD).")
            continue

        # parse reminder days
        if reminder_str in (None, ""):
            reminder_days = 30  # default
        else:
            try:
                reminder_days = int(reminder_str)
            except ValueError:
                reminder_days = 30
                errors.append(
                    f"{doc_type}: invalid reminder days, using 30 by default."
                )

        data[doc_type] = {
            "expiry": date_str.strip(),
            "reminder_days": reminder_days,
        }

    # 3. Save to JSON file
    save_data(data)

    # 4. Build summary text
    summary_text = build_summary(data, errors)

    # 5. Generate PDF and return file path
    pdf_path = generate_pdf(summary_text)

    return summary_text, pdf_path


def build_summary(data: dict, errors: list) -> str:
    """Create a nice human-readable summary text (no emojis, no unicode)."""
    lines = []

    # show any validation issues at the top
    if errors:
        lines.append("Some issues found while saving your data:")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    today_str = date.today().strftime("%Y-%m-%d")
    lines.append(f"Expiry Summary (Today: {today_str})")
    lines.append("")

    if not data:
        lines.append("No documents saved yet.")
    else:
        for doc_type, info in data.items():
            expiry_date = parse_date(info["expiry"])
            dleft = days_until(expiry_date)

            if dleft < 0:
                status = "EXPIRED"
            elif dleft <= 30:
                status = "NEAR EXPIRY"
            else:
                status = "OK"

            lines.append(
                f"{doc_type}: expires on {info['expiry']} "
                f"({dleft} days left) - status: {status}, "
                f"reminder at {info['reminder_days']} days before."
            )

    return "\n".join(lines)

def generate_pdf(text: str) -> str:
    """
    Generate a simple PDF file from the summary text.
    Returns the file path.
    """
    if not text:
        text = "No data available."

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for line in text.split("\n"):
        pdf.multi_cell(0, 8, line)

    output_path = "expiry_summary.pdf"
    pdf.output(output_path)
    return output_path


# ---------- UI (GRADIO) ----------

with gr.Blocks() as demo:
    gr.Markdown("# 🕒 Gulf Expiry Helper — Level 1 (Demo)")
    gr.Markdown(
        "Enter your document expiry dates in **YYYY-MM-DD** format and when "
        "you want a reminder. This is a local demo running on your PC."
    )

    with gr.Row():
        with gr.Column():
            emirates_id_exp = gr.Textbox(
                label="Emirates ID expiry (YYYY-MM-DD)"
            )
            emirates_id_rem = gr.Textbox(
                label="Remind me X days before (Emirates ID)",
                value="30",
            )

            visa_exp = gr.Textbox(
                label="Visa expiry (YYYY-MM-DD)"
            )
            visa_rem = gr.Textbox(
                label="Remind me X days before (Visa)",
                value="30",
            )

            license_exp = gr.Textbox(
                label="Driving License expiry (YYYY-MM-DD)"
            )
            license_rem = gr.Textbox(
                label="Remind me X days before (License)",
                value="30",
            )

        with gr.Column():
            passport_exp = gr.Textbox(
                label="Passport expiry (YYYY-MM-DD)"
            )
            passport_rem = gr.Textbox(
                label="Remind me X days before (Passport)",
                value="60",
            )

            insurance_exp = gr.Textbox(
                label="Car Insurance expiry (YYYY-MM-DD)"
            )
            insurance_rem = gr.Textbox(
                label="Remind me X days before (Car Insurance)",
                value="15",
            )

            tenancy_exp = gr.Textbox(
                label="Tenancy Contract expiry (YYYY-MM-DD)"
            )
            tenancy_rem = gr.Textbox(
                label="Remind me X days before (Tenancy Contract)",
                value="30",
            )

    submit_btn = gr.Button("💾 Save & Show Summary")

    summary_box = gr.Textbox(
        label="Summary",
        lines=12,
    )

    pdf_out = gr.File(
        label="Download Summary PDF"
    )

    submit_btn.click(
        fn=update_documents,
        inputs=[
            emirates_id_exp, emirates_id_rem,
            visa_exp, visa_rem,
            license_exp, license_rem,
            passport_exp, passport_rem,
            insurance_exp, insurance_rem,
            tenancy_exp, tenancy_rem,
        ],
        outputs=[summary_box, pdf_out],
    )


if __name__ == "__main__":
    demo.launch()
