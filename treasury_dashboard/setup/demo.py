"""Sample data for a two-school group in Dubai.

    bench --site <site> execute treasury_dashboard.setup.demo.create_demo_data

Builds Ghaf Education Holding with two schools on the ERPNext U.A.E chart of
accounts, then books roughly one academic term of activity ending today: Term 1
fee invoices and collections, supplier bills with 5% VAT, WPS payroll, cash
deposits and bank sweeps, staff custody and settlements, and Treasury Requests in
every status. Dates are relative to the day the script runs. Safe to re-run; any
school that already has invoices is left alone.
"""

import random

import frappe
from erpnext.accounts.utils import get_balance_on, get_fiscal_year
from frappe.utils import add_days, add_months, flt, get_first_day, getdate, nowdate

from treasury_dashboard.setup.workspace import make_treasury_default_workspace

DEMO_PASSWORD = "Ghaf@2026"
TIME_ZONE = "Asia/Dubai"
SELLING_PRICE_LIST = "Fee Schedule AED"
BUYING_PRICE_LIST = "Supplier Rates AED"

GROUP = {"name": "Ghaf Education Holding", "abbr": "GEH"}

SCHOOLS = [
	{
		"name": "Ghaf British School Al Barsha",
		"abbr": "GBS",
		"key": "barsha",
		"banks": {
			"operating": ("Emirates NBD", "026", "Operating", "1015378420014417"),
			"collection": ("Mashreq", "033", "Fee Collection", "0197731004527731"),
		},
		"opening": {
			"operating": 1_850_000,
			"collection": 642_500,
			"safe": 45_000,
			"counter": 8_500,
			"petty": 5_000,
		},
		"payroll": 132_600,
		"fee_range": (14_850, 21_450),
		"parents": [
			("Ahmed Al Mansoori", 2),
			("Fatima Al Hashimi", 1),
			("James Whitfield", 2),
			("Priya Nair", 1),
			("Omar Farouk", 1),
			("Sophie Laurent", 1),
			("Rajesh Iyer", 2),
			("Aisha Rahman", 1),
			("Daniel Kowalski", 1),
			("Noura Al Shamsi", 2),
			("Hassan Siddiqui", 1),
			("Emily Carter", 1),
			("Khalifa Al Muhairi", 3),
			("Rebecca Hughes", 1),
			("Faisal Qureshi", 2),
			("Hana Yamamoto", 1),
			("Mansour Al Dhaheri", 2),
			("Olivia Grant", 1),
			("Karim Benali", 1),
			("Deepa Krishnan", 2),
			("Thomas Mueller", 1),
			("Reem Al Blooshi", 2),
			("Samuel Adeyemi", 1),
			("Zainab Hussain", 1),
		],
		"sponsor": "Al Khaleej Logistics LLC",
		"staff": [
			("Hamad", "Al Ketbi", "Male", "Administration Officer"),
			("Sara", "Thomas", "Female", "Head of Science"),
			("Imran", "Qureshi", "Male", "Facilities Supervisor"),
			("Laura", "Bennett", "Female", "PE Coordinator"),
		],
		"users": {
			"cashier": ("cashier.barsha", "Ayesha", "Khan"),
			"approver": ("approver.barsha", "Omar", "Al Hammadi"),
		},
	},
	{
		"name": "Ghaf International Academy Mirdif",
		"abbr": "GIA",
		"key": "mirdif",
		"banks": {
			"operating": ("Abu Dhabi Commercial Bank", "003", "Operating", "0004420118734420"),
			"collection": ("Dubai Islamic Bank", "024", "Fee Collection", "0310865520043108"),
		},
		"opening": {
			"operating": 1_240_000,
			"collection": 408_000,
			"safe": 32_000,
			"counter": 6_000,
			"petty": 4_000,
		},
		"payroll": 86_300,
		"fee_range": (9_800, 15_600),
		"parents": [
			("Mohammed Al Falasi", 2),
			("Anjali Sharma", 1),
			("Yousef Haddad", 1),
			("Maria Santos", 2),
			("Abdullah Al Marri", 1),
			("Chen Wei", 1),
			("Layla Ibrahim", 1),
			("Arjun Pillai", 2),
			("Ruth Mensah", 1),
			("Saeed Al Qasimi", 1),
			("Elena Petrova", 1),
			("Tariq Mahmood", 2),
			("Hessa Al Ali", 2),
			("Ravi Subramanian", 1),
			("Amira Khalil", 1),
			("Jonathan Reyes", 2),
			("Meera Joshi", 1),
			("Bilal Chaudhry", 2),
			("Salma Al Nuaimi", 1),
			("Kofi Asante", 1),
			("Natalia Ivanova", 1),
			("Imran Sheikh", 2),
			("Dana Al Zaabi", 1),
			("Lucas Moreau", 1),
		],
		"sponsor": "Gulf Horizon Engineering LLC",
		"staff": [
			("Nadia", "Haddad", "Female", "Office Manager"),
			("Vikram", "Menon", "Male", "Head of Primary"),
			("Khalid", "Al Naqbi", "Male", "Transport Coordinator"),
			("Grace", "Okafor", "Female", "Activities Lead"),
		],
		"users": {
			"cashier": ("cashier.mirdif", "Joseph", "Fernandes"),
			"approver": ("approver.mirdif", "Mariam", "Al Suwaidi"),
		},
	},
]

