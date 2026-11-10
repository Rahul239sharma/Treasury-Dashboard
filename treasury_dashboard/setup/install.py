import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from treasury_dashboard.treasury.constants import ROLE_APPROVER, ROLE_CASHIER, ROLE_OFFICER, TREASURY_ROLES

CUSTOM_FIELDS = {
	"Payment Entry": [
		{
			"fieldname": "treasury_request",
			"label": "Treasury Request",
			"fieldtype": "Link",
			"options": "Treasury Request",
			"insert_after": "reference_date",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
			"in_standard_filter": 1,
		}
	]
}

# standard doctypes the treasury roles need to read so the workbench, link fields
# and ERPNext's own payment logic work for them; company user permissions still apply
READ_ACCESS = (
	"Company",
	"Account",
	"Mode of Payment",
	"Customer",
	"Supplier",
	"Employee",
	"Payment Entry",
	"Journal Entry",
	"Sales Invoice",
	"Purchase Invoice",
	"Bank Account",
	"Number Card",
)

# officers post the approved draft entries; nobody gets cancel through this app
OFFICER_PAYMENT_ENTRY_RIGHTS = ("write", "create", "submit")


def after_install():
	setup()
	load_sample_data()


def after_setup_wizard(args=None):
	# runs as one of the wizard's own stages, before setup_complete is flagged
	load_sample_data(wizard_done=True)


def load_sample_data(wizard_done=False):
	"""Load the Ghaf sample schools so a fresh install opens with real-looking data.

	Runs once the ERPNext setup wizard is complete (straight after install, or when the
	wizard finishes). Skip it with `bench --site <site> set-config treasury_skip_sample_data 1`.
	"""
	if frappe.conf.get("treasury_skip_sample_data"):
		return
	if not wizard_done and not frappe.db.get_single_value("System Settings", "setup_complete"):
		print("Treasury Dashboard: sample data will load when the setup wizard is completed.")
		return

	from treasury_dashboard.setup.demo import create_demo_data

	print("Treasury Dashboard: loading sample data for Ghaf Education Holding (a few minutes)…")
	create_demo_data()


def after_migrate():
	setup()


def setup():
	from treasury_dashboard.setup.workspace import setup_workspaces

	create_roles()
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True, update=True)
	grant_standard_permissions()
	setup_workspaces()
	frappe.clear_cache()


def create_roles():
	for role in TREASURY_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def grant_standard_permissions():
	for doctype in READ_ACCESS:
		for role in (ROLE_CASHIER, ROLE_OFFICER, ROLE_APPROVER):
			_ensure(doctype, role, "read")
			_ensure(doctype, role, "report")

	for ptype in OFFICER_PAYMENT_ENTRY_RIGHTS:
		_ensure("Payment Entry", ROLE_OFFICER, ptype)


def _ensure(doctype, role, ptype):
	rule = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}, ["name", ptype]
	)
	if not rule:
		add_permission(doctype, role, 0, ptype)
	elif not rule[1]:
		update_permission_property(doctype, role, 0, ptype, 1)


def before_uninstall():
	from treasury_dashboard.setup.workspace import restore_hidden_workspaces

	restore_hidden_workspaces()
	frappe.db.delete("Custom DocPerm", {"role": ("in", TREASURY_ROLES)})
	for doctype, fields in CUSTOM_FIELDS.items():
		for field in fields:
			frappe.db.delete("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]})
	frappe.clear_cache()
