result = []

today = frappe.utils.nowdate()

salary_slips = frappe.db.get_all(
    "Salary Slip",
    filters={"docstatus": 1},
    fields=["employee", "employee_name", "net_pay"]
)

for slip in salary_slips:

    emp = frappe.db.get_value(
        "Employee",
        slip.employee,
        ["bank_ac_no", "ifsc_code"],
        as_dict=True
    )

    bank_no = (emp.bank_ac_no or "").replace(" ", "") if emp else ""
    ifsc = (emp.ifsc_code or "") if emp else ""

    flag_line = "I,1," if ifsc[:4].upper() == "HDFC" else "N,2,"

    export_line = (
        flag_line
        + bank_no
        + ","
        + str(slip.net_pay or 0)
        + ","
        + (slip.employee_name or "")
        + ",,,,,,,,,Salary,,,,,,,,,"
        + today
        + ",,"
        + ifsc
        + ",,,"
    )

    result.append({
        "bank_ac_no": bank_no,
        "net_pay": slip.net_pay,
        "employee_name": slip.employee_name,
        "ifsc_code": ifsc,
        "export_line": export_line
    })