GROUP_USER = ("treasury.manager", "Rashid", "Al Mazrouei")
EMAIL_DOMAIN = "ghaf-edu.ae"

SUPPLIERS = [
	# name, group, item, expense account, monthly amount range
	(
		"DEWA - Dubai Electricity and Water Authority",
		"Utilities",
		"UTIL-DEWA",
		"Utilities - Electricity & Water",
		(24_000, 31_000),
	),
	(
		"Desert Rose School Transport LLC",
		"School Services",
		"SRV-TRANSPORT",
		"Student Transport",
		(38_000, 44_000),
	),
	(
		"Golden Spoon Catering Services LLC",
		"School Services",
		"SRV-CATERING",
		"Catering Services",
		(16_000, 22_000),
	),
	(
		"Crescent Facility Management LLC",
		"School Services",
		"SRV-FM",
		"Facilities & Maintenance",
		(15_000, 20_000),
	),
	(
		"Bright Minds Stationery Trading LLC",
		"School Supplies",
		"SUP-STATIONERY",
		"Learning Resources & Stationery",
		(5_000, 9_000),
	),
	(
		"Nexus EdTech Solutions FZ-LLC",
		"School Services",
		"SRV-IT",
		"IT & Software Subscriptions",
		(6_200, 7_400),
	),
]

GRADES = [
	"FS2",
	"Year 1",
	"Year 2",
	"Year 3",
	"Year 4",
	"Year 5",
	"Year 6",
	"Year 7",
	"Year 8",
	"Year 9",
	"Year 10",
	"Year 11",
]


def create_demo_data():
	frappe.flags.in_demo = True
	rng = random.Random(2026)
	today = getdate(nowdate())
	term_start = add_days(today, -82)

	_ensure_site_prerequisites()
	_set_locale()
	_ensure_fiscal_years(add_days(term_start, -200), add_days(today, 60))
	_masters()

	_company(GROUP["name"], GROUP["abbr"], is_group=1)
	_group_accounts(GROUP["name"], GROUP["abbr"])
	_disable_unused_ledgers(GROUP["abbr"])
	for school in SCHOOLS:
		_company(school["name"], school["abbr"], parent=GROUP["name"])
		_school_setup(school)

	_users()
	frappe.db.commit()

	for school in SCHOOLS:
		if not frappe.db.exists("Sales Invoice", {"company": school["name"]}):
			_book_term(school, rng, term_start, today)
			frappe.db.commit()
		if not frappe.db.exists("Treasury Request", {"company": school["name"]}):
			_treasury_requests(school, rng, today)
			frappe.db.commit()
		print(f"{school['name']}: ready")

	frappe.set_user("Administrator")
	frappe.db.commit()


def reset_demo_activity():
	"""Remove every transaction booked for the demo schools so create_demo_data can rebuild them.

	Masters (companies, accounts, parties, users) are kept.
	"""
	companies = [s["name"] for s in SCHOOLS] + [GROUP["name"]]
	for doctype in (
		"Treasury Request",
		"Payment Entry",
		"Journal Entry",
		"Sales Invoice",
		"Purchase Invoice",
	):
		names = frappe.get_all(doctype, filters={"company": ("in", companies)}, pluck="name")
		if not names:
			continue
		for table in frappe.get_meta(doctype).get_table_fields():
			frappe.db.delete(table.options, {"parent": ("in", names), "parenttype": doctype})
		frappe.db.delete("Comment", {"reference_doctype": doctype, "reference_name": ("in", names)})
		frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ("in", names)})
		frappe.db.delete(doctype, {"name": ("in", names)})

	for ledger in ("GL Entry", "Payment Ledger Entry", "Advance Payment Ledger Entry"):
		if frappe.db.table_exists(ledger):
			frappe.db.delete(ledger, {"company": ("in", companies)})
	frappe.db.delete("Treasury Audit Log", {"company": ("in", companies)})
	frappe.db.commit()


# --------------------------------------------------------------------- setup


def _ensure_site_prerequisites():
	# Some v15 sites lose ERPNext's Contact/Address fields after a v16 patch; invoices need them.
	if not frappe.db.has_column("Contact", "is_billing_contact"):
		from erpnext.setup.install import create_address_and_contact_custom_fields

		create_address_and_contact_custom_fields()
	for mode, mode_type in (
		("Cash", "Cash"),
		("Cheque", "Bank"),
		("Wire Transfer", "Bank"),
		("Bank Draft", "Bank"),
		("Credit Card", "Bank"),
	):
		if not frappe.db.exists("Mode of Payment", mode):
			frappe.get_doc(
				{"doctype": "Mode of Payment", "mode_of_payment": mode, "type": mode_type, "enabled": 1}
			).insert(ignore_permissions=True)


def _set_locale():
	settings = frappe.get_single("System Settings")
	if settings.time_zone != TIME_ZONE or settings.number_format != "#,###.##":
		settings.time_zone = TIME_ZONE
		settings.number_format = "#,###.##"
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)
	frappe.db.set_single_value("Global Defaults", "default_currency", "AED")
	# AED reads better as "AED" than the Arabic glyph in mixed English screens and prints
	frappe.db.set_value("Currency", "AED", {"symbol": "AED", "number_format": "#,###.##"})


