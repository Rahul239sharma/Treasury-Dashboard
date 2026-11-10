import frappe
from frappe.utils import add_days, flt, nowdate

from treasury_dashboard.api import dashboard, requests
from treasury_dashboard.tests.utils import (
	CUSTOMER,
	SCHOOL_A,
	SCHOOL_B,
	TreasuryTestCase,
	bank_account,
	cash_account,
	remove_fixtures,
)


def _group(kpis, currency="AED"):
	return next(g for g in kpis["groups"] if g["currency"] == currency)


class TestSchoolIsolation(TreasuryTestCase):
	def test_user_only_sees_their_school(self):
		self.as_user("cashier_a")
		names = [c["name"] for c in dashboard.get_bootstrap()["companies"]]
		self.assertIn(SCHOOL_A, names)
		self.assertNotIn(SCHOOL_B, names)

	def test_other_school_filter_is_refused(self):
		self.as_user("cashier_a")
		with self.assertRaises(frappe.PermissionError):
			dashboard.get_dashboard(company=SCHOOL_B)

	def test_other_school_records_are_absent_from_the_grid(self):
		request = self.make_request(by="cashier_b", company=SCHOOL_B, account=cash_account(SCHOOL_B))
		self.as_user("cashier_a")
		rows = dashboard.get_transactions(search=request.name)["rows"]
		self.assertEqual(rows, [])

	def test_other_school_detail_is_refused(self):
		request = self.make_request(by="cashier_b", company=SCHOOL_B, account=cash_account(SCHOOL_B))
		self.as_user("approver_a")
		with self.assertRaises(frappe.PermissionError):
			dashboard.get_transaction_detail("Treasury Request", request.name)
		with self.assertRaises(frappe.PermissionError):
			requests.approve_request(request.name)

	def test_cannot_raise_request_for_another_school(self):
		self.as_user("cashier_a")
		with self.assertRaises(frappe.PermissionError):
			requests.create_request(
				{
					"request_type": "Receipt",
					"company": SCHOOL_B,
					"party_type": "Customer",
					"party": CUSTOMER,
					"mode_of_payment": "Cash",
					"account": cash_account(SCHOOL_B),
					"amount": 500,
					"purpose": "Cross-school attempt",
				}
			)

	def test_approver_cannot_raise_requests(self):
		self.as_user("approver_a")
		with self.assertRaises(frappe.PermissionError):
			requests.create_request({"company": SCHOOL_A, "amount": 10})

	def test_users_without_treasury_roles_are_turned_away(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			dashboard.get_bootstrap()

	def test_link_queries_respect_school(self):
		self.as_user("cashier_a")
		accounts = [r[0] for r in requests.account_query("Account", "", "name", 0, 50, {"company": SCHOOL_A})]
		self.assertIn(cash_account(), accounts)
		self.assertIn(bank_account(), accounts)
		self.assertNotIn("Debtors - _TTA", accounts)
		with self.assertRaises(frappe.PermissionError):
			requests.account_query("Account", "", "name", 0, 50, {"company": SCHOOL_B})


class TestDashboardFigures(TreasuryTestCase):
	def _receipt_entry(self, amount, account, mode="Cash", company=SCHOOL_A, payment_type="Receive"):
		frappe.set_user("Administrator")
		abbr = "_TTA" if company == SCHOOL_A else "_TTB"
		entry = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": payment_type,
				"company": company,
				"posting_date": nowdate(),
				"mode_of_payment": mode,
				"party_type": "Customer",
				"party": CUSTOMER,
				"paid_from": f"Debtors - {abbr}" if payment_type == "Receive" else account,
				"paid_to": account if payment_type == "Receive" else f"Debtors - {abbr}",
				"paid_amount": amount,
				"received_amount": amount,
				"reference_no": "TEST-REF",
				"reference_date": nowdate(),
			}
		)
		entry.insert()
		entry.submit()
		return entry

	def _kpis(self, company=SCHOOL_A):
		self.as_user("cashier_a" if company == SCHOOL_A else "cashier_b")
		return _group(
			dashboard.get_kpis(company=company, from_date=add_days(nowdate(), -1), to_date=nowdate())
		)

	def test_posted_receipt_moves_cash_and_receipt_figures(self):
		before = self._kpis()
		self._receipt_entry(4_321, cash_account())
		after = self._kpis()
		self.assertAlmostEqual(after["cash"]["value"] - before["cash"]["value"], 4_321)
		self.assertAlmostEqual(after["receipts"]["value"] - before["receipts"]["value"], 4_321)
		self.assertAlmostEqual(after["bank"]["value"], before["bank"]["value"])

	def test_refund_counts_as_payment(self):
		before = self._kpis()
		self._receipt_entry(610, bank_account(), mode="Wire Transfer", payment_type="Pay")
		after = self._kpis()
		self.assertAlmostEqual(after["payments"]["value"] - before["payments"]["value"], 610)
		self.assertAlmostEqual(before["bank"]["value"] - after["bank"]["value"], 610)

	def test_internal_transfer_moves_balances_without_counting_as_flow(self):
		self._receipt_entry(5_000, cash_account())
		before = self._kpis()
		frappe.set_user("Administrator")
		transfer = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Internal Transfer",
				"company": SCHOOL_A,
				"posting_date": nowdate(),
				"mode_of_payment": "Cash",
				"paid_from": cash_account(),
				"paid_to": bank_account(),
				"paid_amount": 3_000,
				"received_amount": 3_000,
				"reference_no": "DEP-TEST",
				"reference_date": nowdate(),
			}
		).insert()
		transfer.submit()
		after = self._kpis()
		self.assertAlmostEqual(before["cash"]["value"] - after["cash"]["value"], 3_000)
		self.assertAlmostEqual(after["bank"]["value"] - before["bank"]["value"], 3_000)
		self.assertAlmostEqual(after["receipts"]["value"], before["receipts"]["value"])
		self.assertAlmostEqual(after["payments"]["value"], before["payments"]["value"])

		self.as_user("cashier_a")
		rows = dashboard.get_transactions(
			company=SCHOOL_A, category="Internal Transfer", search=transfer.name
		)["rows"]
		self.assertEqual([r.name for r in rows], [transfer.name])

	def test_other_school_activity_does_not_leak_into_figures(self):
		before = self._kpis(SCHOOL_A)
		self._receipt_entry(7_777, cash_account(SCHOOL_B), company=SCHOOL_B)
		after = self._kpis(SCHOOL_A)
		self.assertAlmostEqual(after["cash"]["value"], before["cash"]["value"])
		self.assertAlmostEqual(after["receipts"]["value"], before["receipts"]["value"])

	def test_pending_approvals_card(self):
		before = self._kpis()["pending"]
		self.make_request(amount=880, submit=True)
		after = self._kpis()["pending"]
		self.assertEqual(after["count"] - before["count"], 1)
		self.assertAlmostEqual(after["amount"] - before["amount"], 880)


