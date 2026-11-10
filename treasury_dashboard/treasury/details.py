import frappe
from frappe import _
from frappe.utils import flt, get_fullname

from treasury_dashboard.treasury import permissions as perms
from treasury_dashboard.treasury.audit import get_trail
from treasury_dashboard.treasury.constants import (
	CAT_ADVANCE,
	CAT_PAYMENT,
	CAT_RECEIPT,
	CAT_SETTLEMENT,
	CAT_TRANSFER,
	WORKFLOW_CATEGORIES,
)

SUPPORTED = ("Treasury Request", "Payment Entry", "Journal Entry")


def get_detail(doctype, name):
	if doctype not in SUPPORTED:
		frappe.throw(_("{0} is not a treasury document.").format(doctype))

	doc = frappe.get_doc(doctype, name)
	perms.assert_company_access(doc.company)
	if not frappe.has_permission(doctype, "read", doc):
		frappe.throw(_("You are not permitted to view {0}.").format(name), frappe.PermissionError)

	builder = {
		"Treasury Request": _request_detail,
		"Payment Entry": _payment_entry_detail,
		"Journal Entry": _journal_entry_detail,
	}[doctype]
	detail = builder(doc)
	detail.update(
		{
			"doctype": doctype,
			"name": doc.name,
			"company": doc.company,
			"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
			"route": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{doc.name}",
			"trail": _trail_with_names(doctype, doc.name),
		}
	)
	return detail


def _request_detail(doc):
	linked = []
	if doc.payment_entry:
		pe = frappe.db.get_value(
			"Payment Entry",
			doc.payment_entry,
			["name", "docstatus", "posting_date", "paid_amount", "received_amount"],
			as_dict=True,
		)
		if pe:
			linked.append(
				{
					"doctype": "Payment Entry",
					"name": pe.name,
					"status": _docstatus_label(pe.docstatus),
					"posting_date": pe.posting_date,
					"amount": flt(pe.received_amount or pe.paid_amount),
				}
			)
	if doc.against_invoice:
		invoice = frappe.db.get_value(
			doc.against_doctype,
			doc.against_invoice,
			["name", "posting_date", "grand_total", "outstanding_amount", "status"],
			as_dict=True,
		)
		if invoice:
			linked.append(
				{
					"doctype": doc.against_doctype,
					"name": invoice.name,
					"status": invoice.status,
					"posting_date": invoice.posting_date,
					"amount": flt(invoice.grand_total),
					"outstanding": flt(invoice.outstanding_amount),
				}
			)

	return {
		"title": doc.party_name,
		"category": doc.request_type,
		"status": doc.status,
		"workflow": "treasury",
		"amount": flt(doc.amount),
		"flow": "in" if doc.request_type == CAT_RECEIPT else "out",
		"posting_date": doc.posting_date,
		"fields": _fields(
			(_("School"), doc.company),
			(_("Party"), f"{doc.party_name} ({_(doc.party_type)})"),
			(_("Mode of Payment"), doc.mode_of_payment),
			(_("Received Into") if doc.request_type == CAT_RECEIPT else _("Paid From"), doc.account),
			(_("Cheque / Reference"), _join(doc.reference_no, frappe.format(doc.reference_date, "Date"))),
			(_("Purpose"), doc.purpose),
			(_("Requested By"), get_fullname(doc.requested_by)),
			(_("Approved By"), doc.approved_by and get_fullname(doc.approved_by)),
			(_("Approval Remarks"), doc.approval_remarks),
			(_("Rejected By"), doc.rejected_by and get_fullname(doc.rejected_by)),
			(_("Rejection Reason"), doc.rejection_reason),
			(_("Cancelled By"), doc.cancelled_by and get_fullname(doc.cancelled_by)),
			(_("Cancellation Reason"), doc.cancellation_reason),
		),
		"linked": linked,
		"actions": doc.get_allowed_actions(),
		"requested_by": doc.requested_by,
		"is_own_request": doc.requested_by == frappe.session.user,
	}


