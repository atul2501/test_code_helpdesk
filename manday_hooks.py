import frappe
from frappe.utils import getdate

from helpdesk.api.manday import (
    get_customer_from_email,
    get_active_contract,
    validate_contract,
    recalculate_customer_manday,
    update_all_customer_tickets,
    create_manday_history
)



def hd_ticket_before_save(doc, method):

    if not doc.custom_customers:

        customer = None

        if doc.raised_by:

            customer = get_customer_from_email(
                doc.raised_by
            )

        if not customer and frappe.session.user:

            customer = get_customer_from_email(
                frappe.session.user
            )

        if customer:

            doc.custom_customers = customer

    if not doc.custom_customers:

        frappe.throw(
            f"""
            Customer required

            Raised By: {doc.raised_by}

            Session User: {frappe.session.user}
            """
        )

    # customer = doc.custom_customers

    # contract = get_active_contract(
    #     customer
    # )

    # validate_contract(contract)

    # data = recalculate_customer_manday(
    #     customer
    # )
    customer = doc.custom_customers

    contract = get_active_contract(
        customer
    )

    validate_contract(contract)

    old_doc = doc.get_doc_before_save()

    # need_recalculate = doc.is_new()

    # if old_doc:
    #     if old_doc.custom_manday_status != doc.custom_manday_status:
    #         need_recalculate = True
    need_recalculate = doc.is_new()

    if old_doc:

        if old_doc.custom_manday_status != doc.custom_manday_status:
            need_recalculate = True

        elif float(
            old_doc.custom_this_project_manday or 0
        ) != float(
            doc.custom_this_project_manday or 0
        ):
            need_recalculate = True

    if need_recalculate:

        data = recalculate_customer_manday(
            customer
        )

    else:

        data = {
            "used": float(contract.used_manday or 0),
            "available": float(contract.available_manday or 0),
            "start_date": contract.contract_start_date,
            "end_date": contract.contract_end_date,
            "active_contract": contract.active_contract,
            "contract_type": contract.contract_type
        }

    if not data:

        frappe.throw(
            "No active contract found"
        )

    requested = float(
        doc.custom_this_project_manday or 0
    )

    available = float(
         data["available"] or 0
    )

    if (
        doc.is_new()
        and data["contract_type"] == "Manday Based"
        and available <= 0
    ):
        frappe.throw(
            "All allocated mandays have been consumed. Please renew the contract before creating a new ticket."
        )    

    # old_doc = doc.get_doc_before_save()


    old_manday_status = None
    
    if old_doc:
        
        old_manday_status = old_doc.custom_manday_status

        if (
            old_doc.custom_manday_status == "Approved"
            and float(
                old_doc.custom_this_project_manday or 0
            ) != float(
                doc.custom_this_project_manday or 0
            )
        ):

            frappe.throw(
                "Cannot change manday after approval"
            )

    if (
        doc.custom_manday_status == "Approved"
        and (
            not old_doc
            or old_manday_status != "Approved"
            )
        ):
        if data["contract_type"] == "Manday Based":

            if requested <= 0:
                frappe.throw(
                    "Project Manday must be greater than 0 for Manday Based contracts"
                )

            if requested > available:

                frappe.throw(
                    f"""
                    Not enough manday

                    Available: {available}

                    Requested: {requested}
                    """
                )


        doc.custom_manday_status = "Approved"
        
        create_manday_history(
            customer=customer,
            ticket=doc.name or None,
            contract=contract.name,
            manday=requested,
            action="Approved",
            remarks=f"Ticket consumed {requested} manday"
        )

    elif doc.custom_manday_status == "Rejected":

        doc.custom_manday_status = "Rejected"

    else:

        doc.custom_manday_status = "Draft"

    doc.custom_used_manday = (
        data["used"]
    )

    doc.custom_available_manday = (
        data["available"]
    )

    doc.custom_contract_start_date = (
        data["start_date"]
    )

    doc.custom_contract_end_date = (
        data["end_date"]
    )

    doc.custom__active_contract = (
        data["active_contract"]
    )

    doc.custom_contract_type = (
        data["contract_type"]
    )


