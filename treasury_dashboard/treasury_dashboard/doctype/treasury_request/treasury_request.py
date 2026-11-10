# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

import erpnext
import frappe
from erpnext.accounts.utils import FiscalYearError, get_fiscal_year
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cstr, flt, fmt_money, getdate, now_datetime, nowdate

from treasury_dashboard.treasury import permissions as perms
from treasury_dashboard.treasury.audit import log_action, notify_dashboards
from treasury_dashboard.treasury.constants import (
	ALLOWED_PARTY_TYPES,
	APPROVED,
	CANCELLED,
	DRAFT,
	INVOICE_DOCTYPE_FOR,
	MIN_REASON_LENGTH,
	OPEN_STATUSES,
	PENDING,
	POSTED,
	REJECTED,
	REQUEST_PAYMENT,
	REQUEST_RECEIPT,
	REQUEST_TYPES,
	STATUS_TRANSITIONS,
)
from treasury_dashboard.treasury.errors import (
	CompanyMismatchError,
	DuplicateRequestError,
	InvalidStatusTransition,
	LockedFieldError,
	SelfApprovalError,
)

NAMING_SERIES = {
	REQUEST_RECEIPT: "TR-RCV-.YYYY.-.#####",
	REQUEST_PAYMENT: "TR-PAY-.YYYY.-.#####",
}

LOCKED_AFTER_DRAFT = (
	"request_type",
	"company",
	"posting_date",
	"party_type",
	"party",
	"against_doctype",
	"against_invoice",
	"mode_of_payment",
	"account",
	"amount",
	"reference_no",
	"reference_date",
	"purpose",
)


class TreasuryRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link
		against_doctype: DF.Link | None
		against_invoice: DF.DynamicLink | None
		amount: DF.Currency
		approval_remarks: DF.SmallText | None
		approved_by: DF.Link | None
		approved_on: DF.Datetime | None
		cancellation_reason: DF.SmallText | None
		cancelled_by: DF.Link | None
		cancelled_on: DF.Datetime | None
		company: DF.Link
		currency: DF.Link | None
		invoice_outstanding: DF.Currency
		mode_of_payment: DF.Link
		party: DF.DynamicLink
		party_name: DF.Data | None
		party_type: DF.Link
		payment_entry: DF.Link | None
		payment_entry_status: DF.Literal["", "Draft", "Submitted", "Cancelled"]
		posting_date: DF.Date
		purpose: DF.SmallText
		reference_date: DF.Date | None
		reference_no: DF.Data | None
		rejected_by: DF.Link | None
		rejected_on: DF.Datetime | None
		rejection_reason: DF.SmallText | None
		request_type: DF.Literal["Receipt", "Payment"]
		requested_by: DF.Link | None
		status: DF.Literal["Draft", "Pending Approval", "Approved", "Posted", "Rejected", "Cancelled"]
		submitted_on: DF.Datetime | None
	# end: auto-generated types

	def autoname(self):
		self.name = make_autoname(NAMING_SERIES[self.request_type], doc=self)

	def before_validate(self):
		self.reference_no = cstr(self.reference_no).strip() or None
		self.purpose = cstr(self.purpose).strip()
		self.against_doctype = (
			INVOICE_DOCTYPE_FOR.get((self.request_type, self.party_type)) if self.against_invoice else None
		)

	def validate(self):
		if self.is_new():
			self.status = DRAFT
			self.requested_by = frappe.session.user

		self.validate_status_change()
		self.validate_locked_fields()

		if self.flags.skip_business_validation or self.status not in OPEN_STATUSES:
			return

		self.currency = erpnext.get_company_currency(self.company)
		self.validate_request_type()
		self.validate_amount()
		self.validate_posting_date()
		self.validate_account()
		self.validate_mode_of_payment()
		self.validate_party()
		self.validate_invoice()
		self.validate_reference()
		self.check_duplicates()

	def after_insert(self):
		log_action(self, _("Created"), to_status=self.status)

	def on_update(self):
		notify_dashboards(self.company)

	def on_trash(self):
		if self.status != DRAFT:
			frappe.throw(
				_("Only draft requests can be deleted. Cancel {0} instead.").format(self.name),
				InvalidStatusTransition,
			)

	# ------------------------------------------------------------------ guards

	def validate_status_change(self):
		if self.is_new():
			return

		previous = self.get_doc_before_save()
		if not previous or previous.status == self.status:
			return

		if not self.flags.status_change_allowed:
			frappe.throw(
				_("Status cannot be edited directly. Use the treasury actions instead."),
				InvalidStatusTransition,
			)

		if self.status not in STATUS_TRANSITIONS.get(previous.status, ()):
			frappe.throw(
				_("A request cannot move from {0} to {1}.").format(
					frappe.bold(_(previous.status)), frappe.bold(_(self.status))
				),
				InvalidStatusTransition,
			)

	def validate_locked_fields(self):
		previous = None if self.is_new() else self.get_doc_before_save()
		if not previous or previous.status == DRAFT:
			return

		changed = [
			_(self.meta.get_label(field))
			for field in LOCKED_AFTER_DRAFT
			if _normalise(previous.get(field)) != _normalise(self.get(field))
		]
		if changed:
			frappe.throw(
				_("{0} is {1}; these fields can no longer be changed: {2}").format(
					self.name, _(previous.status).lower(), ", ".join(changed)
				),
				LockedFieldError,
			)

	# -------------------------------------------------------- business rules

	def validate_request_type(self):
		if self.request_type not in REQUEST_TYPES:
			frappe.throw(_("Request type must be Receipt or Payment."))

		if self.party_type not in ALLOWED_PARTY_TYPES:
			frappe.throw(
				_("Party type must be one of: {0}.").format(", ".join(_(d) for d in ALLOWED_PARTY_TYPES))
			)

		if self.against_invoice and not self.against_doctype:
			frappe.throw(
				_("Invoices can only be settled on receipts from customers or payments to suppliers.")
			)

	def validate_amount(self):
		self.amount = flt(self.amount, self.precision("amount"))
		if self.amount <= 0:
			frappe.throw(_("Amount must be greater than zero."))

	def validate_posting_date(self):
		if getdate(self.posting_date) > getdate(nowdate()):
			frappe.throw(
				_("Posting date cannot be in the future. Use the cheque date for post-dated cheques.")
			)

		try:
			get_fiscal_year(self.posting_date, company=self.company)
		except FiscalYearError:
			frappe.throw(
				_("No active fiscal year covers {0} for {1}.").format(
					frappe.format(self.posting_date, "Date"), self.company
				)
			)

		frozen_upto = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
		if frozen_upto and getdate(self.posting_date) <= getdate(frozen_upto):
			frappe.throw(
				_("Accounts are frozen up to {0}. Choose a later posting date.").format(
					frappe.format(frozen_upto, "Date")
				)
			)

	def validate_account(self):
		account = frappe.db.get_value(
			"Account",
			self.account,
			["company", "account_type", "is_group", "disabled", "account_currency"],
			as_dict=True,
		)
		if not account:
			frappe.throw(_("Account {0} does not exist.").format(self.account))

		if account.company != self.company:
			frappe.throw(
				_("Account {0} belongs to {1}, not {2}.").format(
					frappe.bold(self.account), account.company, frappe.bold(self.company)
				),
				CompanyMismatchError,
			)
		if account.is_group:
			frappe.throw(_("{0} is a group account. Select a ledger account.").format(self.account))
		if account.disabled:
			frappe.throw(_("Account {0} is disabled.").format(self.account))
		if account.account_type not in ("Cash", "Bank"):
			frappe.throw(_("{0} is not a cash or bank account.").format(frappe.bold(self.account)))
		if account.account_currency != self.currency:
			frappe.throw(
				_("Only {0} cash and bank accounts are supported for {1}.").format(
					self.currency, self.company
				)
			)

		self._account_type = account.account_type

	def validate_mode_of_payment(self):
		mop = frappe.db.get_value("Mode of Payment", self.mode_of_payment, ["type", "enabled"], as_dict=True)
		if not mop or not mop.enabled:
			frappe.throw(_("Mode of Payment {0} is disabled or missing.").format(self.mode_of_payment))

		if mop.type in ("Cash", "Bank") and mop.type != self._account_type:
			frappe.throw(
				_("{0} is a {1} mode of payment but {2} is a {3} account.").format(
					frappe.bold(self.mode_of_payment),
					_(mop.type).lower(),
					frappe.bold(self.account),
					_(self._account_type).lower(),
				)
			)

	def validate_party(self):
		if self.party_type == "Customer":
			party = frappe.db.get_value(
				"Customer", self.party, ["customer_name as party_name", "disabled"], as_dict=True
			)
		else:
			party = frappe.db.get_value(
				"Supplier",
				self.party,
				["supplier_name as party_name", "disabled", "on_hold", "hold_type", "release_date"],
				as_dict=True,
			)

		if not party:
			frappe.throw(_("{0} {1} does not exist.").format(_(self.party_type), self.party))
		if party.disabled:
			frappe.throw(_("{0} {1} is disabled.").format(_(self.party_type), self.party))

		if (
			self.request_type == REQUEST_PAYMENT
			and party.get("on_hold")
			and party.hold_type in ("All", "Payments")
			and (not party.release_date or getdate(party.release_date) > getdate(nowdate()))
		):
			frappe.throw(_("Payments to supplier {0} are on hold.").format(frappe.bold(self.party)))

		self.party_name = party.party_name

	def validate_invoice(self):
		if not self.against_invoice:
			self.invoice_outstanding = 0
			return

		party_field = "customer" if self.against_doctype == "Sales Invoice" else "supplier"
		invoice = frappe.db.get_value(
			self.against_doctype,
			self.against_invoice,
			["company", "docstatus", "outstanding_amount", party_field, "is_return", "currency"],
			as_dict=True,
		)
		if not invoice or invoice.docstatus != 1:
			frappe.throw(
				_("{0} {1} must be submitted.").format(_(self.against_doctype), self.against_invoice)
			)
		if invoice.company != self.company:
			frappe.throw(
				_("{0} belongs to {1}, not {2}.").format(self.against_invoice, invoice.company, self.company),
				CompanyMismatchError,
			)
		if invoice.get(party_field) != self.party:
			frappe.throw(_("{0} is not billed to {1}.").format(self.against_invoice, self.party_name))
		if invoice.is_return:
			frappe.throw(_("Return invoices cannot be settled from the treasury desk."))
		if invoice.currency != self.currency:
			frappe.throw(_("Only invoices billed in {0} can be settled here.").format(self.currency))

		committed = flt(
			frappe.db.get_value(
				"Treasury Request",
				{
					"against_doctype": self.against_doctype,
					"against_invoice": self.against_invoice,
					"status": ("in", OPEN_STATUSES),
					"name": ("!=", self.name),
				},
				"sum(amount)",
			)
		)
		available = flt(invoice.outstanding_amount) - committed
		if self.amount > flt(available, self.precision("amount")):
			frappe.throw(
				_(
					"{0} exceeds what is still collectable on {1}: outstanding {2}, already requested {3}."
				).format(
					self._money(self.amount),
					self.against_invoice,
					self._money(invoice.outstanding_amount),
					self._money(committed),
				)
			)

		self.invoice_outstanding = invoice.outstanding_amount

	def validate_reference(self):
		if self._account_type == "Bank" and not (self.reference_no and self.reference_date):
			frappe.throw(_("Cheque / reference number and date are required for bank transactions."))

	def check_duplicates(self):
		if self.reference_no:
			clash = frappe.db.get_value(
				"Treasury Request",
				{
					"company": self.company,
					"party_type": self.party_type,
					"party": self.party,
					"reference_no": self.reference_no,
					"status": ("not in", (REJECTED, CANCELLED)),
					"name": ("!=", self.name),
				},
				"name",
			)
			if clash:
				frappe.throw(
					_("Reference {0} from {1} is already recorded on {2}.").format(
						frappe.bold(self.reference_no), self.party_name, frappe.bold(clash)
					),
					DuplicateRequestError,
				)

			for entry in frappe.get_all(
				"Payment Entry",
				filters={
					"company": self.company,
					"party_type": self.party_type,
					"party": self.party,
					"reference_no": self.reference_no,
					"docstatus": ("<", 2),
				},
				fields=["name", "treasury_request"],
			):
				if entry.treasury_request != self.name:
					frappe.throw(
						_("Reference {0} from {1} is already recorded on Payment Entry {2}.").format(
							frappe.bold(self.reference_no), self.party_name, frappe.bold(entry.name)
						),
						DuplicateRequestError,
					)

		for twin in frappe.get_all(
			"Treasury Request",
			filters={
				"company": self.company,
				"request_type": self.request_type,
				"party_type": self.party_type,
				"party": self.party,
				"amount": self.amount,
				"posting_date": self.posting_date,
				"status": ("in", OPEN_STATUSES),
				"name": ("!=", self.name),
			},
			fields=["name", "reference_no"],
		):
			if not (self.reference_no and twin.reference_no):
				frappe.throw(
					_(
						"{0} for {1} of {2} on this date is already open as {3}. "
						"Cancel that request or record a distinct reference number."
					).format(
						_(self.request_type),
						self.party_name,
						self._money(self.amount),
						frappe.bold(twin.name),
					),
					DuplicateRequestError,
				)

	# ---------------------------------------------------------------- actions

	def submit_for_approval(self):
		self._assert_company_access()
		if self.requested_by != frappe.session.user and not perms.can_manage():
			frappe.throw(
				_("Only the requester or a Treasury Officer can submit this request."), frappe.PermissionError
			)
		self._expect(DRAFT)
		self._transition(PENDING, _("Submitted for Approval"), values={"submitted_on": now_datetime()})

	def approve(self, remarks=None):
		self._assert_company_access()
		self._assert_decision_maker(_("approve"))
		self._expect(PENDING)

		remarks = cstr(remarks).strip() or None
		self._transition(
			APPROVED,
			_("Approved"),
			remarks=remarks,
			values={
				"approved_by": frappe.session.user,
				"approved_on": now_datetime(),
				"approval_remarks": remarks,
			},
		)
		return self.make_payment_entry()

	def reject(self, reason):
		self._assert_company_access()
		self._assert_decision_maker(_("reject"))
		self._expect(PENDING)
		reason = _require_reason(reason, _("rejection"))

		self._transition(
			REJECTED,
			_("Rejected"),
			remarks=reason,
			values={
				"rejected_by": frappe.session.user,
				"rejected_on": now_datetime(),
				"rejection_reason": reason,
			},
		)

	def cancel_request(self, reason):
		self._assert_company_access()
		is_requester = self.requested_by == frappe.session.user
		if not (perms.can_manage() or (is_requester and self.status in (DRAFT, PENDING))):
			frappe.throw(
				_("Only the requester (before approval) or a Treasury Officer can cancel this request."),
				frappe.PermissionError,
			)
		self._expect(DRAFT, PENDING, APPROVED)
		reason = _require_reason(reason, _("cancellation"))

		if self.status == APPROVED:
			self._discard_draft_payment_entry(reason)

		self._transition(
			CANCELLED,
			_("Cancelled"),
			remarks=reason,
			values={
				"cancelled_by": frappe.session.user,
				"cancelled_on": now_datetime(),
				"cancellation_reason": reason,
			},
		)

	def regenerate_payment_entry(self):
		self._assert_company_access()
		if not (perms.can_decide() or perms.can_manage()):
			frappe.throw(_("Not permitted to create Payment Entries."), frappe.PermissionError)
		self._expect(APPROVED)
		return self.make_payment_entry()

	def make_payment_entry(self):
		from treasury_dashboard.treasury.payment_entry import create_draft_payment_entry

		entry = create_draft_payment_entry(self)
		self.db_set({"payment_entry": entry.name, "payment_entry_status": "Draft"}, notify=True)
		log_action(
			self,
			_("Payment Entry Created"),
			remarks=_("Draft {0} created for posting").format(entry.name),
			linked_doctype="Payment Entry",
			linked_name=entry.name,
		)
		return entry

	def apply_system_status(self, status, action, values=None, linked_name=None):
		"""Status changes driven by the linked Payment Entry lifecycle."""
		self._transition(
			status,
			action,
			values=values,
			linked=("Payment Entry", linked_name) if linked_name else None,
			system=True,
		)

	# ---------------------------------------------------------------- helpers

	def get_allowed_actions(self, user=None):
		user = user or frappe.session.user
		if self.company not in perms.get_permitted_company_names(user):
			return []

		is_requester = self.requested_by == user
		manager = perms.can_manage(user)
		decider = perms.can_decide(user) and not is_requester
		live_entry = self.payment_entry and self.payment_entry_status in ("Draft", "Submitted")

		actions = []
		if self.status == DRAFT and (is_requester or manager):
			actions.append("submit")
		if self.status == PENDING and decider:
			actions += ["approve", "reject"]
		if self.status == APPROVED and not live_entry and (perms.can_decide(user) or manager):
			actions.append("create_payment_entry")
		if (self.status in (DRAFT, PENDING) and is_requester) or (self.status in OPEN_STATUSES and manager):
			actions.append("cancel")
		return actions

	def _transition(self, status, action, remarks=None, values=None, linked=None, system=False):
		previous = self.status
		if status not in STATUS_TRANSITIONS.get(previous, ()):
			frappe.throw(
				_("A request cannot move from {0} to {1}.").format(_(previous), _(status)),
				InvalidStatusTransition,
			)

		self.status = status
		self.update(values or {})
		self.flags.status_change_allowed = True
		self.flags.skip_business_validation = system or status in (REJECTED, CANCELLED)
		try:
			self.save(ignore_permissions=True)
		finally:
			self.flags.status_change_allowed = False
			self.flags.skip_business_validation = False

		log_action(
			self,
			action,
			from_status=previous,
			to_status=status,
			remarks=remarks,
			linked_doctype=linked[0] if linked else None,
			linked_name=linked[1] if linked else None,
		)

	def _discard_draft_payment_entry(self, reason):
		if not self.payment_entry or self.payment_entry_status != "Draft":
			return

		entry = self.payment_entry
		self.db_set({"payment_entry": None, "payment_entry_status": None}, update_modified=False)
		frappe.flags.treasury_skip_pe_sync = True
		try:
			frappe.delete_doc("Payment Entry", entry, ignore_permissions=True)
		finally:
			frappe.flags.treasury_skip_pe_sync = False

		log_action(
			self,
			_("Payment Entry Deleted"),
			remarks=_("Draft removed on cancellation: {0}").format(reason),
			linked_doctype="Payment Entry",
			linked_name=entry,
		)

	def _assert_company_access(self):
		perms.assert_company_access(self.company)

	def _assert_decision_maker(self, verb):
		if not perms.can_decide():
			frappe.throw(_("Only Treasury Approvers can {0} requests.").format(verb), frappe.PermissionError)
		if self.requested_by == frappe.session.user:
			frappe.throw(_("You cannot {0} a request you raised yourself.").format(verb), SelfApprovalError)

	def _expect(self, *statuses):
		if self.status not in statuses:
			frappe.throw(
				_("{0} is {1}; this action needs it to be {2}.").format(
					self.name, frappe.bold(_(self.status)), " / ".join(_(s) for s in statuses)
				),
				InvalidStatusTransition,
			)

	def _money(self, value):
		return fmt_money(value, currency=self.currency)


def _normalise(value):
	if value in (None, ""):
		return ""
	if isinstance(value, float | int):
		return flt(value, 2)
	return cstr(value)


def _require_reason(reason, label):
	reason = cstr(reason).strip()
	if len(reason) < MIN_REASON_LENGTH:
		frappe.throw(
			_("Please give a {0} reason of at least {1} characters.").format(label, MIN_REASON_LENGTH)
		)
	return reason