def _ensure_fiscal_years(start, end):
	cursor = getdate(start)
	while cursor <= getdate(end):
		try:
			get_fiscal_year(cursor)
		except Exception:
			year_start = getdate(f"{cursor.year if cursor.month >= 4 else cursor.year - 1}-04-01")
			year_end = add_days(add_months(year_start, 12), -1)
			frappe.get_doc(
				{
					"doctype": "Fiscal Year",
					"year": f"{year_start.year}-{year_end.year}",
					"year_start_date": year_start,
					"year_end_date": year_end,
				}
			).insert(ignore_permissions=True)
		cursor = add_months(cursor, 1)


def _masters():
	_insert_if_missing("Territory", "United Arab Emirates", parent_territory="All Territories", is_group=1)
	_insert_if_missing("Territory", "Dubai", parent_territory="United Arab Emirates")
	_insert_if_missing("Customer Group", "Parents", parent_customer_group="All Customer Groups")
	_insert_if_missing("Customer Group", "Corporate Sponsors", parent_customer_group="All Customer Groups")
	for group in ("Utilities", "School Services", "School Supplies"):
		_insert_if_missing("Supplier Group", group, parent_supplier_group="All Supplier Groups")
	_insert_if_missing("Item Group", "School Fees", parent_item_group="All Item Groups")

	for name, selling in ((SELLING_PRICE_LIST, 1), (BUYING_PRICE_LIST, 0)):
		if not frappe.db.exists("Price List", name):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": name,
					"currency": "AED",
					"selling": selling,
					"buying": int(not selling),
					"enabled": 1,
				}
			).insert(ignore_permissions=True)

	items = [
		("FEE-TUITION-T1", "Tuition Fee - Term 1", "School Fees"),
		("FEE-TRANSPORT-T1", "School Transport Fee - Term 1", "School Fees"),
		("FEE-REGISTRATION", "Registration & Re-enrolment Fee", "School Fees"),
	] + [(code, code.split("-", 1)[1].title() + " Service", "Services") for _, _, code, _, _ in SUPPLIERS]
	names = {
		"UTIL-DEWA": "Electricity & Water (DEWA)",
		"SRV-TRANSPORT": "School Bus Service",
		"SRV-CATERING": "Canteen & Catering Service",
		"SRV-FM": "Facility Management Service",
		"SUP-STATIONERY": "Classroom Stationery & Resources",
		"SRV-IT": "LMS & IT Support Subscription",
	}
	for code, name, group in items:
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": names.get(code, name),
					"item_group": group,
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"include_item_in_manufacturing": 0,
				}
			).insert(ignore_permissions=True)


def _company(name, abbr, parent=None, is_group=0):
	if frappe.db.exists("Company", name):
		return
	frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": name,
			"abbr": abbr,
			"default_currency": "AED",
			"country": "United Arab Emirates",
			"is_group": is_group,
			"parent_company": parent,
			"create_chart_of_accounts_based_on": "Standard Template",
			"chart_of_accounts": "U.A.E - Chart of Accounts",
			"enable_perpetual_inventory": 0,
		}
	).insert(ignore_permissions=True)


def _group_accounts(company, abbr):
	"""Accounts every school needs; created on the holding so schools inherit them."""
	acc = lambda *a, **k: _account(company, abbr, *a, **k)  # noqa: E731

	acc("Fee Counter Cash", "Cash in Hand", "Cash")
	acc("Parent Fee Receivable", "Accounts Receivable", "Receivable")
	acc("Staff Custody", "Accounts Receivable", "Receivable")
	acc("Input VAT 5%", "Duties and Taxes", "Tax", tax_rate=5)
	acc("Temporary Opening", "Closing Accounts", "Temporary")
	acc("Round Off", "Other Charges", "Round Off")

	acc("School Fee Income", "Revenue", is_group=1)
	for name in ("Tuition Fees", "Transport Fees", "Registration & Enrolment Fees"):
		acc(name, "School Fee Income", "Income Account")

	acc("School Operating Expenses", "Expenses", is_group=1)
	for name in (
		"Teaching & Staff Salaries",
		"Utilities - Electricity & Water",
		"Student Transport",
		"Catering Services",
		"Facilities & Maintenance",
		"Learning Resources & Stationery",
		"IT & Software Subscriptions",
		"Educational Trips & Activities",
	):
		acc(name, "School Operating Expenses", "Expense Account")


