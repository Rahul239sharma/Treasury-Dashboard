import frappe
from frappe import _

from treasury_dashboard.treasury.constants import (
	ROLE_APPROVER,
	ROLE_CASHIER,
	ROLE_OFFICER,
	SUPER_ROLES,
	TREASURY_ROLES,
	VIEWER_ROLES,
)

RESTRICTION_DOCTYPES = (None, "", "Treasury Request")


def get_roles(user=None):
	return set(frappe.get_roles(user or frappe.session.user))


def is_super(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(get_roles(user) & set(SUPER_ROLES))


def can_access_dashboard(user=None):
	roles = get_roles(user)
	return bool(roles & set(TREASURY_ROLES + VIEWER_ROLES + SUPER_ROLES))


def assert_dashboard_access(user=None):
	if not can_access_dashboard(user):
		frappe.throw(_("You do not have access to the Treasury Dashboard."), frappe.PermissionError)


def has_any_role(roles, user=None):
	return is_super(user) or bool(get_roles(user) & set(roles))


def can_create_request(user=None):
	return has_any_role((ROLE_CASHIER, ROLE_OFFICER), user)


def can_decide(user=None):
	return has_any_role((ROLE_APPROVER,), user)


def can_manage(user=None):
	return has_any_role((ROLE_OFFICER,), user)


def get_permitted_companies(user=None):
	"""Companies the user may see on the dashboard, in tree order.

	Respects Company user permissions (descendants are already expanded by Frappe),
	so a user restricted to a holding company sees every school under it.
	"""
	user = user or frappe.session.user
	if not can_access_dashboard(user):
		return []

	companies = frappe.get_all(
		"Company",
		fields=["name", "abbr", "default_currency", "is_group", "parent_company", "lft", "rgt", "country"],
		order_by="lft asc",
	)

	restricted = {
		row.doc
		for row in frappe.permissions.get_user_permissions(user).get("Company", [])
		if row.get("applicable_for") in RESTRICTION_DOCTYPES
	}
	if not restricted:
		return companies

	return [c for c in companies if c.name in restricted]


def get_permitted_company_names(user=None):
	return [c.name for c in get_permitted_companies(user)]


def assert_company_access(company, user=None):
	if not company or company not in get_permitted_company_names(user):
		frappe.throw(
			_("You are not permitted to access treasury records of {0}.").format(frappe.bold(company or "-")),
			frappe.PermissionError,
		)


def resolve_companies(company=None, user=None):
	"""Expand a company filter into the concrete list of permitted companies.

	No filter -> every permitted company. A group company -> its permitted descendants.
	"""
	permitted = get_permitted_companies(user)
	if not company:
		return [c.name for c in permitted]

	assert_company_access(company, user)
	selected = next(c for c in permitted if c.name == company)
	if not selected.is_group:
		return [company]

	return [c.name for c in permitted if selected.lft <= c.lft and c.rgt <= selected.rgt]


def get_capabilities(user=None):
	return {
		"can_create": can_create_request(user),
		"can_approve": can_decide(user),
		"can_manage": can_manage(user),
		"is_viewer_only": not (can_create_request(user) or can_decide(user) or can_manage(user)),
	}
