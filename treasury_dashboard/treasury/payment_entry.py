"""Bridge between Treasury Requests and standard ERPNext Payment Entries.

Entries are always created as drafts; posting (submit) stays with accounts staff in
the native Payment Entry form. The hooks below keep the request in step with whatever
happens to its entry afterwards.
"""

import frappe
from erpnext.accounts.party import get_party_account
from frappe import _
from frappe.utils import flt

from treasury_dashboard.treasury.audit import log_action
from treasury_dashboard.treasury.constants import (
	APPROVED,
	PAYMENT_TYPE_FOR_REQUEST,
	POSTED,
	REQUEST_RECEIPT,
)
from treasury_dashboard.treasury.errors import DuplicatePaymentEntryError


def get_live_payment_entries(request_name, exclude=None):
	filters = {"treasury_request": request_name, "docstatus": ("<", 2)}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.get_all("Payment Entry", filters=filters, pluck="name")


def create_draft_payment_entry(request):
	existing = get_live_payment_entries(request.name)
	if existing:
		frappe.throw(
			_("{0} already has Payment Entry {1}.").format(request.name, frappe.bold(existing[0])),
			DuplicatePaymentEntryError,
		)

	payment_type = PAYMENT_TYPE_FOR_REQUEST[request.request_type]
	is_receipt = request.request_type == REQUEST_RECEIPT
	party_account = get_party_account(request.party_type, request.party, request.company)

	entry = frappe.new_doc("Payment Entry")
	entry.update(
		{
			"payment_type": payment_type,
			"company": request.company,
			"posting_date": request.posting_date,
			"mode_of_payment": request.mode_of_payment,
			"party_type": request.party_type,
			"party": request.party,
			"party_name": request.party_name,
			"paid_from": party_account if is_receipt else request.account,
			"paid_to": request.account if is_receipt else party_account,
			"paid_amount": request.amount,
			"received_amount": request.amount,
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
			"reference_no": request.reference_no,
			"reference_date": request.reference_date or request.posting_date,
			"bank_account": _company_bank_account(request.account, request.company),
			"treasury_request": request.name,
			"custom_remarks": 1,
			"remarks": _remarks_for(request),
		}
	)

	if request.against_invoice:
		invoice = frappe.db.get_value(
			request.against_doctype,
			request.against_invoice,
			["grand_total", "rounded_total", "outstanding_amount", "due_date"],
			as_dict=True,
		)
		entry.append(
			"references",
			{
				"reference_doctype": request.against_doctype,
				"reference_name": request.against_invoice,
				"due_date": invoice.due_date,
				"total_amount": invoice.rounded_total or invoice.grand_total,
				"outstanding_amount": invoice.outstanding_amount,
				"allocated_amount": request.amount,
			},
		)

	entry.setup_party_account_field()
	entry.set_missing_values()
	entry.flags.ignore_permissions = True
	entry.insert()

	entry.add_comment(
		"Info",
		_("Created from Treasury Request {0}, approved by {1}.").format(
			frappe.utils.get_link_to_form("Treasury Request", request.name),
			frappe.utils.get_fullname(request.approved_by),
		),
	)
	return entry


def _company_bank_account(account, company):
	return frappe.db.get_value(
		"Bank Account",
		{"account": account, "company": company, "is_company_account": 1, "disabled": 0},
		"name",
	)


def _remarks_for(request):
	lines = [
		_("{0} via Treasury Request {1}").format(_(request.request_type), request.name),
		request.purpose,
	]
	if request.approved_by:
		lines.append(_("Approved by {0}").format(frappe.utils.get_fullname(request.approved_by)))
	return "\n".join(lines)


# ---------------------------------------------------------------- doc events


def validate_linked_payment_entry(doc, method=None):
	if not doc.get("treasury_request"):
		return

	request = frappe.db.get_value(
		"Treasury Request",
		doc.treasury_request,
		["name", "status", "company", "request_type", "party_type", "party", "amount", "account"],
		as_dict=True,
	)
	if not request:
		frappe.throw(_("Treasury Request {0} does not exist.").format(doc.treasury_request))

	if request.status not in (APPROVED, POSTED):
		frappe.throw(
			_("Treasury Request {0} is {1}; only approved requests can be posted.").format(
				request.name, _(request.status)
			)
		)

	others = get_live_payment_entries(request.name, exclude=doc.name)
	if others:
		frappe.throw(
			_("Treasury Request {0} is already linked to Payment Entry {1}.").format(
				request.name, frappe.bold(others[0])
			),
			DuplicatePaymentEntryError,
		)

	is_receipt = request.request_type == REQUEST_RECEIPT
	actual = {
		_("Company"): doc.company,
		_("Payment Type"): doc.payment_type,
		_("Party Type"): doc.party_type,
		_("Party"): doc.party,
		_("Amount"): flt(doc.received_amount if is_receipt else doc.paid_amount, 2),
		_("Cash / Bank Account"): doc.paid_to if is_receipt else doc.paid_from,
	}
	approved = {
		_("Company"): request.company,
		_("Payment Type"): PAYMENT_TYPE_FOR_REQUEST[request.request_type],
		_("Party Type"): request.party_type,
		_("Party"): request.party,
		_("Amount"): flt(request.amount, 2),
		_("Cash / Bank Account"): request.account,
	}
	changed = [label for label, value in approved.items() if actual[label] != value]
	if changed:
		frappe.throw(
			_("This entry no longer matches approved Treasury Request {0}. Changed: {1}.").format(
				request.name, ", ".join(changed)
			)
		)


def on_payment_entry_submit(doc, method=None):
	request = _linked_request(doc)
	if not request:
		return
	request.apply_system_status(
		POSTED,
		_("Payment Entry Submitted"),
		values={"payment_entry": doc.name, "payment_entry_status": "Submitted"},
		linked_name=doc.name,
	)


def on_payment_entry_cancel(doc, method=None):
	request = _linked_request(doc)
	if not request:
		return
	request.apply_system_status(
		APPROVED,
		_("Payment Entry Cancelled"),
		values={"payment_entry_status": "Cancelled"},
		linked_name=doc.name,
	)


def on_payment_entry_trash(doc, method=None):
	if frappe.flags.get("treasury_skip_pe_sync"):
		return

	request = _linked_request(doc)
	if not request or request.payment_entry != doc.name:
		return

	request.db_set({"payment_entry": None, "payment_entry_status": None})
	log_action(
		request,
		_("Payment Entry Deleted"),
		remarks=_("Draft {0} was deleted").format(doc.name),
		linked_doctype="Payment Entry",
		linked_name=doc.name,
	)


def _linked_request(doc):
	if not doc.get("treasury_request"):
		return None
	if not frappe.db.exists("Treasury Request", doc.treasury_request):
		return None
	return frappe.get_doc("Treasury Request", doc.treasury_request, for_update=True)
