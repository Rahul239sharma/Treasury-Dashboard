"""Unified transaction feed for the treasury grid.

Three sources are merged into one sortable, pageable set:

* Treasury Requests (receipt / payment flows run by this app)
* Payment Entries recorded directly in ERPNext (receipts, payments, internal
  transfers, employee custody advances and custody returns)
* Journal Entries that move money between own accounts (Contra Entry), settle
  employee custody, or are plain Bank/Cash Entries such as WPS payroll transfers

Payment Entries generated from a Treasury Request are not listed on their own;
they appear as the linked document on the request row.
"""

from collections import defaultdict

import frappe
from frappe.utils import cint, flt

from treasury_dashboard.treasury.constants import (
	CAT_ADVANCE,
	CAT_PAYMENT,
	CAT_RECEIPT,
	CAT_SETTLEMENT,
	CAT_TRANSFER,
	CATEGORIES,
	REQUEST_STATUSES,
)

SORTABLE = {
	"posting_date": "t.posting_date {order}, t.creation {order}",
	"amount": "t.amount {order}, t.posting_date DESC",
	"party_name": "t.party_name {order}, t.posting_date DESC",
}

UNION_SQL = f"""
	SELECT 'Treasury Request' AS doctype, tr.name, tr.request_type AS category, tr.posting_date,
		tr.party_type, tr.party, tr.party_name, tr.account, NULL AS counter_account,
		tr.amount, tr.currency, tr.status, tr.mode_of_payment, tr.reference_no, tr.company,
		IF(IFNULL(tr.payment_entry, '') = '', NULL, 'Payment Entry') AS linked_doctype,
		tr.payment_entry AS linked_name, tr.payment_entry_status AS linked_status,
		IF(tr.request_type = 'Receipt', 'in', 'out') AS flow,
		tr.purpose AS remarks, tr.requested_by AS raised_by, tr.creation
	FROM `tabTreasury Request` tr
	WHERE tr.company IN %(companies)s
		AND tr.posting_date BETWEEN %(from_date)s AND %(to_date)s

	UNION ALL

	SELECT 'Payment Entry', pe.name,
		CASE
			WHEN pe.payment_type = 'Internal Transfer' THEN '{CAT_TRANSFER}'
			WHEN pe.party_type = 'Employee' AND pe.payment_type = 'Pay' THEN '{CAT_ADVANCE}'
			WHEN pe.party_type = 'Employee' THEN '{CAT_SETTLEMENT}'
			WHEN pe.payment_type = 'Receive' THEN '{CAT_RECEIPT}'
			ELSE '{CAT_PAYMENT}'
		END,
		pe.posting_date, pe.party_type, pe.party, pe.party_name,
		IF(pe.payment_type = 'Receive', pe.paid_to, pe.paid_from),
		IF(pe.payment_type = 'Internal Transfer', pe.paid_to, NULL),
		IF(pe.payment_type = 'Receive', pe.base_received_amount, pe.base_paid_amount),
		co.default_currency,
		CASE pe.docstatus WHEN 0 THEN 'Draft' WHEN 1 THEN 'Posted' ELSE 'Cancelled' END,
		pe.mode_of_payment, pe.reference_no, pe.company,
		NULL, NULL, NULL,
		CASE pe.payment_type WHEN 'Receive' THEN 'in' WHEN 'Pay' THEN 'out' ELSE 'neutral' END,
		pe.remarks, pe.owner, pe.creation
	FROM `tabPayment Entry` pe
	INNER JOIN `tabCompany` co ON co.name = pe.company
	WHERE pe.company IN %(companies)s
		AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND IFNULL(pe.treasury_request, '') = ''

	UNION ALL

	SELECT 'Journal Entry', je.name,
		CASE
			WHEN je.voucher_type = 'Contra Entry' THEN '{CAT_TRANSFER}'
			WHEN emp.parent IS NOT NULL THEN '{CAT_SETTLEMENT}'
			WHEN money.to_account IS NOT NULL THEN '{CAT_RECEIPT}'
			ELSE '{CAT_PAYMENT}'
		END,
		je.posting_date, emp.party_type, emp.party, COALESCE(e.employee_name, je.title),
		IF(je.voucher_type = 'Contra Entry', money.from_account,
			COALESCE(money.to_account, money.from_account, emp.account)),
		IF(je.voucher_type = 'Contra Entry', money.to_account, NULL),
		je.total_debit, co.default_currency,
		CASE je.docstatus WHEN 0 THEN 'Draft' WHEN 1 THEN 'Posted' ELSE 'Cancelled' END,
		je.mode_of_payment, je.cheque_no, je.company,
		NULL, NULL, NULL,
		CASE
			WHEN je.voucher_type = 'Contra Entry' THEN 'neutral'
			WHEN money.to_account IS NOT NULL THEN 'in'
			WHEN money.from_account IS NOT NULL THEN 'out'
			ELSE 'neutral'
		END,
		je.user_remark, je.owner, je.creation
	FROM `tabJournal Entry` je
	INNER JOIN `tabCompany` co ON co.name = je.company
	LEFT JOIN (
		SELECT parent, MIN(party_type) AS party_type, MIN(party) AS party, MIN(account) AS account
		FROM `tabJournal Entry Account`
		WHERE party_type = 'Employee' AND parenttype = 'Journal Entry'
		GROUP BY parent
	) emp ON emp.parent = je.name
	LEFT JOIN (
		SELECT jea.parent,
			MAX(CASE WHEN jea.credit_in_account_currency > 0 THEN jea.account END) AS from_account,
			MAX(CASE WHEN jea.debit_in_account_currency > 0 THEN jea.account END) AS to_account
		FROM `tabJournal Entry Account` jea
		INNER JOIN `tabAccount` a ON a.name = jea.account
		WHERE a.account_type IN ('Cash', 'Bank') AND jea.parenttype = 'Journal Entry'
		GROUP BY jea.parent
	) money ON money.parent = je.name
	LEFT JOIN `tabEmployee` e ON e.name = emp.party
	WHERE je.company IN %(companies)s
		AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND (
			je.voucher_type = 'Contra Entry'
			OR emp.parent IS NOT NULL
			OR (je.voucher_type IN ('Bank Entry', 'Cash Entry') AND money.parent IS NOT NULL)
		)
"""