class TestUnifiedGrid(TreasuryTestCase):
	def test_request_and_its_entry_appear_as_one_row(self):
		request = self.make_request(amount=2_222, submit=True)
		self.approve(request)
		self.as_user("cashier_a")
		data = dashboard.get_transactions(company=SCHOOL_A, search=request.name)
		self.assertEqual(len(data["rows"]), 1)
		row = data["rows"][0]
		self.assertEqual(row.status, "Approved")
		self.assertEqual(row.linked_doctype, "Payment Entry")

	def test_status_and_type_filters(self):
		self.make_request(amount=2_323, submit=True)
		self.as_user("cashier_a")
		pending = dashboard.get_transactions(company=SCHOOL_A, statuses=["Pending Approval"])["rows"]
		self.assertTrue(pending)
		self.assertTrue(all(r.status == "Pending Approval" for r in pending))

		payments = dashboard.get_transactions(company=SCHOOL_A, category="Payment")["rows"]
		self.assertTrue(all(r.category == "Payment" for r in payments))

	def test_detail_lists_allowed_actions_per_user(self):
		request = self.make_request(amount=2_424, submit=True)

		self.as_user("approver_a")
		detail = dashboard.get_transaction_detail("Treasury Request", request.name)
		self.assertEqual(sorted(detail["actions"]), ["approve", "reject"])

		self.as_user("cashier_a")
		detail = dashboard.get_transaction_detail("Treasury Request", request.name)
		self.assertEqual(detail["actions"], ["cancel"])
		self.assertTrue(detail["is_own_request"])

	def test_full_flow_through_the_api(self):
		self.as_user("cashier_a")
		created = requests.create_request(
			{
				"request_type": "Receipt",
				"company": SCHOOL_A,
				"posting_date": nowdate(),
				"party_type": "Customer",
				"party": CUSTOMER,
				"mode_of_payment": "Cash",
				"account": cash_account(),
				"amount": 1_234.5,
				"purpose": "Bus fee top-up",
				"status": "Approved",
				"requested_by": "someone.else@test.local",
			},
			submit=1,
		)
		self.assertEqual(created["status"], "Pending Approval")
		self.assertEqual(
			frappe.db.get_value("Treasury Request", created["name"], "requested_by"),
			"treasury.cashier.a@test.local",
		)

		self.as_user("approver_a")
		approved = requests.approve_request(created["name"], remarks="ok")
		self.assertEqual(approved["status"], "Approved")
		self.assertEqual(approved["linked"][0]["doctype"], "Payment Entry")
		self.assertEqual(approved["linked"][0]["status"], "Draft")
		self.assertAlmostEqual(flt(approved["linked"][0]["amount"]), 1_234.5)

	def test_unknown_category_is_rejected(self):
		self.as_user("cashier_a")
		with self.assertRaises(frappe.ValidationError):
			dashboard.get_transactions(category="Crypto")


def tearDownModule():
	remove_fixtures()
