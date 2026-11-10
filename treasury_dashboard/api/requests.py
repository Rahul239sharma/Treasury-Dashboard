import frappe
from frappe import _
from frappe.utils import cint

from treasury_dashboard.treasury import details
from treasury_dashboard.treasury import permissions as perms
from treasury_dashboard.treasury.constants import INVOICE_DOCTYPE_FOR, REQUEST_RECEIPT

EDITABLE_FIELDS = (
	"request_type",
	"company",
	"posting_date",
	"party_type",
	"party",
	"against_invoice",
	"mode_of_payment",
	"account",
	"amount",
	"reference_no",
	"reference_date",
	"purpose",
)


@frappe.whitelist()
def get_request_context(company, request_type=REQUEST_RECEIPT):
	perms.assert_dashboard_access()
	perms.assert_company_access(company)

	currency = frappe.get_cached_value("Company", company, "default_currency")
	accounts = frappe.get_all(
		"Account",
		filters={
			"company": company,
			"account_type": ("in", ("Cash", "Bank")),
			"is_group": 0,
			"disabled": 0,
			"account_currency": currency,
		},
		fields=["name", "account_name", "account_type"],
		order_by="account_type desc, account_name asc",
	)
	mode_accounts = dict(
		frappe.get_all(
			"Mode of Payment Account",
			filters={"company": company, "parenttype": "Mode of Payment"},
			fields=["parent", "default_account"],
			as_list=True,
		)
	)
	defaults = frappe.get_cached_value(
		"Company", company, ["default_cash_account", "default_bank_account"], as_dict=True
	)

	return {
		"company": company,
		"currency": currency,
		"accounts": accounts,
		"mode_accounts": mode_accounts,
		"default_cash_account": defaults.default_cash_account,
		"default_bank_account": defaults.default_bank_account,
		"party_types": ["Customer", "Supplier"],
		"default_party_type": "Customer" if request_type == REQUEST_RECEIPT else "Supplier",
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def account_query(doctype, txt, searchfield, start, page_len, filters):
	company = (filters or {}).get("company")
	perms.assert_company_access(company)
	txt = f"%{txt}%"
	return frappe.db.sql(
		"""
		SELECT name, account_type, account_name
		FROM `tabAccount`
		WHERE company = %(company)s AND account_type IN ('Cash', 'Bank')
			AND is_group = 0 AND disabled = 0
			AND (name LIKE %(txt)s OR account_name LIKE %(txt)s)
		ORDER BY account_type DESC, account_name
		LIMIT %(page_len)s OFFSET %(start)s
		""",
		{"company": company, "txt": txt, "start": cint(start), "page_len": cint(page_len)},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def invoice_query(doctype, txt, searchfield, start, page_len, filters):
	filters = filters or {}
	company = filters.get("company")
	perms.assert_company_access(company)

	invoice_doctype = INVOICE_DOCTYPE_FOR.get((filters.get("request_type"), filters.get("party_type")))
	if not invoice_doctype or doctype != invoice_doctype or not filters.get("party"):
		return []

	party_field = "customer" if invoice_doctype == "Sales Invoice" else "supplier"
	return frappe.db.sql(
		f"""
		SELECT name, CONCAT('Outstanding ', FORMAT(outstanding_amount, 2)), posting_date
		FROM `tab{invoice_doctype}`
		WHERE company = %(company)s AND {party_field} = %(party)s AND docstatus = 1
			AND is_return = 0 AND outstanding_amount > 0 AND name LIKE %(txt)s
		ORDER BY posting_date ASC
		LIMIT %(page_len)s OFFSET %(start)s
		""",
		{
			"company": company,
			"party": filters.get("party"),
			"txt": f"%{txt}%",
			"start": cint(start),
			"page_len": cint(page_len),
		},
	)


@frappe.whitelist(methods=["POST"])
def create_request(values, submit=0):
	perms.assert_dashboard_access()
	if not perms.can_create_request():
		frappe.throw(_("Only Treasury Cashiers and Officers can raise requests."), frappe.PermissionError)

	values = frappe.parse_json(values) or {}
	perms.assert_company_access(values.get("company"))

	doc = frappe.new_doc("Treasury Request")
	doc.update({field: values.get(field) for field in EDITABLE_FIELDS if field in values})
	if doc.against_invoice:
		doc.against_doctype = INVOICE_DOCTYPE_FOR.get((doc.request_type, doc.party_type))
	doc.insert()

	if cint(submit):
		doc.submit_for_approval()

	return details.get_detail(doc.doctype, doc.name)


@frappe.whitelist(methods=["POST"])
def submit_request(name):
	doc = _load(name)
	doc.submit_for_approval()
	return details.get_detail(doc.doctype, doc.name)


@frappe.whitelist(methods=["POST"])
def approve_request(name, remarks=None):
	doc = _load(name)
	doc.approve(remarks)
	return details.get_detail(doc.doctype, doc.name)


@frappe.whitelist(methods=["POST"])
def reject_request(name, reason=None):
	doc = _load(name)
	doc.reject(reason)
	return details.get_detail(doc.doctype, doc.name)


@frappe.whitelist(methods=["POST"])
def cancel_request(name, reason=None):
	doc = _load(name)
	doc.cancel_request(reason)
	return details.get_detail(doc.doctype, doc.name)


@frappe.whitelist(methods=["POST"])
def create_payment_entry(name):
	doc = _load(name)
	doc.regenerate_payment_entry()
	return details.get_detail(doc.doctype, doc.name)


def _load(name):
	perms.assert_dashboard_access()
	doc = frappe.get_doc("Treasury Request", name, for_update=True)
	perms.assert_company_access(doc.company)
	doc.check_permission("read")
	return doc
