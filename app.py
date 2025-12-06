from datetime import datetime, date
import json
import os
from typing import Dict, Any, List, Tuple

from fpdf import FPDF
import gradio as gr

# ---------- CONFIG ----------

from config import DATA_FILE

DOC_TYPES = [
    "Emirates ID",
    "Visa",
    "Driving License",
    "Passport",
    "Car Insurance",
    "Tenancy Contract",
]


# ---------- DATA STORE HELPERS ----------

def _empty_store() -> Dict[str, Any]:
    """Return a clean default store structure."""
    return {"profiles": {}, "companies": {}}


def load_store() -> Dict[str, Any]:
    """
    Load the full data store from JSON, with migration from older formats.
    Ensures the structure:
      {
        "profiles": {
           profile_name: {
               "docs": { doc_type: {expiry, reminder_days}, ... },
               "history": [ {timestamp, note}, ... ]
           },
           ...
        },
        "companies": {
           company_name: {
               "employees": [
                   {
                       "name": str,
                       "role": str,
                       "docs": { ... },
                       "history": [ ... ]
                   },
                   ...
               ]
           },
           ...
        }
      }
    """
    if not os.path.exists(DATA_FILE):
        return _empty_store()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return _empty_store()

    if not isinstance(raw, dict):
        raw = {}

    profiles = raw.get("profiles")
    companies = raw.get("companies")

    # If old format without "profiles"/"companies", treat everything as profiles
    if profiles is None and companies is None:
        profiles = raw
        companies = {}

    if profiles is None:
        profiles = {}
    if companies is None:
        companies = {}

    # Normalize profiles
    new_profiles: Dict[str, Any] = {}
    for pname, pdata in profiles.items():
        if not isinstance(pdata, dict):
            continue
        docs = pdata.get("docs")
        history = pdata.get("history", [])
        if docs is None:
            # Assume everything that looks like a doc dict is a document
            docs = {}
            for k, v in pdata.items():
                if isinstance(v, dict) and "expiry" in v:
                    docs[k] = v
        new_profiles[pname] = {
            "docs": docs if isinstance(docs, dict) else {},
            "history": history if isinstance(history, list) else [],
        }

    # Normalize companies
    new_companies: Dict[str, Any] = {}
    for cname, cdata in companies.items():
        if not isinstance(cdata, dict):
            continue
        employees = cdata.get("employees", [])
        clean_emps = []
        if isinstance(employees, list):
            for emp in employees:
                if not isinstance(emp, dict):
                    continue
                name = emp.get("name", "").strip()
                role = emp.get("role", "").strip()
                docs = emp.get("docs")
                history = emp.get("history", [])
                if docs is None:
                    docs = {}
                    for k, v in emp.items():
                        if isinstance(v, dict) and "expiry" in v:
                            docs[k] = v
                clean_emps.append(
                    {
                        "name": name,
                        "role": role,
                        "docs": docs if isinstance(docs, dict) else {},
                        "history": history if isinstance(history, list) else [],
                    }
                )
        new_companies[cname] = {"employees": clean_emps}

    return {"profiles": new_profiles, "companies": new_companies}