def _payment_entry_detail(doc):
	if doc.payment_type == "Internal Transfer":
		category = CAT_TRANSFER
	elif doc.party_type == "Employee":
		category = CAT_ADVANCE if doc.payment_type == "Pay" else CAT_SETTLEMENT
	else:
		category = CAT_RECEIPT if doc.payment_type == "Receive" else CAT_PAYMENT

	linked = [
		{
			"doctype": ref.reference_doctype,
			"name": ref.reference_name,
			"amount": flt(ref.allocated_amount),
			"outstanding": flt(ref.outstanding_amount),
		}
		for ref in doc.references
	]
	if doc.get("treasury_request"):
		linked.insert(0, {"doctype": "Treasury Request", "name": doc.treasury_request})

	amount = doc.base_received_amount if doc.payment_type == "Receive" else doc.base_paid_amount
	return {
		"title": doc.party_name or _("{0} to {1}").format(doc.paid_from, doc.paid_to),
		"category": category,
		"status": _docstatus_label(doc.docstatus),
		"workflow": _workflow_note(category, doc.get("treasury_request")),
		"amount": flt(amount),
		"flow": {"Receive": "in", "Pay": "out"}.get(doc.payment_type, "neutral"),
		"posting_date": doc.posting_date,
		"fields": _fields(
			(_("School"), doc.company),
			(_("Payment Type"), _(doc.payment_type)),
			(_("Party"), doc.party and f"{doc.party_name} ({_(doc.party_type)})"),
			(_("Mode of Payment"), doc.mode_of_payment),
			(_("Paid From"), doc.paid_from),
			(_("Paid To"), doc.paid_to),
			(_("Cheque / Reference"), _join(doc.reference_no, frappe.format(doc.reference_date, "Date"))),
			(_("Remarks"), doc.remarks),
			(_("Recorded By"), get_fullname(doc.owner)),
		),
		"linked": linked,
		"ledger": _ledger(doc),
		"actions": [],
	}


def _journal_entry_detail(doc):
	cash_accounts = {
		row.account
		for row in doc.accounts
		if frappe.get_cached_value("Account", row.account, "account_type") in ("Cash", "Bank")
	}
	money_in = any(row.debit and row.account in cash_accounts for row in doc.accounts)
	money_out = any(row.credit and row.account in cash_accounts for row in doc.accounts)

	if doc.voucher_type == "Contra Entry":
		category, flow = CAT_TRANSFER, "neutral"
	elif any(row.party_type == "Employee" for row in doc.accounts):
		category, flow = CAT_SETTLEMENT, "in" if money_in else "neutral"
	elif money_in:
		category, flow = CAT_RECEIPT, "in"
	else:
		category, flow = CAT_PAYMENT, "out" if money_out else "neutral"

	return {
		"title": doc.title or doc.name,
		"category": category,
		"status": _docstatus_label(doc.docstatus),
		"workflow": _workflow_note(category),
		"amount": flt(doc.total_debit),
		"flow": flow,
		"posting_date": doc.posting_date,
		"fields": _fields(
			(_("School"), doc.company),
			(_("Entry Type"), _(doc.voucher_type)),
			(_("Cheque / Reference"), _join(doc.cheque_no, frappe.format(doc.cheque_date, "Date"))),
			(_("Remarks"), doc.user_remark),
			(_("Recorded By"), get_fullname(doc.owner)),
		),
		"lines": [
			{
				"account": row.account,
				"party": row.party,
				"debit": flt(row.debit),
				"credit": flt(row.credit),
			}
			for row in doc.accounts
		],
		"linked": [],
		"ledger": _ledger(doc),
		"actions": [],
	}


def _workflow_note(category, treasury_request=None):
	if treasury_request:
		return "treasury"
	if category in WORKFLOW_CATEGORIES:
		return "standard"
	return "erpnext"


def _ledger(doc):
	if doc.docstatus != 1:
		return []
	return frappe.get_all(
		"GL Entry",
		filters={"voucher_type": doc.doctype, "voucher_no": doc.name, "is_cancelled": 0},
		fields=["account", "party", "debit", "credit"],
		order_by="debit desc",
	)


def _trail_with_names(doctype, name):
	trail = get_trail(doctype, name)
	for row in trail:
		row["user_fullname"] = get_fullname(row.user)
	return trail


def _docstatus_label(docstatus):
	return {0: "Draft", 1: "Posted", 2: "Cancelled"}.get(docstatus, "Draft")


def _fields(*pairs):
	return [{"label": label, "value": value} for label, value in pairs if value not in (None, "")]


def _join(*parts):
	return " · ".join(str(p) for p in parts if p) or None
