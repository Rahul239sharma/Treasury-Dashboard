from itertools import count

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from treasury_dashboard.setup.demo import _ensure_fiscal_years

PASSWORD = "Test@Treasury#2026"

SCHOOL_A = "_Test Treasury School A"
SCHOOL_B = "_Test Treasury School B"
ABBR = {SCHOOL_A: "_TTA", SCHOOL_B: "_TTB"}

CUSTOMER = "_Test Treasury Parent"
SUPPLIER = "_Test Treasury Vendor"
HELD_SUPPLIER = "_Test Treasury Vendor On Hold"
ITEM = "_Test Treasury Fee"
PRICE_LIST = "_Test Treasury AED"

# distinct default amounts keep unrelated requests from tripping the duplicate guard
_amounts = count(1_003, 7)

USERS = {
	"cashier_a": ("treasury.cashier.a@test.local", ["Treasury Cashier"], SCHOOL_A),
	"cashier_a2": ("treasury.cashier.a2@test.local", ["Treasury Cashier"], SCHOOL_A),
	"approver_a": ("treasury.approver.a@test.local", ["Treasury Approver"], SCHOOL_A),
	"officer_a": ("treasury.officer.a@test.local", ["Treasury Officer"], SCHOOL_A),
	"approver_b": ("treasury.approver.b@test.local", ["Treasury Approver"], SCHOOL_B),
	"cashier_b": ("treasury.cashier.b@test.local", ["Treasury Cashier"], SCHOOL_B),
}


def user(key):
	return USERS[key][0]


def employee():
	return frappe.db.get_value("Employee", {"first_name": "_Test Treasury", "company": SCHOOL_A})


def cash_account(company=SCHOOL_A):
	return f"Cash - {ABBR[company]}"


def bank_account(company=SCHOOL_A):
	return f"Test Bank - {ABBR[company]}"


def ensure_fixtures():
	if frappe.flags.treasury_fixtures_ready:
		return

	frappe.set_user("Administrator")
	_ensure_fiscal_years(add_days(nowdate(), -60), add_days(nowdate(), 30))

	for company, abbr in ABBR.items():
		if not frappe.db.exists("Company", company):
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": company,
					"abbr": abbr,
					"default_currency": "AED",
					"country": "United Arab Emirates",
					"create_chart_of_accounts_based_on": "Standard Template",
					"chart_of_accounts": "Standard",
					"enable_perpetual_inventory": 0,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Account", f"Test Bank - {abbr}"):
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Test Bank",
					"company": company,
					"parent_account": f"Bank Accounts - {abbr}",
					"account_type": "Bank",
					"account_currency": "AED",
				}
			).insert(ignore_permissions=True)

	if not frappe.db.exists("Customer", CUSTOMER):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": CUSTOMER,
				"customer_group": "Individual",
				"territory": "All Territories",
			}
		).insert(ignore_permissions=True)
	for name, on_hold in ((SUPPLIER, 0), (HELD_SUPPLIER, 1)):
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": "All Supplier Groups",
					"on_hold": on_hold,
					"hold_type": "All" if on_hold else None,
				}
			).insert(ignore_permissions=True)

	if not frappe.db.exists("Item", ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Price List", PRICE_LIST):
		frappe.get_doc(
			{"doctype": "Price List", "price_list_name": PRICE_LIST, "currency": "AED", "selling": 1}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Employee", {"first_name": "_Test Treasury", "company": SCHOOL_A}):
		frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "_Test Treasury",
				"last_name": "Staff",
				"gender": "Female",
				"company": SCHOOL_A,
				"status": "Active",
				"date_of_birth": "1988-04-12",
				"date_of_joining": "2019-08-25",
			}
		).insert(ignore_permissions=True)

	for email, roles, company in USERS.values():
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": email.split("@")[0],
					"send_welcome_email": 0,
					"new_password": PASSWORD,
					"roles": [{"role": r} for r in roles],
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("User Permission", {"user": email, "allow": "Company"}):
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": email,
					"allow": "Company",
					"for_value": company,
					"apply_to_all_doctypes": 1,
					"is_default": 1,
				}
			).insert(ignore_permissions=True)

	frappe.db.commit()
	frappe.flags.treasury_fixtures_ready = True


def remove_fixtures():
	"""Delete the test schools, users and parties so nothing from the suite stays on the site."""
	frappe.set_user("Administrator")
	companies = [c for c in ABBR if frappe.db.exists("Company", c)]
	emails = [email for email, *_ in USERS.values()]

	for doctype in (
		"Treasury Request",
		"Payment Entry",
		"Journal Entry",
		"Sales Invoice",
		"Purchase Invoice",
	):
		names = frappe.get_all(doctype, filters={"company": ("in", companies or [""])}, pluck="name")
		for table in frappe.get_meta(doctype).get_table_fields():
			if names:
				frappe.db.delete(table.options, {"parent": ("in", names), "parenttype": doctype})
		if names:
			frappe.db.delete(doctype, {"name": ("in", names)})
	for ledger in ("GL Entry", "Payment Ledger Entry", "Treasury Audit Log"):
		if companies and frappe.db.table_exists(ledger):
			frappe.db.delete(ledger, {"company": ("in", companies)})

	frappe.db.delete("User Permission", {"user": ("in", emails)})
	for email in emails:
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	for employee in frappe.get_all("Employee", filters={"company": ("in", companies or [""])}, pluck="name"):
		frappe.delete_doc("Employee", employee, force=True, ignore_permissions=True)
	for doctype, name in (
		("Customer", CUSTOMER),
		("Supplier", SUPPLIER),
		("Supplier", HELD_SUPPLIER),
		("Item", ITEM),
		("Price List", PRICE_LIST),
	):
		if frappe.db.exists(doctype, name):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
	for company in companies:
		frappe.delete_doc("Company", company, force=True, ignore_permissions=True)

	frappe.db.commit()
	frappe.flags.treasury_fixtures_ready = False


class TreasuryTestCase(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		ensure_fixtures()
		super().setUpClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_user(self, key):
		frappe.set_user(user(key))

	def make_request(self, by="cashier_a", submit=False, **values):
		self.as_user(by)
		data = {
			"doctype": "Treasury Request",
			"request_type": "Receipt",
			"company": SCHOOL_A,
			"posting_date": nowdate(),
			"party_type": "Customer",
			"party": CUSTOMER,
			"mode_of_payment": "Cash",
			"account": cash_account(),
			"amount": next(_amounts),
			"purpose": "Term 1 tuition instalment",
		}
		data.update(values)
		if data.get("against_invoice"):
			data["against_doctype"] = (
				"Sales Invoice" if data["request_type"] == "Receipt" else "Purchase Invoice"
			)
		doc = frappe.get_doc(data).insert()
		if submit:
			doc.submit_for_approval()
		return doc

	def make_sales_invoice(self, amount, company=SCHOOL_A):
		frappe.set_user("Administrator")
		abbr = ABBR[company]
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": company,
				"customer": CUSTOMER,
				"posting_date": nowdate(),
				"due_date": nowdate(),
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": PRICE_LIST,
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"debit_to": f"Debtors - {abbr}",
				"disable_rounded_total": 1,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": amount,
						"income_account": f"Sales - {abbr}",
						"cost_center": f"Main - {abbr}",
					}
				],
			}
		)
		invoice.insert(ignore_permissions=True)
		invoice.submit()
		return invoice

	def approve(self, request, by="approver_a", remarks=None):
		self.as_user(by)
		request.reload()
		return request.approve(remarks)
