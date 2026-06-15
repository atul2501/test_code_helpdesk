import frappe
from frappe.utils import getdate


def get_customer_from_email(email):

    if not email:
        return None

    contact = frappe.db.get_value(
        "Contact Email",
        {
            "email_id": email
        },
        "parent"
    )

    if not contact:
        return None

    customer = frappe.db.get_value(
        "Dynamic Link",
        {
            "parent": contact,
            "link_doctype": "Customer"
        },
        "link_name"
    )

    return customer


def get_active_contract(customer):

    today = getdate()

    contracts = frappe.get_all(
        "Customer Manday",
        filters={
            "customer": customer,
            "contract_start_date": ["<=", today],
            "contract_end_date": [">=", today],
            "active_contract" : 1
        },
        fields=[
            "name",
            "customer",#
            "total_manday",#
            "used_manday", #
            "pending_manday", #
            "available_manday", #
            "contract_start_date",#
            "contract_end_date",#
            "active_contract",#
            "contract_type"#
        ]
    )

    if len(contracts) > 1:
        frappe.throw(
            f"Multiple active contracts found for customer {customer}"
        )

    if not contracts:
        return None

    return contracts[0]


def validate_contract(contract):

    if not contract:

        frappe.throw(
            "No active contract found"
        )

    today = getdate()

    start_date = contract.contract_start_date
    end_date = contract.contract_end_date

    if start_date:

        start_date = getdate(start_date)

        if today < start_date:

            frappe.throw(
                "Contract has not started yet"
            )

    if end_date:

        end_date = getdate(end_date)

        if today > end_date:

            frappe.db.set_value(
                "Customer Manday",
                contract.name,
                "active_contract",
                0,
                update_modified=False
            )

            update_all_customer_tickets(
                contract.customer
            )

            frappe.throw(
                "Contract expired"
            )


def calculate_used_manday(customer, contract):

    result = frappe.db.sql(
        """
        SELECT
            COALESCE(SUM(custom_this_project_manday), 0)
        FROM
            `tabHD Ticket`
        WHERE
            custom_customers = %s
            AND custom_manday_status = 'Approved'
            AND docstatus < 2
            AND DATE(creation) >= %s
            AND DATE(creation) <= %s
        """,
        (
            customer,
            contract.contract_start_date,
            contract.contract_end_date
        )
    )

    return float(result[0][0] or 0)


def recalculate_customer_manday(customer):

    contract = get_active_contract(customer)

    if not contract:
        return None

    total = float(
        contract.total_manday or 0
    )

    used = calculate_used_manday(
        customer,
        contract
    )

    available = total - used

    if available < 0:
        available = 0

    frappe.db.set_value(
        "Customer Manday",
        contract.name,
        {
            "used_manday": used,
            "available_manday": available
        },
        update_modified=False
    )

    return {
        "name": contract.name,
        "total": total,
        "used": used,
        "available": available,
        "start_date": contract.contract_start_date,
        "end_date": contract.contract_end_date,
        "active_contract": contract.active_contract,
        "contract_type": contract.contract_type
    }


def update_all_customer_tickets(customer):

    data = recalculate_customer_manday(
        customer
    )

    # No active contract
    if not data:

        frappe.db.sql(
            """
            UPDATE `tabHD Ticket`
            SET
                custom_available_manday = 0,
                custom__active_contract = 0,
                custom_contract_start_date = NULL,
                custom_contract_end_date = NULL,
                custom_contract_type = NULL
            WHERE
                custom_customers = %s
                AND docstatus < 2
            """,
            (customer,)
        )

        return

    frappe.db.sql(
        """
        UPDATE `tabHD Ticket`
        SET
            custom_used_manday = %s,
            custom_available_manday = %s,
            custom_contract_start_date = %s,
            custom_contract_end_date = %s,
            custom__active_contract = %s,
            custom_contract_type = %s
        WHERE
            custom_customers = %s
            AND docstatus < 2
        """,
        (
            data["used"],
            data["available"],
            data["start_date"],
            data["end_date"],
            data["active_contract"],
            data["contract_type"],
            customer
        )
    )


def update_contract_status():

    today = getdate()

    contracts = frappe.get_all(
        "Customer Manday",
        fields=[
            "name",
            "customer",
            "contract_start_date",
            "contract_end_date",
            "active_contract"
        ]
    )

    updated_customers = set()

    for contract in contracts:

        active = 0

        if contract.contract_start_date and contract.contract_end_date:

            start_date = getdate(contract.contract_start_date)
            end_date = getdate(contract.contract_end_date)

            active = 1 if start_date <= today <= end_date else 0

        if active != int(contract.active_contract or 0):

            frappe.db.set_value(
                "Customer Manday",
                contract.name,
                "active_contract",
                active,
                update_modified=False
            )

            updated_customers.add(contract.customer)

    for customer in updated_customers:
        update_all_customer_tickets(customer)

    frappe.db.commit()



def create_manday_history(customer,ticket,contract,manday,action,remarks=None):

    history = frappe.new_doc(
        "Manday History"
    )

    history.customer = customer
    history.ticket = ticket
    history.contract = contract
    history.manday = manday
    history.action = action
    history.action_date = frappe.utils.now()

    if remarks:
        history.remarks = remarks

    history.insert(
        ignore_permissions=True
    )