EXCLUDED_FROM_TOTALS = ("Rejected", "Cancelled")


def get_transactions(
	companies,
	from_date,
	to_date,
	category=None,
	statuses=None,
	search=None,
	start=0,
	page_length=25,
	sort_by="posting_date",
	sort_order="desc",
):
	if not companies:
		return {"rows": [], "total": 0, "categories": {}, "totals": {}}

	params = {"companies": tuple(companies), "from_date": from_date, "to_date": to_date}
	shared_conditions = _outer_conditions(params, statuses, search)

	category_condition = ""
	if category:
		if category not in CATEGORIES:
			frappe.throw(frappe._("Unknown transaction type {0}").format(category))
		params["category"] = category
		category_condition = "AND t.category = %(category)s"

	order = "ASC" if str(sort_order).lower() == "asc" else "DESC"
	order_by = SORTABLE.get(sort_by, SORTABLE["posting_date"]).format(order=order)
	params["start"] = max(cint(start), 0)
	params["page_length"] = min(max(cint(page_length), 1), 200)

	rows = frappe.db.sql(
		f"""
		SELECT t.* FROM ({UNION_SQL}) t
		WHERE 1 = 1 {shared_conditions} {category_condition}
		ORDER BY {order_by}
		LIMIT %(page_length)s OFFSET %(start)s
		""",
		params,
		as_dict=True,
	)

	summary = frappe.db.sql(
		f"""
		SELECT t.category, t.flow, t.status, t.currency, COUNT(*) AS records, SUM(t.amount) AS amount
		FROM ({UNION_SQL}) t
		WHERE 1 = 1 {shared_conditions}
		GROUP BY t.category, t.flow, t.status, t.currency
		""",
		params,
		as_dict=True,
	)

	counts = dict.fromkeys(CATEGORIES, 0)
	total = 0
	totals = defaultdict(lambda: {"in": 0.0, "out": 0.0, "neutral": 0.0})
	for row in summary:
		counts[row.category] = counts.get(row.category, 0) + row.records
		if category and row.category != category:
			continue
		total += row.records
		if row.status not in EXCLUDED_FROM_TOTALS:
			totals[row.currency][row.flow] += flt(row.amount)

	for row in rows:
		row.amount = flt(row.amount)

	return {
		"rows": rows,
		"total": total,
		"start": params["start"],
		"page_length": params["page_length"],
		"categories": counts,
		"totals": dict(totals),
	}


def _outer_conditions(params, statuses, search):
	conditions = []

	if statuses:
		if isinstance(statuses, str):
			statuses = [statuses]
		valid = set(REQUEST_STATUSES)
		statuses = [s for s in statuses if s in valid]
		if statuses:
			params["statuses"] = tuple(statuses)
			conditions.append("AND t.status IN %(statuses)s")

	search = (search or "").strip()
	if search:
		params["search"] = f"%{search}%"
		conditions.append(
			"""AND (t.name LIKE %(search)s OR t.party LIKE %(search)s OR t.party_name LIKE %(search)s
			OR t.reference_no LIKE %(search)s OR t.remarks LIKE %(search)s OR t.account LIKE %(search)s
			OR t.linked_name LIKE %(search)s)"""
		)

	return "\n".join(conditions)
