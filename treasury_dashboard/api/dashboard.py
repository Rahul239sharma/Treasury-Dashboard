import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

from treasury_dashboard.treasury import details, kpis, transactions
from treasury_dashboard.treasury import permissions as perms
from treasury_dashboard.treasury.constants import (
	CAT_ADVANCE,
	CAT_PAYMENT,
	CAT_RECEIPT,
	CAT_SETTLEMENT,
	CAT_TRANSFER,
	REALTIME_EVENT,
	REQUEST_STATUSES,
)

MAX_RANGE_DAYS = 731

CATEGORY_INFO = [
	{
		"category": CAT_RECEIPT,
		"workflow": True,
		"description": "Fee collections and other money received, with approval before posting.",
	},
	{
		"category": CAT_PAYMENT,
		"workflow": True,
		"description": "Supplier payments and refunds, with approval before posting.",
	},
	{
		"category": CAT_TRANSFER,
		"workflow": False,
		"description": "Cash deposits and transfers between the school's own cash and bank accounts.",
		"standard": {"doctype": "Payment Entry", "values": {"payment_type": "Internal Transfer"}},
	},
	{
		"category": CAT_ADVANCE,
		"workflow": False,
		"description": "Cash custody and advances handed to staff.",
		"standard": {"doctype": "Payment Entry", "values": {"payment_type": "Pay", "party_type": "Employee"}},
	},
	{
		"category": CAT_SETTLEMENT,
		"workflow": False,
		"description": "Custody returns and expense settlements against staff custody.",
		"standard": {"doctype": "Journal Entry", "values": {"voucher_type": "Journal Entry"}},
	},
]


@frappe.whitelist()
def get_bootstrap():
	perms.assert_dashboard_access()
	companies = perms.get_permitted_companies()
	names = [c.name for c in companies]

	default_company = frappe.defaults.get_user_default("Company")
	if default_company not in names:
		leaves = [c.name for c in companies if not c.is_group]
		default_company = leaves[0] if len(leaves) == 1 else None

	return {
		"user": {"name": frappe.session.user, "full_name": frappe.utils.get_fullname()},
		"companies": [
			{
				"name": c.name,
				"abbr": c.abbr,
				"currency": c.default_currency,
				"is_group": c.is_group,
				"parent_company": c.parent_company,
			}
			for c in companies
		],
		"default_company": default_company,
		"capabilities": perms.get_capabilities(),
		"categories": [{**info, "description": _(info["description"])} for info in CATEGORY_INFO],
		"statuses": REQUEST_STATUSES,
		"modes_of_payment": frappe.get_all(
			"Mode of Payment", filters={"enabled": 1}, fields=["name", "type"], order_by="name"
		),
		"default_range": {"from_date": str(get_first_day(nowdate())), "to_date": nowdate()},
		"realtime_event": REALTIME_EVENT,
	}


@frappe.whitelist()
def get_dashboard(
	company=None,
	from_date=None,
	to_date=None,
	category=None,
	statuses=None,
	search=None,
	start=0,
	page_length=25,
	sort_by=None,
	sort_order=None,
):
	perms.assert_dashboard_access()
	companies = perms.resolve_companies(company)
	from_date, to_date = _date_range(from_date, to_date)

	return {
		"kpis": kpis.get_kpis(companies, from_date, to_date),
		"transactions": transactions.get_transactions(
			companies,
			from_date,
			to_date,
			category=category or None,
			statuses=frappe.parse_json(statuses) if statuses else None,
			search=search,
			start=start,
			page_length=page_length,
			sort_by=sort_by or "posting_date",
			sort_order=sort_order or "desc",
		),
	}


@frappe.whitelist()
def get_kpis(company=None, from_date=None, to_date=None):
	perms.assert_dashboard_access()
	from_date, to_date = _date_range(from_date, to_date)
	return kpis.get_kpis(perms.resolve_companies(company), from_date, to_date)


@frappe.whitelist()
def get_transactions(
	company=None,
	from_date=None,
	to_date=None,
	category=None,
	statuses=None,
	search=None,
	start=0,
	page_length=25,
	sort_by=None,
	sort_order=None,
):
	perms.assert_dashboard_access()
	from_date, to_date = _date_range(from_date, to_date)
	return transactions.get_transactions(
		perms.resolve_companies(company),
		from_date,
		to_date,
		category=category or None,
		statuses=frappe.parse_json(statuses) if statuses else None,
		search=search,
		start=start,
		page_length=page_length,
		sort_by=sort_by or "posting_date",
		sort_order=sort_order or "desc",
	)


@frappe.whitelist()
def get_transaction_detail(doctype, name):
	perms.assert_dashboard_access()
	return details.get_detail(doctype, name)


def _date_range(from_date, to_date):
	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or get_first_day(to_date))
	if from_date > to_date:
		frappe.throw(_("From date cannot be after to date."))
	if (to_date - from_date).days > MAX_RANGE_DAYS:
		frappe.throw(_("Please choose a range of two years or less."))
	return from_date, to_date
