app_name = "treasury_dashboard"
app_title = "Treasury Dashboard"
app_publisher = "rahul"
app_description = "Unified treasury workbench for multi-school education groups on ERPNext"
app_email = "rs@gmail.com"
app_license = "mit"

required_apps = ["frappe/erpnext"]

after_install = "treasury_dashboard.setup.install.after_install"
after_migrate = "treasury_dashboard.setup.install.after_migrate"
before_uninstall = "treasury_dashboard.setup.install.before_uninstall"
setup_wizard_complete = "treasury_dashboard.setup.install.after_setup_wizard"

boot_session = "treasury_dashboard.setup.workspace.boot_session"
app_include_js = "treasury_nav.bundle.js"

doc_events = {
	"Payment Entry": {
		"validate": "treasury_dashboard.treasury.payment_entry.validate_linked_payment_entry",
		"on_submit": "treasury_dashboard.treasury.payment_entry.on_payment_entry_submit",
		"on_cancel": "treasury_dashboard.treasury.payment_entry.on_payment_entry_cancel",
		"on_trash": "treasury_dashboard.treasury.payment_entry.on_payment_entry_trash",
	}
}

# audit rows must outlive the documents they describe
ignore_links_on_delete = ["Treasury Audit Log"]
