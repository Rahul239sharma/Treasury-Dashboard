import frappe

from treasury_dashboard.treasury.constants import TREASURY_ROLES

TREASURY_WORKSPACE = "Treasury"
# Sidebar entry that opens the treasury-dashboard desk page rather than a workspace page.
DASHBOARD_ENTRY = "Treasury Dashboard"
VISIBLE_WORKSPACES = (TREASURY_WORKSPACE, DASHBOARD_ENTRY)

# Custom HTML Block placed on the "Treasury Dashboard" workspace. If the workspace view wins the
# race for /app/treasury-dashboard, this block's script runs once the workspace has rendered and
# hands the URL back to the desk page.
REDIRECT_BLOCK = "Open Treasury Dashboard"
REDIRECT_HTML = """<div class="opening">Opening Treasury Dashboard…</div>"""
REDIRECT_STYLE = """.opening { padding: 24px 4px; color: var(--text-muted); font-size: 14px; }"""
REDIRECT_SCRIPT = """const page = "treasury-dashboard";
if (frappe.workspaces) delete frappe.workspaces[page];
frappe.route_flags.replace_route = true;
if (window.location.pathname === "/app/" + page) frappe.router.route();
else frappe.set_route(page);
"""


def setup_workspaces():
	ensure_redirect_block()
	hide_other_workspaces()
	set_treasury_landing_page()


def ensure_redirect_block():
	values = {"html": REDIRECT_HTML, "style": REDIRECT_STYLE, "script": REDIRECT_SCRIPT, "private": 0}
	if frappe.db.exists("Custom HTML Block", REDIRECT_BLOCK):
		frappe.db.set_value("Custom HTML Block", REDIRECT_BLOCK, values, update_modified=False)
		return
	frappe.get_doc({"doctype": "Custom HTML Block", **values}).insert(
		ignore_permissions=True, set_name=REDIRECT_BLOCK
	)


def hide_other_workspaces():
	"""Leave only the two treasury entries in the sidebar.

	System Managers can still open hidden workspaces by URL or search, and
	restore_hidden_workspaces() brings them all back.
	"""
	for name in frappe.get_all(
		"Workspace", filters={"public": 1, "name": ("not in", VISIBLE_WORKSPACES)}, pluck="name"
	):
		frappe.db.set_value("Workspace", name, "is_hidden", 1, update_modified=False)
	for name in VISIBLE_WORKSPACES:
		if frappe.db.exists("Workspace", name):
			frappe.db.set_value("Workspace", name, "is_hidden", 0, update_modified=False)


def restore_hidden_workspaces():
	for name in frappe.get_all("Workspace", filters={"public": 1, "is_hidden": 1}, pluck="name"):
		frappe.db.set_value("Workspace", name, "is_hidden", 0, update_modified=False)


def boot_session(bootinfo):
	# The sidebar entry shares its URL (/app/treasury-dashboard) with the desk page. The router
	# prefers workspaces, so leaving the entry out of its list makes the link open the page.
	bootinfo.allowed_workspaces = [
		w for w in (bootinfo.get("allowed_workspaces") or []) if w.get("name") != DASHBOARD_ENTRY
	]

	# Home and the other standard workspaces are hidden, so the logo and /app land on Treasury.
	user = bootinfo.get("user")
	if user is not None and frappe.db.exists("Workspace", TREASURY_WORKSPACE):
		default = user.get("default_workspace") or {}
		if default.get("name") not in VISIBLE_WORKSPACES:
			user["default_workspace"] = {
				"name": TREASURY_WORKSPACE,
				"public": 1,
				"title": TREASURY_WORKSPACE,
			}


def set_treasury_landing_page():
	for role in TREASURY_ROLES:
		if frappe.db.exists("Role", role):
			frappe.db.set_value("Role", role, "home_page", f"/app/{frappe.scrub(TREASURY_WORKSPACE)}")


def make_treasury_default_workspace(user):
	if frappe.db.exists("Workspace", TREASURY_WORKSPACE):
		frappe.db.set_value("User", user, "default_workspace", TREASURY_WORKSPACE)