def _school_setup(school):
	company, abbr = school["name"], school["abbr"]
	# each school banks separately, so it keeps its own bank ledgers
	frappe.db.set_value("Company", company, "allow_account_creation_against_child_company", 1)
	frappe.clear_document_cache("Company", company)
	_group_accounts(company, abbr)

	_disable_unused_ledgers(abbr)

	bank_accounts = {}
	for role, (bank, code, label, number) in school["banks"].items():
		ledger = _account(company, abbr, f"{bank} - {label} {number[-4:]}", "Banks", "Bank")
		bank_accounts[role] = ledger
		_insert_if_missing("Bank", bank, swift_number=None)
		if not frappe.db.exists("Bank Account", {"account": ledger}):
			frappe.get_doc(
				{
					"doctype": "Bank Account",
					"account_name": f"{school['abbr']} {label}",
					"bank": bank,
					"account": ledger,
					"company": company,
					"is_company_account": 1,
					"is_default": int(role == "operating"),
					"bank_account_no": number,
					"iban": _iban(code, number),
				}
			).insert(ignore_permissions=True)

	frappe.db.set_value(
		"Company",
		company,
		{
			"default_receivable_account": f"Parent Fee Receivable - {abbr}",
			"default_payable_account": f"Trade Payable - {abbr}",
			"default_cash_account": f"Main Safe - {abbr}",
			"default_bank_account": bank_accounts["operating"],
			"default_income_account": f"Tuition Fees - {abbr}",
			"default_expense_account": f"Facilities & Maintenance - {abbr}",
			"round_off_account": f"Round Off - {abbr}",
			"round_off_cost_center": f"Main - {abbr}",
			"cost_center": f"Main - {abbr}",
		},
	)

	mode_accounts = {
		"Cash": f"Fee Counter Cash - {abbr}",
		"Cheque": bank_accounts["collection"],
		"Wire Transfer": bank_accounts["operating"],
		"Bank Draft": bank_accounts["operating"],
		"Credit Card": f"Visa & Master Credit Cards - {abbr}",
	}
	for mode, account in mode_accounts.items():
		doc = frappe.get_doc("Mode of Payment", mode)
		if not any(row.company == company for row in doc.accounts):
			doc.append("accounts", {"company": company, "default_account": account})
			doc.save(ignore_permissions=True)

	school["_accounts"] = {
		"operating": bank_accounts["operating"],
		"collection": bank_accounts["collection"],
		"safe": f"Main Safe - {abbr}",
		"counter": f"Fee Counter Cash - {abbr}",
		"petty": f"Petty Cash - Administration - {abbr}",
		"card": f"Visa & Master Credit Cards - {abbr}",
		"receivable": f"Parent Fee Receivable - {abbr}",
		"payable": f"Trade Payable - {abbr}",
		"custody": f"Staff Custody - {abbr}",
		"vat": f"Input VAT 5% - {abbr}",
		"opening": f"Temporary Opening - {abbr}",
		"cost_center": f"Main - {abbr}",
	}

	_parties(school)
	_employees(school)


def _disable_unused_ledgers(abbr):
	"""Template ledgers a school group does not use; keeps balance breakdowns readable."""
	for ledger in (
		"PayPal Account",
		"Gateway Credit Cards",
		"Manual Visa & Master Cards",
		"Main Safe - Foreign Currency",
		"Banks Current Accounts",
		"Petty Cash - Others",
	):
		name = f"{ledger} - {abbr}"
		if not frappe.db.exists("Account", name):
			continue
		frappe.db.delete("Mode of Payment Account", {"default_account": name})
		for field in ("default_cash_account", "default_bank_account"):
			frappe.db.set_value(
				"Company",
				{field: name},
				field,
				f"Main Safe - {abbr}" if field == "default_cash_account" else None,
			)
		frappe.db.set_value("Account", name, "disabled", 1)


def _parties(school):
	for name, _children in school["parents"]:
		_customer(name, "Parents", "Individual")
	_customer(school["sponsor"], "Corporate Sponsors", "Company")
	for name, group, *_ in SUPPLIERS:
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": group,
					"supplier_type": "Company",
					"country": "United Arab Emirates",
				}
			).insert(ignore_permissions=True)


def _customer(name, group, customer_type):
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_group": group,
				"customer_type": customer_type,
				"territory": "Dubai",
			}
		).insert(ignore_permissions=True)


