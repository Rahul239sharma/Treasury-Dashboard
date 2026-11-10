"""Headline treasury figures, computed from posted GL entries.

Cash and bank balances are closing balances as at the end of the selected period.
Receipts and payments are money that actually moved into or out of cash/bank
ledgers inside the period. Transfers between the group's own cash and bank
accounts (Internal Transfer payment entries, Contra journal entries) and opening
entries are excluded so the same dirham is not counted twice.
"""

from collections import defaultdict

import frappe
from frappe.utils import add_days, cint, date_diff, flt, getdate

from treasury_dashboard.treasury.constants import APPROVED, PENDING

NOT_A_TRANSFER = """
	AND gle.is_opening = 'No'
	AND NOT EXISTS (
		SELECT 1 FROM `tabPayment Entry` pe
		WHERE gle.voucher_type = 'Payment Entry' AND pe.name = gle.voucher_no
			AND pe.payment_type = 'Internal Transfer')
	AND NOT EXISTS (
		SELECT 1 FROM `tabJournal Entry` je
		WHERE gle.voucher_type = 'Journal Entry' AND je.name = gle.voucher_no
			AND je.voucher_type = 'Contra Entry')
"""


def get_kpis(companies, from_date, to_date, user=None):
	if not companies:
		return {"currency": None, "groups": []}

	from_date, to_date = getdate(from_date), getdate(to_date)
	span = date_diff(to_date, from_date) + 1
	prev_to = add_days(from_date, -1)
	prev_from = add_days(prev_to, -(span - 1))

	currency_of = dict(
		frappe.get_all(
			"Company", filters={"name": ("in", companies)}, fields=["name", "default_currency"], as_list=True
		)
	)

	groups = defaultdict(_empty_group)

	for row in _balances(companies, to_date):
		group = groups[currency_of[row.company]]
		bucket = group["cash"] if row.account_type == "Cash" else group["bank"]
		bucket["value"] += flt(row.balance)
		bucket["accounts"].append(
			{
				"account": row.account,
				"account_name": row.account_name,
				"company": row.company,
				"balance": flt(row.balance),
			}
		)

	for row in _flows(companies, from_date, to_date):
		group = groups[currency_of[row.company]]
		group["receipts"]["value"] += flt(row.inflow)
		group["receipts"]["count"] += row.inflow_vouchers
		group["payments"]["value"] += flt(row.outflow)
		group["payments"]["count"] += row.outflow_vouchers
		day = group["trend"].setdefault(str(row.posting_date), {"inflow": 0.0, "outflow": 0.0})
		day["inflow"] += flt(row.inflow)
		day["outflow"] += flt(row.outflow)

	for row in _flows(companies, prev_from, prev_to):
		group = groups[currency_of[row.company]]
		group["receipts"]["previous"] += flt(row.inflow)
		group["payments"]["previous"] += flt(row.outflow)

	user = user or frappe.session.user
	for row in _approval_queue(companies, user):
		group = groups[currency_of[row.company]]
		group["pending"]["count"] += cint(row.pending_count)
		group["pending"]["amount"] += flt(row.pending_amount)
		group["pending"]["raised_by_others"] += cint(row.raised_by_others)
		group["pending"]["awaiting_posting"] += cint(row.awaiting_posting)

	# currencies of selected companies with no activity still get a (zero) card set
	for currency in set(currency_of.values()):
		groups[currency]

	ordered = sorted(groups.items(), key=lambda item: -_weight(item[1]))
	result = []
	for currency, group in ordered:
		group["currency"] = currency
		group["trend"] = [{"date": d, **v} for d, v in sorted(group["trend"].items())]
		for bucket in (group["cash"], group["bank"]):
			active = [a for a in bucket["accounts"] if abs(a["balance"]) >= 0.005]
			bucket["idle_accounts"] = len(bucket["accounts"]) - len(active)
			bucket["accounts"] = sorted(active, key=lambda a: -abs(a["balance"]))
		result.append(group)

	return {
		"currency": result[0]["currency"],
		"from_date": str(from_date),
		"to_date": str(to_date),
		"previous_period": {"from_date": str(prev_from), "to_date": str(prev_to)},
		"groups": result,
	}


def _empty_group():
	return {
		"cash": {"value": 0.0, "accounts": [], "idle_accounts": 0},
		"bank": {"value": 0.0, "accounts": [], "idle_accounts": 0},
		"receipts": {"value": 0.0, "previous": 0.0, "count": 0},
		"payments": {"value": 0.0, "previous": 0.0, "count": 0},
		"pending": {"count": 0, "amount": 0.0, "raised_by_others": 0, "awaiting_posting": 0},
		"trend": {},
	}


def _weight(group):
	return abs(group["cash"]["value"]) + abs(group["bank"]["value"]) + group["receipts"]["value"]


def _balances(companies, as_of):
	return frappe.db.sql(
		"""
		SELECT acc.company, acc.name AS account, acc.account_name, acc.account_type,
			COALESCE(SUM(gle.debit - gle.credit), 0) AS balance
		FROM `tabAccount` acc
		LEFT JOIN `tabGL Entry` gle
			ON gle.account = acc.name
			AND gle.is_cancelled = 0
			AND gle.posting_date <= %(as_of)s
		WHERE acc.company IN %(companies)s
			AND acc.account_type IN ('Cash', 'Bank')
			AND acc.is_group = 0
			AND acc.disabled = 0
		GROUP BY acc.company, acc.name, acc.account_name, acc.account_type
		""",
		{"companies": tuple(companies), "as_of": as_of},
		as_dict=True,
	)


def _flows(companies, from_date, to_date):
	return frappe.db.sql(
		f"""
		SELECT gle.company, gle.posting_date,
			SUM(gle.debit) AS inflow,
			SUM(gle.credit) AS outflow,
			COUNT(DISTINCT CASE WHEN gle.debit > 0 THEN gle.voucher_no END) AS inflow_vouchers,
			COUNT(DISTINCT CASE WHEN gle.credit > 0 THEN gle.voucher_no END) AS outflow_vouchers
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.company IN %(companies)s
			AND gle.is_cancelled = 0
			AND acc.account_type IN ('Cash', 'Bank')
			AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
			{NOT_A_TRANSFER}
		GROUP BY gle.company, gle.posting_date
		""",
		{"companies": tuple(companies), "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)


def _approval_queue(companies, user):
	return frappe.db.sql(
		"""
		SELECT company,
			SUM(status = %(pending)s) AS pending_count,
			SUM(CASE WHEN status = %(pending)s THEN amount ELSE 0 END) AS pending_amount,
			SUM(status = %(pending)s AND requested_by != %(user)s) AS raised_by_others,
			SUM(status = %(approved)s AND payment_entry_status = 'Draft') AS awaiting_posting
		FROM `tabTreasury Request`
		WHERE company IN %(companies)s AND status IN (%(pending)s, %(approved)s)
		GROUP BY company
		""",
		{"companies": tuple(companies), "pending": PENDING, "approved": APPROVED, "user": user},
		as_dict=True,
	)
