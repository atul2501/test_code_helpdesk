import frappe
from frappe.model.document import Document

class CustomerManday(Document):

    def validate(self):

        # Validate dates
        if self.contract_start_date > self.contract_end_date:
            frappe.throw(
                "Contract Start Date cannot be greater than Contract End Date"
            )

        # Manday Based contract validation
        if (
            self.contract_type == "Manday Based"
            and float(self.total_manday or 0) <= 0
        ):
            frappe.throw(
                "Total Manday must be greater than 0 for Manday Based contracts"
            )

        # Contract Only contracts should always have 0 mandays
        if self.contract_type == "Contract Only":
            self.total_manday = 0
            self.used_manday = 0
            self.available_manday = 0

        # Get other contracts for the same customer
        contracts = frappe.get_all(
            "Customer Manday",
            filters={
                "customer": self.customer,
                "name": ["!=", self.name]
            },
            fields=[
                "name",
                "contract_type",
                "contract_start_date",
                "contract_end_date"
            ]
        )

        for contract in contracts:

            is_overlap = (
                self.contract_start_date <= contract.contract_end_date
                and self.contract_end_date >= contract.contract_start_date
            )

            if not is_overlap:
                continue

            # Contract Only cannot overlap with any contract
            if (
                self.contract_type == "Contract Only"
                or contract.contract_type == "Contract Only"
            ):
                frappe.throw(
                    f"""
                    Contract period overlaps with existing contract:
                    {contract.name}

                    Contract Only contracts cannot overlap.
                    """
                )

        self.available_manday = max(0,float(self.total_manday or 0) - float(self.used_manday or 0))
