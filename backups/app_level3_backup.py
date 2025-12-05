from datetime import datetime, date
import json
import os
from typing import Dict, Any, List, Tuple

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

def _empty_storage() -> Dict[str, Any]:
    """
    Unified storage format:

    {
      "profiles": {
         "<profile_name>": { "<doc_type>": {"expiry": "...", "reminder_days": 30}, ... }
      },
      "companies": {
         "<company_name>": {
             "employees": {
                 "<emp_id>": {
                     "name": "...",
                     "role": "...",
                     "docs": { "<doc_type>": {...} }
                 }
             }
         }
      }
    }
    """
    return {"profiles": {}, "companies": {}}


def load_data() -> Dict[str, Any]:
    """Load storage from JSON, auto-migrate old format if needed."""
    if not os.path.exists(DATA_FILE):
        return _empty_storage()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # corrupted file → start fresh
        return _empty_storage()

    # New format already
    if isinstance(data, dict) and ("profiles" in data or "companies" in data):
        profiles = data.get("profiles", {})
        companies = data.get("companies", {})
        return {"profiles": profiles, "companies": companies}

    # Old format (top-level profiles only, like {"Self": {...}, "wife": {...}})
    if isinstance(data, dict):
        return {"profiles": data, "companies": {}}

    # Fallback
    return _empty_storage()


