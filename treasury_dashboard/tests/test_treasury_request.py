import frappe
from frappe.utils import add_days, nowdate

from treasury_dashboard.tests.utils import (
	CUSTOMER,
	HELD_SUPPLIER,
	SCHOOL_A,
	SCHOOL_B,
	SUPPLIER,
	TreasuryTestCase,
	bank_account,
	cash_account,
	employee,
	remove_fixtures,
)
from treasury_dashboard.treasury.errors import (
	CompanyMismatchError,
	DuplicatePaymentEntryError,
	DuplicateRequestError,
	InvalidStatusTransition,
	LockedFieldError,
	SelfApprovalError,
)


class TestRequestValidation(TreasuryTestCase):
	def test_amount_must_be_positive(self):
		for amount in (0, -250):
			with self.assertRaisesRegex(frappe.ValidationError, "greater than zero"):
				self.make_request(amount=amount)

	def test_account_must_belong_to_the_same_school(self):
		with self.assertRaises(CompanyMismatchError):
			self.make_request(account=cash_account(SCHOOL_B))

	def test_account_must_be_cash_or_bank(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not a cash or bank account"):
			self.make_request(account="Debtors - _TTA")

	def test_mode_of_payment_must_match_account_type(self):
		with self.assertRaisesRegex(frappe.ValidationError, "mode of payment"):
			self.make_request(mode_of_payment="Cash", account=bank_account())

	def test_bank_transactions_need_a_reference(self):
		with self.assertRaisesRegex(frappe.ValidationError, "reference number and date are required"):
			self.make_request(mode_of_payment="Wire Transfer", account=bank_account())

	def test_posting_date_cannot_be_in_the_future(self):
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be in the future"):
			self.make_request(posting_date=add_days(nowdate(), 1))

	def test_post_dated_cheque_is_allowed(self):
		request = self.make_request(
			mode_of_payment="Cheque",
			account=bank_account(),
			reference_no="000731",
			reference_date=add_days(nowdate(), 30),
		)
		self.assertEqual(request.status, "Draft")

	def test_supplier_on_hold_cannot_be_paid(self):
		with self.assertRaisesRegex(frappe.ValidationError, "on hold"):
			self.make_request(request_type="Payment", party_type="Supplier", party=HELD_SUPPLIER)

	def test_only_customers_and_suppliers(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Party type must be"):
			self.make_request(party_type="Employee", party=employee())


class TestDuplicatePrevention(TreasuryTestCase):
	def test_same_reference_from_same_party_is_blocked(self):
		values = {
			"mode_of_payment": "Cheque",
			"account": bank_account(),
			"reference_no": "445566",
			"reference_date": nowdate(),
		}
		self.make_request(**values)
		with self.assertRaises(DuplicateRequestError):
			self.make_request(amount=999, **values)

	def test_identical_open_request_is_blocked(self):
		self.make_request(amount=2750)
		with self.assertRaises(DuplicateRequestError):
			self.make_request(amount=2750)

	def test_identical_amount_with_distinct_references_is_allowed(self):
		common = {
			"mode_of_payment": "Cheque",
			"account": bank_account(),
			"reference_date": nowdate(),
			"amount": 3100,
		}
		self.make_request(reference_no="100001", **common)
		second = self.make_request(reference_no="100002", **common)
		self.assertEqual(second.status, "Draft")

	def test_rejected_request_does_not_block_a_fresh_one(self):
		first = self.make_request(amount=4200, submit=True)
		self.as_user("approver_a")
		first.reload()
		first.reject("Wrong parent account selected")
		self.assertEqual(self.make_request(amount=4200).status, "Draft")

	def test_cannot_request_more_than_invoice_outstanding(self):
		invoice = self.make_sales_invoice(10_000)
		self.make_request(amount=6_000, against_invoice=invoice.name)
		with self.assertRaisesRegex(frappe.ValidationError, "exceeds what is still collectable"):
			self.make_request(amount=5_000, against_invoice=invoice.name, purpose="Second instalment")

	def test_invoice_from_another_school_is_rejected(self):
		invoice = self.make_sales_invoice(5_000, company=SCHOOL_B)
		with self.assertRaises(CompanyMismatchError):
			self.make_request(amount=1_000, against_invoice=invoice.name)


class TestStatusRules(TreasuryTestCase):
	def test_status_cannot_be_edited_directly(self):
		request = self.make_request()
		request.status = "Approved"
		with self.assertRaises(InvalidStatusTransition):
			request.save()

	def test_fields_lock_once_submitted(self):
		request = self.make_request(submit=True)
		request.reload()
		request.amount = 9_999
		with self.assertRaises(LockedFieldError):
			request.save()

	def test_draft_cannot_be_approved(self):
		request = self.make_request()
		with self.assertRaises(InvalidStatusTransition):
			self.approve(request)

	def test_rejected_request_cannot_be_approved(self):
		request = self.make_request(submit=True)
		self.as_user("approver_a")
		request.reload()
		request.reject("Receipt book number missing")
		with self.assertRaises(InvalidStatusTransition):
			self.approve(request)

	def test_rejection_needs_a_reason(self):
		request = self.make_request(submit=True)
		self.as_user("approver_a")
		request.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "reason"):
			request.reject("  ")

	def test_only_drafts_can_be_deleted(self):
		request = self.make_request(submit=True)
		frappe.set_user("Administrator")
		with self.assertRaises(InvalidStatusTransition):
			frappe.delete_doc("Treasury Request", request.name)


class TestApprovalFlow(TreasuryTestCase):
	def test_receipt_approval_creates_one_draft_payment_entry(self):
		request = self.make_request(submit=True, amount=3_250)
		entry = self.approve(request, remarks="Cash counted and verified")

		request.reload()
		self.assertEqual(request.status, "Approved")
		self.assertEqual(request.approved_by, "treasury.approver.a@test.local")
		self.assertEqual(request.payment_entry, entry.name)

		entry.reload()
		self.assertEqual(entry.docstatus, 0)
		self.assertEqual(entry.payment_type, "Receive")
		self.assertEqual(entry.paid_to, cash_account())
		self.assertEqual(entry.party, CUSTOMER)
		self.assertEqual(entry.received_amount, 3_250)
		self.assertEqual(entry.treasury_request, request.name)
		self.assertEqual(frappe.db.count("Payment Entry", {"treasury_request": request.name}), 1)

	def test_payment_approval_creates_pay_entry(self):
		request = self.make_request(
			request_type="Payment",
			party_type="Supplier",
			party=SUPPLIER,
			mode_of_payment="Wire Transfer",
			account=bank_account(),
			reference_no="FT2631400017",
			reference_date=nowdate(),
			amount=12_400,
			submit=True,
		)
		entry = self.approve(request)
		self.assertEqual(entry.payment_type, "Pay")
		self.assertEqual(entry.paid_from, bank_account())
		self.assertEqual(entry.paid_amount, 12_400)

	def test_receipt_against_invoice_is_allocated(self):
		invoice = self.make_sales_invoice(8_000)
		request = self.make_request(amount=8_000, against_invoice=invoice.name, submit=True)
		entry = self.approve(request)
		self.assertEqual(len(entry.references), 1)
		self.assertEqual(entry.references[0].reference_name, invoice.name)
		self.assertEqual(entry.references[0].allocated_amount, 8_000)

	def test_requester_cannot_approve_own_request(self):
		frappe.get_doc("User", "treasury.approver.a@test.local").add_roles("Treasury Cashier")
		try:
			request = self.make_request(by="approver_a", submit=True)
			with self.assertRaises(SelfApprovalError):
				self.approve(request, by="approver_a")
			with self.assertRaises(SelfApprovalError):
				request.reject("Trying to reject my own")
		finally:
			frappe.set_user("Administrator")
			frappe.get_doc("User", "treasury.approver.a@test.local").remove_roles("Treasury Cashier")

	def test_cashier_cannot_approve(self):
		request = self.make_request(submit=True)
		with self.assertRaises(frappe.PermissionError):
			self.approve(request, by="cashier_a2")

	def test_approver_from_another_school_cannot_act(self):
		request = self.make_request(submit=True)
		with self.assertRaises(frappe.PermissionError):
			self.approve(request, by="approver_b")

	def test_second_payment_entry_is_refused(self):
		request = self.make_request(submit=True)
		entry = self.approve(request)

		with self.assertRaises(InvalidStatusTransition):
			request.approve()

		frappe.set_user("Administrator")
		copy = frappe.copy_doc(entry)
		copy.treasury_request = request.name
		with self.assertRaises(DuplicatePaymentEntryError):
			copy.insert()

	def test_draft_entry_cannot_be_altered_before_posting(self):
		request = self.make_request(submit=True, amount=2_000)
		entry = self.approve(request)
		frappe.set_user("Administrator")
		entry.reload()
		entry.paid_amount = entry.received_amount = 2_500
		with self.assertRaisesRegex(frappe.ValidationError, "no longer matches"):
			entry.save()


class TestPaymentEntryLifecycle(TreasuryTestCase):
	def _approved(self, **values):
		request = self.make_request(submit=True, **values)
		entry = self.approve(request)
		return request, entry

	def test_posting_marks_request_posted(self):
		request, entry = self._approved(amount=1_150)
		self.as_user("officer_a")
		frappe.get_doc("Payment Entry", entry.name).submit()

		request.reload()
		self.assertEqual(request.status, "Posted")
		self.assertEqual(request.payment_entry_status, "Submitted")

	def test_cancelling_entry_reopens_request_for_a_new_entry(self):
		request, entry = self._approved(amount=1_275)
		frappe.set_user("Administrator")
		entry = frappe.get_doc("Payment Entry", entry.name)
		entry.submit()
		entry.cancel()

		request.reload()
		self.assertEqual(request.status, "Approved")
		self.assertEqual(request.payment_entry_status, "Cancelled")

		self.as_user("approver_a")
		replacement = request.regenerate_payment_entry()
		self.assertNotEqual(replacement.name, entry.name)
		self.assertEqual(
			frappe.db.count("Payment Entry", {"treasury_request": request.name, "docstatus": 0}), 1
		)

	def test_deleting_draft_entry_unlinks_it(self):
		request, entry = self._approved(amount=1_325)
		frappe.set_user("Administrator")
		frappe.delete_doc("Payment Entry", entry.name)

		request.reload()
		self.assertEqual(request.status, "Approved")
		self.assertFalse(request.payment_entry)
		self.assertIn(
			"create_payment_entry", request.get_allowed_actions(user="treasury.approver.a@test.local")
		)

	def test_cancelling_approved_request_removes_its_draft_entry(self):
		request, entry = self._approved(amount=1_475)
		self.as_user("officer_a")
		request.reload()
		request.cancel_request("Parent paid the same fee online")
		self.assertFalse(frappe.db.exists("Payment Entry", entry.name))
		self.assertEqual(frappe.db.get_value("Treasury Request", request.name, "status"), "Cancelled")

	def test_requester_cannot_cancel_after_approval(self):
		request, _entry = self._approved(amount=1_525)
		self.as_user("cashier_a")
		request.reload()
		with self.assertRaises(frappe.PermissionError):
			request.cancel_request("Changed my mind")


class TestAuditTrail(TreasuryTestCase):
	def test_every_decision_is_logged(self):
		request = self.make_request(submit=True, amount=1_775)
		entry = self.approve(request, remarks="Verified against receipt book 0412")

		actions = frappe.get_all(
			"Treasury Audit Log",
			filters={"reference_name": request.name},
			fields=["action", "to_status", "user", "linked_name"],
			order_by="creation asc",
		)
		self.assertEqual(
			[a.action for a in actions],
			["Created", "Submitted for Approval", "Approved", "Payment Entry Created"],
		)
		self.assertEqual(actions[2].user, "treasury.approver.a@test.local")
		self.assertEqual(actions[3].linked_name, entry.name)

	def test_rejection_reason_is_kept(self):
		request = self.make_request(submit=True, amount=1_825)
		self.as_user("approver_a")
		request.reload()
		request.reject("Amount does not match the receipt slip")

		log = frappe.get_all(
			"Treasury Audit Log",
			filters={"reference_name": request.name, "action": "Rejected"},
			fields=["remarks", "user"],
		)[0]
		self.assertEqual(log.remarks, "Amount does not match the receipt slip")
		self.assertEqual(request.rejection_reason, "Amount does not match the receipt slip")

	def test_audit_rows_are_immutable(self):
		request = self.make_request(amount=1_875)
		frappe.set_user("Administrator")
		log = frappe.get_last_doc("Treasury Audit Log", filters={"reference_name": request.name})
		log.remarks = "edited"
		with self.assertRaises(frappe.ValidationError):
			log.save(ignore_permissions=True)


def tearDownModule():
	remove_fixtures()
