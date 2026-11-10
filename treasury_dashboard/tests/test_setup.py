import frappe

from treasury_dashboard.setup.workspace import (
	DASHBOARD_ENTRY,
	REDIRECT_BLOCK,
	TREASURY_WORKSPACE,
	VISIBLE_WORKSPACES,
	boot_session,
	setup_workspaces,
)
from treasury_dashboard.tests.utils import TreasuryTestCase, remove_fixtures


class TestVoucherPrint(TreasuryTestCase):
	def test_receipt_voucher_is_bilingual_with_amount_in_words(self):
		request = self.make_request(amount=2_500, submit=True)
		self.approve(request)
		frappe.set_user("Administrator")
		html = frappe.get_print("Treasury Request", request.name, "Treasury Voucher")
		self.assertIn("Receipt Voucher", html)
		self.assertIn("سند قبض", html)
		self.assertIn("AED Two Thousand, Five Hundred only", html)
		self.assertNotIn("NOT APPROVED", html)

	def test_unapproved_voucher_is_watermarked(self):
		request = self.make_request(amount=2_600)
		frappe.set_user("Administrator")
		html = frappe.get_print("Treasury Request", request.name, "Treasury Voucher")
		self.assertIn("NOT APPROVED", html)


class TestWorkspaceSetup(TreasuryTestCase):
	def test_only_treasury_entries_stay_visible(self):
		setup_workspaces()
		visible = frappe.get_all("Workspace", filters={"public": 1, "is_hidden": 0}, pluck="name")
		self.assertEqual(sorted(visible), sorted(VISIBLE_WORKSPACES))

	def test_dashboard_entry_routes_to_the_page(self):
		bootinfo = frappe._dict(
			allowed_workspaces=[frappe._dict(name=TREASURY_WORKSPACE), frappe._dict(name=DASHBOARD_ENTRY)]
		)
		boot_session(bootinfo)
		self.assertEqual([w.name for w in bootinfo.allowed_workspaces], [TREASURY_WORKSPACE])

	def test_dashboard_entry_uses_redirect_block(self):
		setup_workspaces()
		self.assertTrue(frappe.db.exists("Custom HTML Block", REDIRECT_BLOCK))
		workspace = frappe.get_doc("Workspace", DASHBOARD_ENTRY)
		self.assertEqual([b.custom_block_name for b in workspace.custom_blocks], [REDIRECT_BLOCK])
		self.assertFalse(workspace.shortcuts)

	def test_everyone_lands_on_treasury(self):
		bootinfo = frappe._dict(allowed_workspaces=[], user=frappe._dict(default_workspace={"name": "Home"}))
		boot_session(bootinfo)
		self.assertEqual(bootinfo.user["default_workspace"]["name"], TREASURY_WORKSPACE)

	def test_treasury_roles_land_on_treasury_workspace(self):
		setup_workspaces()
		for role in ("Treasury Cashier", "Treasury Officer", "Treasury Approver"):
			self.assertEqual(frappe.db.get_value("Role", role, "home_page"), "/app/treasury")

	def test_dashboard_page_is_registered_for_treasury_roles(self):
		roles = frappe.get_all(
			"Has Role", filters={"parent": "treasury-dashboard", "parenttype": "Page"}, pluck="role"
		)
		for role in ("Treasury Cashier", "Treasury Officer", "Treasury Approver"):
			self.assertIn(role, roles)


def tearDownModule():
	remove_fixtures()