def _employees(school):
	school["_employees"] = []
	for i, (first, last, gender, designation) in enumerate(school["staff"]):
		existing = frappe.db.get_value(
			"Employee", {"first_name": first, "last_name": last, "company": school["name"]}
		)
		if not existing:
			_insert_if_missing("Designation", designation)
			existing = (
				frappe.get_doc(
					{
						"doctype": "Employee",
						"first_name": first,
						"last_name": last,
						"gender": gender,
						"company": school["name"],
						"designation": designation,
						"status": "Active",
						"date_of_birth": f"{1979 + i * 3}-0{i + 3}-14",
						"date_of_joining": f"{2016 + i}-08-2{i}",
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		school["_employees"].append(existing)


def _users():
	def make(login, first, last, roles, companies):
		email = f"{login}@{EMAIL_DOMAIN}"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first,
					"last_name": last,
					"send_welcome_email": 0,
					"user_type": "System User",
					"time_zone": TIME_ZONE,
					"new_password": DEMO_PASSWORD,
					"roles": [{"role": role} for role in roles],
				}
			).insert(ignore_permissions=True)
		make_treasury_default_workspace(email)
		for i, company in enumerate(companies):
			if not frappe.db.exists(
				"User Permission", {"user": email, "allow": "Company", "for_value": company}
			):
				frappe.get_doc(
					{
						"doctype": "User Permission",
						"user": email,
						"allow": "Company",
						"for_value": company,
						"apply_to_all_doctypes": 1,
						"is_default": int(i == 0),
					}
				).insert(ignore_permissions=True)
		return email

	for school in SCHOOLS:
		users = school["users"]
		school["_cashier"] = make(*users["cashier"], ["Treasury Cashier"], [school["name"]])
		school["_approver"] = make(*users["approver"], ["Treasury Approver"], [school["name"]])
		school["_manager"] = make(*GROUP_USER, ["Treasury Officer", "Treasury Approver"], [GROUP["name"]])


# ------------------------------------------------------------------ activity


def _book_term(school, rng, term_start, today):
	a = school["_accounts"]
	company = school["name"]
	fy_start = getdate(get_fiscal_year(term_start, company=company)[1])

	_je(
		school,
		"Opening Entry",
		fy_start,
		[
			(a["operating"], school["opening"]["operating"], 0),
			(a["collection"], school["opening"]["collection"], 0),
			(a["safe"], school["opening"]["safe"], 0),
			(a["counter"], school["opening"]["counter"], 0),
			(a["petty"], school["opening"]["petty"], 0),
			(a["opening"], 0, sum(school["opening"].values())),
		],
		remark="Opening cash and bank balances",
		is_opening=True,
	)

	invoices = _fee_invoices(school, rng, term_start)
	_fee_collections(school, rng, invoices, term_start, today)
	_re_enrolment(school, rng, term_start, today)

	bills = _supplier_bills(school, rng, term_start, today)
	_supplier_payments(school, rng, bills, today)

	_payroll(school, term_start, today)
	_cash_management(school, rng, term_start, today)
	_custody(school, rng, term_start, today)


def _fee_invoices(school, rng, term_start):
	a = school["_accounts"]
	invoices = []
	low, high = school["fee_range"]
	for idx, (parent, children) in enumerate(school["parents"]):
		items = []
		for child in range(children):
			grade = GRADES[(idx * 3 + child * 5) % len(GRADES)]
			fee = round(rng.uniform(low, high) / 50) * 50
			items.append(
				_fee_line("FEE-TUITION-T1", fee, f"Tuition Fee - Term 1 · {grade}", a, "Tuition Fees", school)
			)
			if rng.random() < 0.45:
				items.append(
					_fee_line(
						"FEE-TRANSPORT-T1",
						2_350,
						f"School Transport - Term 1 · {grade}",
						a,
						"Transport Fees",
						school,
					)
				)
		invoices.append(_sales_invoice(school, parent, add_days(term_start, rng.randint(0, 4)), items))

	sponsored = [
		_fee_line(
			"FEE-TUITION-T1",
			18_400,
			"Tuition Fee - Term 1 · 4 sponsored students (staff education allowance)",
			a,
			"Tuition Fees",
			school,
			qty=4,
		)
	]
	invoices.append(_sales_invoice(school, school["sponsor"], add_days(term_start, 6), sponsored))
	return invoices


def _fee_line(item, rate, description, a, income, school, qty=1):
	return {
		"item_code": item,
		"description": description,
		"qty": qty,
		"rate": rate,
		"income_account": f"{income} - {school['abbr']}",
		"cost_center": a["cost_center"],
	}


def _fee_collections(school, rng, invoices, term_start, today):
	unpaid = []
	modes = ["Wire Transfer", "Wire Transfer", "Cheque", "Cheque", "Credit Card", "Cash"]

	for i, invoice in enumerate(invoices):
		profile = i % 6
		if profile == 5 or i == len(invoices) - 2:
			unpaid.append(invoice.name)
			continue

		instalments = 2 if profile == 3 else 1
		remaining = flt(invoice.outstanding_amount)
		for n in range(instalments):
			amount = remaining if n == instalments - 1 else round(remaining / 2 / 50) * 50
			if profile == 4 and n == 0:
				amount = round(remaining * 0.6 / 50) * 50
			remaining -= amount
			posted = add_days(term_start, rng.randint(8 + n * 30, 34 + n * 30))
			posted = min(posted, add_days(today, -1))
			mode = modes[(i + n) % len(modes)]
			if mode == "Cash" and amount > 9_000:
				mode = "Credit Card"
			_receipt(school, rng, invoice, amount, posted, mode, today)

		if profile == 4:
			unpaid.append(invoice.name)
	return unpaid


def _re_enrolment(school, rng, term_start, today):
	"""Re-enrolment deposits for next year, mostly paid in cash at the fee counter."""
	a = school["_accounts"]
	for idx, (parent, _children) in enumerate(school["parents"][:9]):
		billed = add_days(term_start, 38 + idx * 3)
		if billed >= today:
			break
		line = _fee_line(
			"FEE-REGISTRATION",
			1_050,
			"Re-enrolment deposit 2027-28",
			a,
			"Registration & Enrolment Fees",
			school,
		)
		invoice = _sales_invoice(school, parent, billed, [line])
		paid = min(add_days(billed, rng.randint(0, 3)), add_days(today, -1))
		_receipt(school, rng, invoice, 1_050, paid, "Cash" if idx % 3 else "Credit Card", today)


def _receipt(school, rng, invoice, amount, posted, mode, today):
	a = school["_accounts"]
	account = {
		"Cash": a["counter"],
		"Cheque": a["collection"],
		"Wire Transfer": a["operating"],
		"Credit Card": a["card"],
	}[mode]
	ref_no, ref_date = _reference(rng, mode, posted, school)
	if mode == "Cheque" and rng.random() < 0.35:
		ref_date = add_days(posted, rng.choice([15, 30, 45]))
	_pe(
		school,
		"Receive",
		posted,
		amount,
		mode,
		party_type="Customer",
		party=invoice.customer,
		paid_from=a["receivable"],
		paid_to=account,
		reference_no=ref_no,
		reference_date=ref_date,
		invoice=invoice,
	)


def _supplier_bills(school, rng, term_start, today):
	bills = []
	month = get_first_day(term_start)
	while month <= today:
		for supplier, _group, item, expense, (low, high) in SUPPLIERS:
			if item == "SUP-STATIONERY" and rng.random() < 0.4:
				continue
			posted = max(add_days(month, rng.randint(1, 6)), term_start)
			if posted > today:
				continue
			amount = round(rng.uniform(low, high), 2)
			bills.append(
				_purchase_invoice(
					school,
					supplier,
					posted,
					item,
					amount,
					f"{expense} - {school['abbr']}",
					bill_no=f"{supplier.split()[0][:4].upper()}/{posted.strftime('%y%m')}/{rng.randint(1000, 9999)}",
				)
			)
		month = add_months(month, 1)
	return bills


def _supplier_payments(school, rng, bills, today):
	a = school["_accounts"]
	unpaid = []
	for bill in bills:
		due = getdate(add_days(bill.posting_date, rng.randint(12, 24)))
		if due >= add_days(today, -2):
			unpaid.append(bill.name)
			continue
		mode = "Cheque" if "DEWA" not in bill.supplier and rng.random() < 0.2 else "Wire Transfer"
		ref_no, ref_date = _reference(rng, mode, due, school)
		_pe(
			school,
			"Pay",
			due,
			flt(bill.outstanding_amount),
			mode,
			party_type="Supplier",
			party=bill.supplier,
			paid_from=a["operating"],
			paid_to=a["payable"],
			reference_no=ref_no,
			reference_date=ref_date,
			invoice=bill,
		)
	return unpaid


def _payroll(school, term_start, today):
	a = school["_accounts"]
	month = get_first_day(term_start)
	while month <= today:
		pay_day = add_days(month, 27)
		if term_start <= pay_day <= today:
			label = pay_day.strftime("%B %Y")
			_je(
				school,
				"Bank Entry",
				pay_day,
				[
					(f"Teaching & Staff Salaries - {school['abbr']}", school["payroll"], 0),
					(a["operating"], 0, school["payroll"]),
				],
				cheque_no=f"WPS-SIF-{pay_day.strftime('%Y%m')}-{school['abbr']}",
				remark=f"{label} salaries via WPS",
				title=f"WPS payroll {label}",
			)
		month = add_months(month, 1)


def _cash_management(school, rng, term_start, today):
	a = school["_accounts"]
	day = add_days(term_start, 12)
	while day < today:
		on_hand = get_balance_on(a["counter"], day, company=school["name"])
		amount = min(round(rng.uniform(5_500, 12_500) / 100) * 100, round((on_hand - 1_500) / 100) * 100)
		if amount < 1_000:
			day = add_days(day, 5)
			continue
		_pe(
			school,
			"Internal Transfer",
			day,
			amount,
			"Cash",
			paid_from=a["counter"],
			paid_to=a["collection"],
			reference_no=f"DEP-{day.strftime('%d%m')}-{rng.randint(100, 999)}",
			reference_date=day,
			remarks="Fee counter cash deposited at branch",
		)
		day = add_days(day, rng.randint(8, 12))

	day = add_days(term_start, 20)
	while day < today:
		available = get_balance_on(a["collection"], day, company=school["name"]) - 150_000
		amount = min(round(rng.uniform(120_000, 240_000) / 1000) * 1000, round(available / 1000) * 1000)
		if amount < 20_000:
			day = add_days(day, 7)
			continue
		_je(
			school,
			"Contra Entry",
			day,
			[(a["operating"], amount, 0), (a["collection"], 0, amount)],
			cheque_no=f"SWEEP-{day.strftime('%y%m%d')}",
			remark="Sweep from fee collection account to operating account",
			title="Fee collection sweep",
		)
		day = add_days(day, rng.randint(14, 18))


def _custody(school, rng, term_start, today):
	a = school["_accounts"]
	staff = school["_employees"]
	trips = [
		(staff[3], 3_500, "Custody - Year 6 trip to Al Shindagha Museum", 3_180),
		(staff[1], 2_000, "Custody - science lab consumables", 1_865),
		(staff[0], 1_500, "Custody - admissions open day hospitality", None),
		(staff[2], 2_800, "Custody - minor repairs, Block B", 2_800),
	]
	for i, (employee, amount, purpose, spent) in enumerate(trips):
		given = add_days(term_start, 18 + i * 14)
		if given >= today:
			break
		_pe(
			school,
			"Pay",
			given,
			amount,
			"Cash",
			party_type="Employee",
			party=employee,
			paid_from=a["safe"],
			paid_to=a["custody"],
			reference_no=None,
			reference_date=given,
			remarks=purpose,
		)
		if spent is None:
			continue

		settled = add_days(given, rng.randint(5, 9))
		if settled >= today:
			continue
		_je(
			school,
			"Journal Entry",
			settled,
			[
				(f"Educational Trips & Activities - {school['abbr']}", spent, 0),
				(a["custody"], 0, spent, "Employee", employee),
			],
			remark=f"Expense report settled against {purpose.lower()}",
			title=f"Custody settlement - {frappe.db.get_value('Employee', employee, 'employee_name')}",
		)
		if amount > spent:
			_pe(
				school,
				"Receive",
				settled,
				amount - spent,
				"Cash",
				party_type="Employee",
				party=employee,
				paid_from=a["custody"],
				paid_to=a["safe"],
				reference_no=None,
				reference_date=settled,
				remarks=f"Unspent balance returned - {purpose.lower()}",
			)

	# a fee receipt keyed in but never posted, and a supplier payment reversed after posting
	parent = school["parents"][1][0]
	_pe(
		school,
		"Receive",
		add_days(today, -2),
		1_200,
		"Cash",
		party_type="Customer",
		party=parent,
		paid_from=a["receivable"],
		paid_to=a["counter"],
		remarks="Uniform & book deposit (awaiting verification)",
		submit=False,
	)
	reversed_pe = _pe(
		school,
		"Pay",
		add_days(today, -9),
		4_725,
		"Cheque",
		party_type="Supplier",
		party=SUPPLIERS[4][0],
		paid_from=a["operating"],
		paid_to=a["payable"],
		reference_no=f"{rng.randint(100000, 999999)}",
		reference_date=add_days(today, -9),
		remarks="Advance for Term 2 workbooks",
	)
	reversed_pe.cancel()


# ---------------------------------------------------------- treasury requests


def _treasury_requests(school, rng, today):
	"""Raise requests as the school's cashier and walk them through the workflow."""
	a = school["_accounts"]
	cashier, approver, manager = school["_cashier"], school["_approver"], school["_manager"]
	unpaid = _open_documents("Sales Invoice", school["name"])
	bills = _open_documents("Purchase Invoice", school["name"])

	def raise_request(**values):
		frappe.set_user(cashier)
		doc = frappe.get_doc({"doctype": "Treasury Request", "company": school["name"], **values})
		doc.insert()
		return doc

	def as_user(user, fn, *args):
		frappe.set_user(user)
		doc = fn.__self__
		doc.reload()
		return fn(*args)

	def receipt_on(invoice, mode, amount=None, days_ago=1, purpose=None):
		ref_no, ref_date = _reference(rng, mode, add_days(today, -days_ago), school)
		return raise_request(
			request_type="Receipt",
			posting_date=add_days(today, -days_ago),
			party_type="Customer",
			party=invoice.customer,
			against_doctype="Sales Invoice",
			against_invoice=invoice.name,
			mode_of_payment=mode,
			account={"Cheque": a["collection"], "Cash": a["counter"], "Credit Card": a["card"]}.get(
				mode, a["operating"]
			),
			amount=amount or invoice.outstanding_amount,
			reference_no=ref_no,
			reference_date=ref_date,
			purpose=purpose or f"Term 1 fees - {invoice.customer}",
		)

	def payment_on(bill, days_ago=1, purpose=None):
		ref_no, ref_date = _reference(rng, "Wire Transfer", add_days(today, -days_ago), school)
		return raise_request(
			request_type="Payment",
			posting_date=add_days(today, -days_ago),
			party_type="Supplier",
			party=bill.supplier,
			against_doctype="Purchase Invoice",
			against_invoice=bill.name,
			mode_of_payment="Wire Transfer",
			account=a["operating"],
			amount=bill.outstanding_amount,
			reference_no=ref_no,
			reference_date=ref_date,
			purpose=purpose or f"{bill.supplier} - bill {bill.bill_no}",
		)

	# posted: approved, then posted by the group treasury manager
	if unpaid:
		posted = receipt_on(unpaid.pop(0), "Wire Transfer", days_ago=6)
		as_user(cashier, posted.submit_for_approval)
		entry = as_user(approver, posted.approve, "Bank credit confirmed on statement")
		frappe.set_user(manager)
		frappe.get_doc("Payment Entry", entry.name).submit()

	# approved, draft payment entry waiting for posting
	if bills:
		approved = payment_on(bills.pop(0), days_ago=3)
		as_user(cashier, approved.submit_for_approval)
		as_user(approver, approved.approve, "Within monthly budget")

	# rejected
	rejected = raise_request(
		request_type="Payment",
		posting_date=add_days(today, -4),
		party_type="Supplier",
		party=SUPPLIERS[3][0],
		mode_of_payment="Cheque",
		account=a["collection"],
		amount=18_650,
		reference_no=f"{rng.randint(100000, 999999)}",
		reference_date=add_days(today, 10),
		purpose="Emergency chiller repair - Block A (no LPO attached)",
	)
	as_user(cashier, rejected.submit_for_approval)
	as_user(
		approver, rejected.reject, "No approved LPO on file. Raise the LPO and resubmit with the quotation."
	)

	# pending approval
	if unpaid:
		receipt_on(unpaid.pop(0), "Cheque", days_ago=1).submit_for_approval()
	if bills:
		payment_on(bills.pop(0), days_ago=0).submit_for_approval()
	cash = raise_request(
		request_type="Receipt",
		posting_date=today,
		party_type="Customer",
		party=school["parents"][4][0],
		mode_of_payment="Cash",
		account=a["counter"],
		amount=750,
		purpose="Registration & re-enrolment fee for 2027-28",
	)
	cash.submit_for_approval()

	# drafts and a withdrawn request
	if unpaid:
		receipt_on(
			unpaid.pop(0), "Credit Card", amount=5_000, days_ago=0, purpose="Part payment at front desk"
		)

	withdrawn = raise_request(
		request_type="Payment",
		posting_date=add_days(today, -2),
		party_type="Supplier",
		party=SUPPLIERS[1][0],
		mode_of_payment="Wire Transfer",
		account=a["operating"],
		amount=3_400,
		reference_no=f"FT{rng.randint(10**9, 10**10 - 1)}",
		reference_date=add_days(today, -2),
		purpose="Additional bus for sports day",
	)
	withdrawn.cancel_request("Supplier will add this to next month's invoice")

	frappe.set_user("Administrator")


# ------------------------------------------------------------------- helpers


def _open_documents(doctype, company):
	names = frappe.get_all(
		doctype,
		filters={"company": company, "docstatus": 1, "outstanding_amount": (">", 0), "is_return": 0},
		order_by="posting_date asc, name asc",
		pluck="name",
	)
	return [frappe.get_doc(doctype, name) for name in names]


def _sales_invoice(school, customer, posting_date, items):
	a = school["_accounts"]
	doc = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": school["name"],
			"customer": customer,
			"posting_date": posting_date,
			"set_posting_time": 1,
			"due_date": add_days(posting_date, 21),
			"currency": "AED",
			"conversion_rate": 1,
			"selling_price_list": SELLING_PRICE_LIST,
			"price_list_currency": "AED",
			"plc_conversion_rate": 1,
			"debit_to": a["receivable"],
			"cost_center": a["cost_center"],
			"disable_rounded_total": 1,
			"items": items,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _purchase_invoice(school, supplier, posting_date, item, amount, expense_account, bill_no):
	a = school["_accounts"]
	doc = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": school["name"],
			"supplier": supplier,
			"posting_date": posting_date,
			"set_posting_time": 1,
			"bill_no": bill_no,
			"bill_date": posting_date,
			"due_date": add_days(posting_date, 30),
			"currency": "AED",
			"conversion_rate": 1,
			"buying_price_list": BUYING_PRICE_LIST,
			"price_list_currency": "AED",
			"plc_conversion_rate": 1,
			"credit_to": a["payable"],
			"cost_center": a["cost_center"],
			"disable_rounded_total": 1,
			"items": [
				{
					"item_code": item,
					"qty": 1,
					"rate": amount,
					"expense_account": expense_account,
					"cost_center": a["cost_center"],
				}
			],
			"taxes": [
				{
					"category": "Total",
					"add_deduct_tax": "Add",
					"charge_type": "On Net Total",
					"account_head": a["vat"],
					"rate": 5,
					"description": "VAT 5%",
					"cost_center": a["cost_center"],
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _pe(
	school,
	payment_type,
	posting_date,
	amount,
	mode,
	party_type=None,
	party=None,
	paid_from=None,
	paid_to=None,
	reference_no=None,
	reference_date=None,
	invoice=None,
	remarks=None,
	submit=True,
):
	doc = frappe.new_doc("Payment Entry")
	doc.update(
		{
			"payment_type": payment_type,
			"company": school["name"],
			"posting_date": posting_date,
			"mode_of_payment": mode,
			"party_type": party_type,
			"party": party,
			"paid_from": paid_from,
			"paid_to": paid_to,
			"paid_amount": amount,
			"received_amount": amount,
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
			"reference_no": reference_no,
			"reference_date": reference_date or posting_date,
		}
	)
	if remarks:
		doc.custom_remarks = 1
		doc.remarks = remarks
	if invoice:
		doc.append(
			"references",
			{
				"reference_doctype": invoice.doctype,
				"reference_name": invoice.name,
				"total_amount": invoice.grand_total,
				"outstanding_amount": frappe.db.get_value(
					invoice.doctype, invoice.name, "outstanding_amount"
				),
				"allocated_amount": amount,
			},
		)
	if party_type:
		doc.setup_party_account_field()
		doc.set_missing_values()
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def _je(school, voucher_type, posting_date, lines, cheque_no=None, remark=None, title=None, is_opening=False):
	a = school["_accounts"]
	rows = []
	for line in lines:
		account, debit, credit, *party = line
		row = {
			"account": account,
			"debit_in_account_currency": debit,
			"credit_in_account_currency": credit,
			"cost_center": a["cost_center"],
		}
		if party:
			row.update({"party_type": party[0], "party": party[1]})
		rows.append(row)

	doc = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": voucher_type,
			"company": school["name"],
			"posting_date": posting_date,
			"cheque_no": cheque_no,
			"cheque_date": posting_date if cheque_no else None,
			"user_remark": remark,
			"title": title,
			"is_opening": "Yes" if is_opening else "No",
			"accounts": rows,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _reference(rng, mode, posted, school):
	if mode == "Cheque":
		return f"{rng.randint(100000, 999999)}", posted
	if mode == "Wire Transfer":
		return f"FT{posted.strftime('%y%j')}{rng.randint(10000, 99999)}", posted
	if mode == "Credit Card":
		return f"POS-{school['abbr']}-{rng.randint(100000, 999999)}", posted
	return None, posted


def _account(company, abbr, name, parent, account_type=None, is_group=0, tax_rate=None):
	docname = f"{name} - {abbr}"
	if frappe.db.exists("Account", docname):
		return docname
	frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": name,
			"company": company,
			"parent_account": f"{parent} - {abbr}",
			"account_type": account_type,
			"is_group": is_group,
			"account_currency": "AED",
			"tax_rate": tax_rate,
		}
	).insert(ignore_permissions=True)
	return docname


def _insert_if_missing(doctype, name, **values):
	if frappe.db.exists(doctype, name):
		return
	meta = frappe.get_meta(doctype)
	name_field = {
		"Territory": "territory_name",
		"Customer Group": "customer_group_name",
		"Supplier Group": "supplier_group_name",
		"Item Group": "item_group_name",
		"Bank": "bank_name",
		"Designation": "designation_name",
		"Salutation": "salutation",
	}.get(doctype, meta.autoname.replace("field:", "") if meta.autoname else "name")
	frappe.get_doc({"doctype": doctype, name_field: name, **values}).insert(ignore_permissions=True)


def _iban(bank_code, account_no):
	bban = f"{bank_code}{account_no}"
	digits = "".join(str(int(ch, 36)) for ch in bban + "AE00")
	return f"AE{98 - int(digits) % 97:02d}{bban}"