def save_store(store: Dict[str, Any]) -> None:
    """Persist the store back to JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


# ---------- DATE / STATUS HELPERS ----------

def parse_date(dstr: str):
    """Convert 'YYYY-MM-DD' string to date object, or None if invalid."""
    if not dstr:
        return None
    try:
        return datetime.strptime(dstr.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def days_until(expiry: date) -> int:
    """Return how many days from today until expiry (can be negative)."""
    today = date.today()
    return (expiry - today).days


def evaluate_doc(expiry_str: str, reminder_days: int) -> Dict[str, Any]:
    """
    Given expiry string and reminder days, return a dict with:
      {expiry, days_left, status, reminder_days}
    or {} if expiry is invalid.
    """
    expiry_date = parse_date(expiry_str)
    if not expiry_date:
        return {}

    dleft = days_until(expiry_date)
    if dleft < 0:
        status = "EXPIRED"
    elif dleft <= 30:
        status = "NEAR EXPIRY"
    else:
        status = "OK"

    return {
        "expiry": expiry_str,
        "days_left": dleft,
        "status": status,
        "reminder_days": reminder_days,
    }


# ---------- CORE LOGIC: PERSONAL PROFILES ----------

def save_profile(
    profile_name: str,
    emirates_id_exp: str, emirates_id_rem: str,
    visa_exp: str, visa_rem: str,
    license_exp: str, license_rem: str,
    passport_exp: str, passport_rem: str,
    insurance_exp: str, insurance_rem: str,
    tenancy_exp: str, tenancy_rem: str,
):
    """
    Save / update one profile's documents and return:
      - profile summary text
      - profile PDF path
      - overview table (list of rows) for all profiles
      - status message
    """
    if not profile_name or not profile_name.strip():
        profile_name = "Self"
    profile_name = profile_name.strip()

    store = load_store()
    profiles = store["profiles"]

    # Build docs for this profile
    raw_inputs = {
        "Emirates ID": (emirates_id_exp, emirates_id_rem),
        "Visa": (visa_exp, visa_rem),
        "Driving License": (license_exp, license_rem),
        "Passport": (passport_exp, passport_rem),
        "Car Insurance": (insurance_exp, insurance_rem),
        "Tenancy Contract": (tenancy_exp, tenancy_rem),
    }

    docs: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    for doc_type, (dstr, rstr) in raw_inputs.items():
        if not dstr:
            continue
        expiry_date = parse_date(dstr)
        if not expiry_date:
            errors.append(f"{doc_type}: invalid date (use YYYY-MM-DD).")
            continue

        if rstr in (None, ""):
            reminder_days = 30
        else:
            try:
                reminder_days = int(rstr)
            except ValueError:
                reminder_days = 30
                errors.append(
                    f"{doc_type}: invalid reminder days, using 30 by default."
                )

        docs[doc_type] = {
            "expiry": dstr.strip(),
            "reminder_days": reminder_days,
        }

    # Ensure profile exists
    existing = profiles.get(profile_name, {"docs": {}, "history": []})
    history = existing.get("history", [])

    # Append a simple history note
    history.append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "note": f"Profile updated with {len(docs)} documents.",
        }
    )

    profiles[profile_name] = {
        "docs": docs,
        "history": history,
    }

    save_store(store)

    # Build summary for this profile
    summary_text = build_profile_summary(profile_name, docs, errors)

    # Generate profile PDF
    pdf_path = generate_pdf(summary_text, f"profile_{profile_name}_summary.pdf")

    # Build overview table for all profiles
    overview_rows = build_profiles_overview_table(store)

    msg = "Saved successfully."
    if errors:
        msg += " Some issues were found; see summary."

    return summary_text, pdf_path, overview_rows, msg


def build_profile_summary(
    profile_name: str,
    docs: Dict[str, Dict[str, Any]],
    errors: List[str]
) -> str:
    """Create a readable summary for a single profile (ASCII only)."""
    lines: List[str] = []

    if errors:
        lines.append("Some issues found while saving your data:")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    today_str = date.today().strftime("%Y-%m-%d")
    lines.append(f"Expiry Summary for profile: {profile_name} (Today: {today_str})")
    lines.append("")

    if not docs:
        lines.append("No documents saved for this profile.")
    else:
        for doc_type, info in docs.items():
            expiry = info.get("expiry", "")
            reminder_days = int(info.get("reminder_days", 30))
            eva = evaluate_doc(expiry, reminder_days)
            if not eva:
                lines.append(f"{doc_type}: invalid expiry date.")
                continue
            lines.append(
                f"{doc_type}: expires on {eva['expiry']} "
                f"({eva['days_left']} days left) - status: {eva['status']}, "
                f"reminder at {eva['reminder_days']} days before."
            )

    return "\n".join(lines)


def build_profiles_overview_table(store: Dict[str, Any]) -> List[List[Any]]:
    """
    Build a small table: [Profile, Next document, Next expiry, Days left, Status]
    for all profiles.
    """
    rows: List[List[Any]] = []
    profiles = store.get("profiles", {})
    for pname, pdata in profiles.items():
        docs = pdata.get("docs", {})
        best_doc = None
        best_info = None
        for doc_type, info in docs.items():
            eva = evaluate_doc(info.get("expiry", ""), int(info.get("reminder_days", 30)))
            if not eva:
                continue
            if best_info is None or eva["days_left"] < best_info["days_left"]:
                best_info = eva
                best_doc = doc_type
        if best_info is None:
            rows.append([pname, "-", "-", "-", "NO VALID DOCS"])
        else:
            rows.append(
                [
                    pname,
                    best_doc,
                    best_info["expiry"],
                    best_info["days_left"],
                    best_info["status"],
                ]
            )
    # Sort by days_left ascending (soonest first)
    rows.sort(key=lambda r: r[3] if isinstance(r[3], int) else 99999)
    return rows


# ---------- CORE LOGIC: COMPANY HR / EMPLOYEES ----------

def save_employee(
    company_name: str,
    employee_name: str,
    role: str,
    emirates_id_exp: str, emirates_id_rem: str,
    visa_exp: str, visa_rem: str,
    license_exp: str, license_rem: str,
    passport_exp: str, passport_rem: str,
    insurance_exp: str, insurance_rem: str,
    tenancy_exp: str, tenancy_rem: str,
):
    """
    Save / update one employee under a company and return:
      - company summary text
      - company PDF path
      - employee table rows
      - status message
    """
    if not company_name or not company_name.strip():
        company_name = "My Company"
    company_name = company_name.strip()

    if not employee_name or not employee_name.strip():
        return "Employee name is required.", None, [], "Employee name is required."

    employee_name = employee_name.strip()
    role = (role or "").strip()

    store = load_store()
    companies = store["companies"]
    company = companies.get(company_name, {"employees": []})
    employees = company.get("employees", [])

    # Build docs
    raw_inputs = {
        "Emirates ID": (emirates_id_exp, emirates_id_rem),
        "Visa": (visa_exp, visa_rem),
        "Driving License": (license_exp, license_rem),
        "Passport": (passport_exp, passport_rem),
        "Car Insurance": (insurance_exp, insurance_rem),
        "Tenancy Contract": (tenancy_exp, tenancy_rem),
    }

    docs: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    for doc_type, (dstr, rstr) in raw_inputs.items():
        if not dstr:
            continue
        expiry_date = parse_date(dstr)
        if not expiry_date:
            errors.append(f"{doc_type}: invalid date (use YYYY-MM-DD).")
            continue

        if rstr in (None, ""):
            reminder_days = 30
        else:
            try:
                reminder_days = int(rstr)
            except ValueError:
                reminder_days = 30
                errors.append(
                    f"{doc_type}: invalid reminder days, using 30 by default."
                )

        docs[doc_type] = {
            "expiry": dstr.strip(),
            "reminder_days": reminder_days,
        }

    # Find existing employee with same name
    existing_index = None
    for idx, emp in enumerate(employees):
        if emp.get("name", "").strip().lower() == employee_name.lower():
            existing_index = idx
            break

    history: List[Dict[str, Any]]
    if existing_index is not None:
        history = employees[existing_index].get("history", [])
    else:
        history = []

    history.append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "note": f"Employee updated with {len(docs)} documents.",
        }
    )

    employee_record = {
        "name": employee_name,
        "role": role,
        "docs": docs,
        "history": history,
    }

    if existing_index is not None:
        employees[existing_index] = employee_record
    else:
        employees.append(employee_record)

    company["employees"] = employees
    companies[company_name] = company
    store["companies"] = companies
    save_store(store)

    # Build summary and table
    summary_text = build_company_summary(company_name, company, errors)
    pdf_path = generate_pdf(summary_text, f"company_{company_name}_summary.pdf")
    employee_rows = build_employee_table(company_name, company)

    msg = "Saved successfully."
    if errors:
        msg += " Some issues were found; see summary."

    return summary_text, pdf_path, employee_rows, msg


def build_company_summary(
    company_name: str,
    company: Dict[str, Any],
    errors: List[str],
) -> str:
    """Create a readable summary for one company (ASCII only)."""
    lines: List[str] = []

    if errors:
        lines.append("Some issues found while saving your data:")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    today_str = date.today().strftime("%Y-%m-%d")
    lines.append(f"Company expiry summary: {company_name} (Today: {today_str})")
    lines.append("")

    employees = company.get("employees", [])
    if not employees:
        lines.append("No employees saved for this company.")
        return "\n".join(lines)

    for emp in employees:
        name = emp.get("name", "") or "-"
        role = emp.get("role", "") or "-"
        docs = emp.get("docs", {})
        # Find next upcoming expiry for this employee
        best_doc = None
        best_info = None
        for doc_type, info in docs.items():
            eva = evaluate_doc(info.get("expiry", ""), int(info.get("reminder_days", 30)))
            if not eva:
                continue
            if best_info is None or eva["days_left"] < best_info["days_left"]:
                best_info = eva
                best_doc = doc_type
        if best_info is None:
            lines.append(f"{name} ({role}): no valid documents.")
        else:
            lines.append(
                f"{name} ({role}): next expiry {best_doc} on {best_info['expiry']} "
                f"({best_info['days_left']} days left), status: {best_info['status']}."
            )

    return "\n".join(lines)


def build_employee_table(company_name: str, company: Dict[str, Any]) -> List[List[Any]]:
    """
    Table rows: [Company, Name, Role, Next expiry doc, Next expiry date, Days left, Status]
    """
    rows: List[List[Any]] = []
    employees = company.get("employees", [])
    for emp in employees:
        name = emp.get("name", "") or "-"
        role = emp.get("role", "") or "-"
        docs = emp.get("docs", {})
        best_doc = None
        best_info = None
        for doc_type, info in docs.items():
            eva = evaluate_doc(info.get("expiry", ""), int(info.get("reminder_days", 30)))
            if not eva:
                continue
            if best_info is None or eva["days_left"] < best_info["days_left"]:
                best_info = eva
                best_doc = doc_type
        if best_info is None:
            rows.append([company_name, name, role, "-", "-", "-", "NO VALID DOCS"])
        else:
            rows.append(
                [
                    company_name,
                    name,
                    role,
                    best_doc,
                    best_info["expiry"],
                    best_info["days_left"],
                    best_info["status"],
                ]
            )
    rows.sort(key=lambda r: r[5] if isinstance(r[5], int) else 99999)
    return rows


# ---------- ANALYTICS AND REMINDER PREVIEW ----------

def build_analytics():
    """
    Compute overall stats and upcoming expiries.
    Returns:
      - analytics_text (str)
      - upcoming_rows (list of rows)
    """
    store = load_store()
    profiles = store.get("profiles", {})
    companies = store.get("companies", {})

    total_profiles = len(profiles)
    total_employees = sum(len(c.get("employees", [])) for c in companies.values())

    status_counts = {"EXPIRED": 0, "NEAR EXPIRY": 0, "OK": 0}
    upcoming: List[Tuple[int, List[Any]]] = []

    # Profiles
    for pname, pdata in profiles.items():
        docs = pdata.get("docs", {})
        for doc_type, info in docs.items():
            eva = evaluate_doc(info.get("expiry", ""), int(info.get("reminder_days", 30)))
            if not eva:
                continue
            status_counts[eva["status"]] += 1
            upcoming.append(
                (
                    eva["days_left"],
                    [
                        "Profile",
                        pname,
                        "-",
                        doc_type,
                        eva["expiry"],
                        eva["days_left"],
                        eva["status"],
                    ],
                )
            )

    # Employees
    for cname, cdata in companies.items():
        employees = cdata.get("employees", [])
        for emp in employees:
            name = emp.get("name", "") or "-"
            docs = emp.get("docs", {})
            for doc_type, info in docs.items():
                eva = evaluate_doc(info.get("expiry", ""), int(info.get("reminder_days", 30)))
                if not eva:
                    continue
                status_counts[eva["status"]] += 1
                upcoming.append(
                    (
                        eva["days_left"],
                        [
                            "Employee",
                            name,
                            cname,
                            doc_type,
                            eva["expiry"],
                            eva["days_left"],
                            eva["status"],
                        ],
                    )
                )

    # Sort upcoming by days_left ascending and keep top 30
    upcoming.sort(key=lambda t: t[0])
    upcoming_rows = [row for _, row in upcoming[:30]]

    today_str = date.today().strftime("%Y-%m-%d")
    lines: List[str] = []
    lines.append(f"Analytics summary (Today: {today_str})")
    lines.append("")
    lines.append(f"Total personal profiles: {total_profiles}")
    lines.append(f"Total employees (all companies): {total_employees}")
    lines.append("")
    lines.append("Document status counts (profiles + employees):")
    lines.append(f"- OK: {status_counts['OK']}")
    lines.append(f"- NEAR EXPIRY (<=30 days): {status_counts['NEAR EXPIRY']}")
    lines.append(f"- EXPIRED: {status_counts['EXPIRED']}")
    lines.append("")
    risk_score = status_counts["EXPIRED"] * 2 + status_counts["NEAR EXPIRY"]
    lines.append(f"Simple risk score (higher is worse): {risk_score}")
    if risk_score == 0:
        lines.append("Risk level: Very low.")
    elif risk_score <= 5:
        lines.append("Risk level: Low.")
    elif risk_score <= 15:
        lines.append("Risk level: Moderate.")
    else:
        lines.append("Risk level: High. Many documents are near expiry or expired.")

    return "\n".join(lines), upcoming_rows


def preview_reminders(as_of_date_str: str, window_days: int):
    """
    Preview which reminders would fire between as_of_date and as_of_date + window_days.
    Return a text explanation and a table of rows.
    """
    if not as_of_date_str:
        as_of_date = date.today()
        as_of_str = as_of_date.strftime("%Y-%m-%d")
    else:
        tmp = parse_date(as_of_date_str)
        if not tmp:
            as_of_date = date.today()
            as_of_str = as_of_date.strftime("%Y-%m-%d")
        else:
            as_of_date = tmp
            as_of_str = as_of_date.strftime("%Y-%m-%d")

    if window_days is None or window_days < 0:
        window_days = 7

    store = load_store()
    profiles = store.get("profiles", {})
    companies = store.get("companies", {})

    rows: List[List[Any]] = []
    lines: List[str] = []
    lines.append(
        f"Reminder preview from {as_of_str} for the next {window_days} days."
    )
    lines.append("A reminder fires when (expiry_date - today) equals reminder_days.")
    lines.append("")

    # Helper to compute days diff from as_of_date instead of today
    def days_from(date_obj: date) -> int:
        return (date_obj - as_of_date).days

    # Profiles
    for pname, pdata in profiles.items():
        docs = pdata.get("docs", {})
        for doc_type, info in docs.items():
            expiry_str = info.get("expiry", "")
            reminder_days = int(info.get("reminder_days", 30))
            expiry_date = parse_date(expiry_str)
            if not expiry_date:
                continue
            dleft = days_from(expiry_date)
            # Only future within window
            if dleft < 0 or dleft > window_days:
                continue
            # Reminder triggers when days_left == reminder_days
            # Here we show both triggered and upcoming inside window
            will_fire = (dleft == reminder_days)
            rows.append(
                [
                    "Profile",
                    pname,
                    "-",
                    doc_type,
                    expiry_str,
                    reminder_days,
                    dleft,
                    "YES" if will_fire else "SOON",
                ]
            )

    # Employees
    for cname, cdata in companies.items():
        employees = cdata.get("employees", [])
        for emp in employees:
            name = emp.get("name", "") or "-"
            docs = emp.get("docs", {})
            for doc_type, info in docs.items():
                expiry_str = info.get("expiry", "")
                reminder_days = int(info.get("reminder_days", 30))
                expiry_date = parse_date(expiry_str)
                if not expiry_date:
                    continue
                dleft = days_from(expiry_date)
                if dleft < 0 or dleft > window_days:
                    continue
                will_fire = (dleft == reminder_days)
                rows.append(
                    [
                        "Employee",
                        name,
                        cname,
                        doc_type,
                        expiry_str,
                        reminder_days,
                        dleft,
                        "YES" if will_fire else "SOON",
                    ]
                )

    if not rows:
        lines.append("No reminders would fire in this window.")
    else:
        lines.append(f"Total items in window: {len(rows)}")

    # Sort rows by days_left ascending
    rows.sort(key=lambda r: r[6])

    return "\n".join(lines), rows


# ---------- PDF GENERATION ----------

def generate_pdf(text: str, filename: str) -> str:
    """
    Generate a simple PDF file from ASCII text.
    Returns the file path.
    """
    if not text:
        text = "No data available."

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    # Ensure we do not pass any non-latin1 characters to FPDF
    safe_lines = []
    for line in text.split("\n"):
        safe_line = line.encode("latin-1", "replace").decode("latin-1")
        safe_lines.append(safe_line)

    for line in safe_lines:
        pdf.multi_cell(0, 8, line)

    output_path = filename
    pdf.output(output_path)
    return output_path


# ---------- UI (GRADIO) ----------

with gr.Blocks(title="Gulf Fines & Expiry Helper") as demo:
    gr.Markdown(
        "# Gulf Fines & Expiry Helper – Demo\n"
        "Track expiries for yourself, your family, and your company staff.\n"
        "This is a local demo running on your PC (no cloud, no login)."
    )

    with gr.Tab("Personal profiles"):
        gr.Markdown(
            "### Personal / family profiles\n"
            "Enter a profile name (for example: Self, Wife, Son, Dad) and expiry dates "
            "in `YYYY-MM-DD` format."
        )

        profile_name_input = gr.Textbox(
            label="Profile name",
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

        save_profile_btn = gr.Button("Save profile and show summary")

        profile_summary_box = gr.Textbox(
            label="Profile summary",
            lines=10,
        )
        profile_pdf_out = gr.File(
            label="Download profile summary PDF"
        )
        profile_overview_table = gr.DataFrame(
            headers=["Profile", "Next document", "Next expiry", "Days left", "Status"],
            label="All profiles overview (soonest expiry first)",
            interactive=False,
        )
        profile_msg = gr.Textbox(
            label="Messages",
            interactive=False,
        )

        save_profile_btn.click(
            fn=save_profile,
            inputs=[
                profile_name_input,
                emirates_id_exp, emirates_id_rem,
                visa_exp, visa_rem,
                license_exp, license_rem,
                passport_exp, passport_rem,
                insurance_exp, insurance_rem,
                tenancy_exp, tenancy_rem,
            ],
            outputs=[
                profile_summary_box,
                profile_pdf_out,
                profile_overview_table,
                profile_msg,
            ],
        )

    with gr.Tab("Company HR dashboard"):
        gr.Markdown(
            "### Company / PRO dashboard\n"
            "Basic HR view for small companies or PROs. Add employees and see upcoming expiries."
        )

        company_name_input = gr.Textbox(
            label="Company name",
            value="My Company",
        )
        employee_name_input = gr.Textbox(
            label="Employee name",
        )
        role_input = gr.Textbox(
            label="Role / position",
        )

        with gr.Row():
            with gr.Column():
                emp_emirates_id_exp = gr.Textbox(
                    label="Emirates ID expiry (YYYY-MM-DD)"
                )
                emp_emirates_id_rem = gr.Textbox(
                    label="Remind me X days before (Emirates ID)",
                    value="30",
                )

                emp_visa_exp = gr.Textbox(
                    label="Visa expiry (YYYY-MM-DD)"
                )
                emp_visa_rem = gr.Textbox(
                    label="Remind me X days before (Visa)",
                    value="30",
                )

                emp_license_exp = gr.Textbox(
                    label="Driving License expiry (YYYY-MM-DD)"
                )
                emp_license_rem = gr.Textbox(
                    label="Remind me X days before (License)",
                    value="30",
                )

            with gr.Column():
                emp_passport_exp = gr.Textbox(
                    label="Passport expiry (YYYY-MM-DD)"
                )
                emp_passport_rem = gr.Textbox(
                    label="Remind me X days before (Passport)",
                    value="60",
                )

                emp_insurance_exp = gr.Textbox(
                    label="Insurance expiry (YYYY-MM-DD)"
                )
                emp_insurance_rem = gr.Textbox(
                    label="Remind me X days before (Insurance)",
                    value="15",
                )

                emp_tenancy_exp = gr.Textbox(
                    label="Tenancy / contract expiry (YYYY-MM-DD)"
                )
                emp_tenancy_rem = gr.Textbox(
                    label="Remind me X days before (Tenancy)",
                    value="30",
                )

        save_employee_btn = gr.Button("Save employee and update company summary")

        company_summary_box = gr.Textbox(
            label="Company summary",
            lines=8,
        )
        company_pdf_out = gr.File(
            label="Download company summary PDF"
        )
        employee_table = gr.DataFrame(
            headers=[
                "Company",
                "Name",
                "Role",
                "Next expiry doc",
                "Next expiry date",
                "Days left",
                "Status",
            ],
            label="Employees overview (soonest expiry first)",
            interactive=False,
        )
        company_msg = gr.Textbox(
            label="Messages",
            interactive=False,
        )

        save_employee_btn.click(
            fn=save_employee,
            inputs=[
                company_name_input,
                employee_name_input,
                role_input,
                emp_emirates_id_exp, emp_emirates_id_rem,
                emp_visa_exp, emp_visa_rem,
                emp_license_exp, emp_license_rem,
                emp_passport_exp, emp_passport_rem,
                emp_insurance_exp, emp_insurance_rem,
                emp_tenancy_exp, emp_tenancy_rem,
            ],
            outputs=[
                company_summary_box,
                company_pdf_out,
                employee_table,
                company_msg,
            ],
        )

    with gr.Tab("Analytics and reminders"):
        gr.Markdown(
            "### Analytics\n"
            "See overall risk level and upcoming expiries across profiles and companies."
        )

        analytics_btn = gr.Button("Recompute analytics")
        analytics_text = gr.Textbox(
            label="Analytics summary",
            lines=10,
            interactive=False,
        )
        upcoming_table = gr.DataFrame(
            headers=[
                "Type",  # Profile / Employee
                "Name",
                "Company",
                "Document",
                "Expiry date",
                "Days left",
                "Status",
            ],
            label="Top upcoming expiries (profiles + employees)",
            interactive=False,
        )

        analytics_btn.click(
            fn=build_analytics,
            inputs=[],
            outputs=[analytics_text, upcoming_table],
        )

        gr.Markdown(
            "### Reminder preview\n"
            "Simulate which reminders would fire around a given date."
        )

        with gr.Row():
            reminder_date_input = gr.Textbox(
                label="Assume today is (YYYY-MM-DD, empty = real today)",
            )
            reminder_window_input = gr.Number(
                label="Look ahead this many days",
                value=7,
                precision=0,
            )

        reminder_btn = gr.Button("Preview reminders")
        reminder_text = gr.Textbox(
            label="Reminder preview summary",
            lines=8,
            interactive=False,
        )
        reminder_table = gr.DataFrame(
            headers=[
                "Type",
                "Name",
                "Company",
                "Document",
                "Expiry date",
                "Reminder days",
                "Days from chosen date",
                "Reminder status",
            ],
            label="Items inside the chosen window",
            interactive=False,
        )

        reminder_btn.click(
            fn=preview_reminders,
            inputs=[reminder_date_input, reminder_window_input],
            outputs=[reminder_text, reminder_table],
        )

if __name__ == "__main__":
    import os

    # If running on Render → PORT exists
    # If running locally → use 7860
    port = int(os.environ.get("PORT", 7860))

    demo.launch(
        server_name="0.0.0.0" if "PORT" in os.environ else "127.0.0.1",
        server_port=port,
        share=False
    )