def save_data(storage: Dict[str, Any]) -> None:
    """Save full storage to JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(storage, f, indent=2)


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


# ---------- PDF HELPER ----------

def generate_pdf(text: str, filename: str = "expiry_summary.pdf") -> str:
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
        # Latin-1 safe text (avoids emoji / fancy dash crashes)
        safe_line = line.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 8, safe_line)

    pdf.output(filename)
    return filename


# ---------- PROFILE (FAMILY) LOGIC ----------

def build_profile_summary(profile_name: str, data: dict, errors: List[str]) -> str:
    """Create a human-readable summary for a single profile."""
    lines: List[str] = []

    if errors:
        lines.append("Some issues found while saving your data:")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    today_str = date.today().strftime("%Y-%m-%d")
    lines.append(f"Expiry Summary for profile: {profile_name} (Today: {today_str})")
    lines.append("")

    if not data:
        lines.append("No documents saved yet for this profile.")
    else:
        for doc_type, info in data.items():
            expiry_date = parse_date(info.get("expiry", ""))
            if not expiry_date:
                lines.append(f"{doc_type}: invalid or missing expiry date.")
                continue

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
                f"reminder at {info.get('reminder_days', 30)} days before."
            )

    return "\n".join(lines)


def update_profile_documents(
    profile_name,
    emirates_id_exp, emirates_id_rem,
    visa_exp, visa_rem,
    license_exp, license_rem,
    passport_exp, passport_rem,
    insurance_exp, insurance_rem,
    tenancy_exp, tenancy_rem,
):
    """
    Handles saving / updating documents for a single profile (family member).
    """

    # Decide profile name
    if not profile_name or not profile_name.strip():
        profile_name = "Self"
    profile_name = profile_name.strip()

    storage = load_data()
    profiles = storage.get("profiles", {})

    raw_inputs = {
        "Emirates ID": (emirates_id_exp, emirates_id_rem),
        "Visa": (visa_exp, visa_rem),
        "Driving License": (license_exp, license_rem),
        "Passport": (passport_exp, passport_rem),
        "Car Insurance": (insurance_exp, insurance_rem),
        "Tenancy Contract": (tenancy_exp, tenancy_rem),
    }

    profile_docs: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    for doc_type, (date_str, reminder_str) in raw_inputs.items():
        if not date_str:
            continue

        expiry_date = parse_date(date_str)
        if not expiry_date:
            errors.append(f"{doc_type}: invalid date (use YYYY-MM-DD).")
            continue

        if reminder_str in (None, ""):
            reminder_days = 30
        else:
            try:
                reminder_days = int(reminder_str)
            except ValueError:
                reminder_days = 30
                errors.append(
                    f"{doc_type}: invalid reminder days, using 30 by default."
                )

        profile_docs[doc_type] = {
            "expiry": date_str.strip(),
            "reminder_days": reminder_days,
        }

    # Attach to profiles and save
    profiles[profile_name] = profile_docs
    storage["profiles"] = profiles
    save_data(storage)

    # Build summary and PDF
    summary_text = build_profile_summary(profile_name, profile_docs, errors)
    pdf_path = generate_pdf(summary_text, filename=f"profile_{profile_name}_summary.pdf")

    return summary_text, pdf_path


# ---------- COMPANY / HR LOGIC ----------

def _next_employee_id(employees: Dict[str, Any]) -> str:
    """Generate a simple incremental employee id as string."""
    if not employees:
        return "1"
    try:
        max_id = max(int(eid) for eid in employees.keys())
    except Exception:
        # fallback if keys are weird
        return str(len(employees) + 1)
    return str(max_id + 1)


def build_company_summary(company_name: str, company: dict) -> Tuple[str, List[List[Any]]]:
    """
    Build a text summary and table rows for a company's employees.
    Returns (text_summary, table_rows).
    """
    lines: List[str] = []
    rows: List[List[Any]] = []

    today_str = date.today().strftime("%Y-%m-%d")
    lines.append(f"Company expiry summary: {company_name} (Today: {today_str})")
    lines.append("")

    employees = company.get("employees", {})
    if not employees:
        lines.append("No employees saved yet for this company.")
        return "\n".join(lines), rows

    for emp_id, emp in employees.items():
        name = emp.get("name", f"Employee {emp_id}")
        role = emp.get("role", "")
        docs = emp.get("docs", {})

        next_expiry_days = None  # type: ignore
        next_expiry_label = ""

        for doc_type, info in docs.items():
            expiry_date = parse_date(info.get("expiry", ""))
            if not expiry_date:
                continue
            dleft = days_until(expiry_date)

            if next_expiry_days is None or dleft < next_expiry_days:
                next_expiry_days = dleft
                next_expiry_label = f"{doc_type} ({info.get('expiry', '')})"

        if next_expiry_days is None:
            status = "NO DOCUMENTS"
            days_left_display = ""
        else:
            days_left_display = str(next_expiry_days)
            if next_expiry_days < 0:
                status = "EXPIRED"
            elif next_expiry_days <= 30:
                status = "NEAR EXPIRY"
            else:
                status = "OK"

        lines.append(
            f"{name} - {role}: "
            f"next expiry: {next_expiry_label or 'N/A'}, "
            f"days left: {days_left_display or 'N/A'}, "
            f"status: {status}"
        )

        rows.append([
            name,
            role,
            next_expiry_label or "",
            days_left_display,
            status,
        ])

    return "\n".join(lines), rows


def save_employee(
    company_name,
    employee_name,
    employee_role,
    emirates_id_exp, emirates_id_rem,
    visa_exp, visa_rem,
    license_exp, license_rem,
    passport_exp, passport_rem,
    insurance_exp, insurance_rem,
    tenancy_exp, tenancy_rem,
):
    """
    Add or update an employee for a given company and return:
    - company summary text
    - company PDF path
    - employees table rows
    - validation messages
    """
    messages: List[str] = []

    if not company_name or not company_name.strip():
        company_name = "Default Company"
    company_name = company_name.strip()

    if not employee_name or not employee_name.strip():
        employee_name = "Unnamed employee"
        messages.append("Employee name was empty. Using 'Unnamed employee'.")

    employee_role = (employee_role or "").strip()

    storage = load_data()
    companies = storage.get("companies", {})

    company = companies.get(company_name, {"employees": {}})
    employees = company.get("employees", {})

    raw_inputs = {
        "Emirates ID": (emirates_id_exp, emirates_id_rem),
        "Visa": (visa_exp, visa_rem),
        "Driving License": (license_exp, license_rem),
        "Passport": (passport_exp, passport_rem),
        "Car Insurance": (insurance_exp, insurance_rem),
        "Tenancy Contract": (tenancy_exp, tenancy_rem),
    }

    docs: Dict[str, Dict[str, Any]] = []
    docs = {}
    doc_errors: List[str] = []

    for doc_type, (date_str, reminder_str) in raw_inputs.items():
        if not date_str:
            continue

        expiry_date = parse_date(date_str)
        if not expiry_date:
            doc_errors.append(f"{doc_type}: invalid date (use YYYY-MM-DD).")
            continue

        if reminder_str in (None, ""):
            reminder_days = 30
        else:
            try:
                reminder_days = int(reminder_str)
            except ValueError:
                reminder_days = 30
                doc_errors.append(
                    f"{doc_type}: invalid reminder days, using 30 by default."
                )

        docs[doc_type] = {
            "expiry": date_str.strip(),
            "reminder_days": reminder_days,
        }

    if doc_errors:
        messages.extend(doc_errors)

    emp_id = _next_employee_id(employees)
    employees[emp_id] = {
        "name": employee_name.strip(),
        "role": employee_role,
        "docs": docs,
    }

    company["employees"] = employees
    companies[company_name] = company
    storage["companies"] = companies
    save_data(storage)

    company_summary, rows = build_company_summary(company_name, company)
    pdf_path = generate_pdf(
        company_summary,
        filename=f"company_{company_name.replace(' ', '_')}_summary.pdf",
    )

    # join messages into a single string for UI
    messages_text = "\n".join(messages) if messages else "Saved successfully."

    return company_summary, pdf_path, rows, messages_text


# ---------- UI (GRADIO) ----------

with gr.Blocks() as demo:
    gr.Markdown("# Gulf Fines & Expiry Helper – Demo")

    with gr.Tab("Personal profiles"):
        gr.Markdown(
            "Track expiries for yourself and family members.\n"
            "Enter dates in YYYY-MM-DD format."
        )

        profile_name_input = gr.Textbox(
            label="Profile name (e.g., Self, Wife, Dad)",
            value="Self",
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

        submit_profile_btn = gr.Button("Save profile and show summary")

        profile_summary_box = gr.Textbox(
            label="Profile summary",
            lines=12,
        )

        profile_pdf_out = gr.File(
            label="Download profile summary PDF"
        )

        submit_profile_btn.click(
            fn=update_profile_documents,
            inputs=[
                profile_name_input,
                emirates_id_exp, emirates_id_rem,
                visa_exp, visa_rem,
                license_exp, license_rem,
                passport_exp, passport_rem,
                insurance_exp, insurance_rem,
                tenancy_exp, tenancy_rem,
            ],
            outputs=[profile_summary_box, profile_pdf_out],
        )

    with gr.Tab("Company HR dashboard"):
        gr.Markdown(
            "Basic HR view for small companies or PROs.\n"
            "Add employees and see upcoming expiries."
        )

        company_name_input = gr.Textbox(
            label="Company name",
            value="My Company",
        )

        with gr.Row():
            employee_name_input = gr.Textbox(
                label="Employee name"
            )
            employee_role_input = gr.Textbox(
                label="Role / position"
            )

        gr.Markdown("Employee document expiries (YYYY-MM-DD):")

        with gr.Row():
            with gr.Column():
                emirates_id_exp_hr = gr.Textbox(
                    label="Emirates ID expiry"
                )
                emirates_id_rem_hr = gr.Textbox(
                    label="Remind me X days before (Emirates ID)",
                    value="30",
                )

                visa_exp_hr = gr.Textbox(
                    label="Visa expiry"
                )
                visa_rem_hr = gr.Textbox(
                    label="Remind me X days before (Visa)",
                    value="30",
                )

                license_exp_hr = gr.Textbox(
                    label="Driving License expiry"
                )
                license_rem_hr = gr.Textbox(
                    label="Remind me X days before (License)",
                    value="30",
                )

            with gr.Column():
                passport_exp_hr = gr.Textbox(
                    label="Passport expiry"
                )
                passport_rem_hr = gr.Textbox(
                    label="Remind me X days before (Passport)",
                    value="60",
                )

                insurance_exp_hr = gr.Textbox(
                    label="Insurance expiry"
                )
                insurance_rem_hr = gr.Textbox(
                    label="Remind me X days before (Insurance)",
                    value="15",
                )

                tenancy_exp_hr = gr.Textbox(
                    label="Tenancy / contract expiry"
                )
                tenancy_rem_hr = gr.Textbox(
                    label="Remind me X days before (Tenancy)",
                    value="30",
                )

        save_employee_btn = gr.Button("Save employee and update company summary")

        company_summary_box = gr.Textbox(
            label="Company summary",
            lines=12,
        )

        company_pdf_out = gr.File(
            label="Download company summary PDF"
        )

        employees_table = gr.Dataframe(
            headers=["Name", "Role", "Next expiry", "Days left", "Status"],
            row_count=(0, "dynamic"),
            col_count=5,
        )

        hr_messages_box = gr.Textbox(
            label="Messages",
            lines=3,
        )

        save_employee_btn.click(
            fn=save_employee,
            inputs=[
                company_name_input,
                employee_name_input,
                employee_role_input,
                emirates_id_exp_hr, emirates_id_rem_hr,
                visa_exp_hr, visa_rem_hr,
                license_exp_hr, license_rem_hr,
                passport_exp_hr, passport_rem_hr,
                insurance_exp_hr, insurance_rem_hr,
                tenancy_exp_hr, tenancy_rem_hr,
            ],
            outputs=[
                company_summary_box,
                company_pdf_out,
                employees_table,
                hr_messages_box,
            ],
        )


if __name__ == "__main__":
    demo.launch()