def manday_transaction_after_submit(doc, method):

    customer = doc.customer

    if not customer:

        frappe.throw(
            "Customer required"
        )

    new_manday = float(
        doc.manday or 0
    )

    if (
        doc.contract_type == "Manday Based"
        and float(doc.manday or 0) <= 0
    ):
        frappe.throw(
            "Manday must be greater than 0 for Manday Based contracts"
        )

    contract = frappe.db.get_value(
        "Customer Manday",
        {
            "customer": customer,
            "contract_start_date": doc.contract_start_date,
            "contract_end_date": doc.contract_end_date
        },
        [
            "name",
            "total_manday",
            "used_manday"
        ],
        as_dict=True
    )

    today = getdate()

    active_contract = 0

    if (
        doc.contract_start_date
        and doc.contract_end_date
    ):

        start_date = getdate(
            doc.contract_start_date
        )

        end_date = getdate(
            doc.contract_end_date
        )

        if start_date <= today <= end_date:

            active_contract = 1

    if contract:

        total = float(
            contract["total_manday"] or 0
        )

        used = float(
            contract["used_manday"] or 0
        )

        if doc.contract_type == "Manday Based":

            total += new_manday
            available = total - used

        else:

            total = 0
            available = 0

        frappe.db.set_value(
            "Customer Manday",
            contract["name"],
            {
                "total_manday": total,
                "available_manday": available,
                "active_contract": active_contract,
                "contract_type": doc.contract_type
            }
        )

    else:

        new_doc = frappe.new_doc(
            "Customer Manday"
        )

#

        new_doc.customer = customer

        if doc.contract_type == "Contract Only":

            new_doc.total_manday = 0
            new_doc.used_manday = 0
            new_doc.pending_manday = 0
            new_doc.available_manday = 0

        else:

            new_doc.total_manday = new_manday
            new_doc.used_manday = 0
            new_doc.pending_manday = 0
            new_doc.available_manday = new_manday

        new_doc.contract_start_date = doc.contract_start_date
        new_doc.contract_end_date = doc.contract_end_date
        new_doc.active_contract = active_contract
        new_doc.contract_type = doc.contract_type


        new_doc.insert(ignore_permissions=True)

        frappe.msgprint(f"Created Contract: {new_doc.name}")

    # Create history for both existing and new contracts
    contract_name = (
        contract["name"]
        if contract
        else new_doc.name
    )

    create_manday_history(
        customer=customer,
        ticket=None,
        contract=contract_name,
        manday=new_manday,
        action="Contract Created",
        remarks=f"{new_manday} manday allocated"
    )

    update_all_customer_tickets(
        customer
    )



def hd_ticket_on_update(doc, method):

    if not doc.custom_customers:
        return

    old_doc = doc.get_doc_before_save()

    if not old_doc:
        return

    # Only trigger when manday status changes
    if old_doc.custom_manday_status != doc.custom_manday_status:
        update_all_customer_tickets(
            doc.custom_customers
        )


from frappe.utils import getdate


def manday_transaction_before_submit(doc, method):

    contracts = frappe.get_all(
        "Customer Manday",
        filters={
            "customer": doc.customer
        },
        fields=[
            "name",
            "contract_type",
            "contract_start_date",
            "contract_end_date"
        ]
    )

    doc_start = getdate(doc.contract_start_date)
    doc_end = getdate(doc.contract_end_date)

    for contract in contracts:

        contract_start = getdate(
            contract.contract_start_date
        )

        contract_end = getdate(
            contract.contract_end_date
        )

        is_overlap = (
            doc_start <= contract_end
            and doc_end >= contract_start
        )

        if not is_overlap:
            continue

        if contract.contract_type == "Contract Only":

            frappe.throw(
                f"""
                Cannot create Manday Transaction.

                Contract Only already exists:

                {contract.name}

                Period:
                {contract.contract_start_date}
                to
                {contract.contract_end_date}
                """
            )
