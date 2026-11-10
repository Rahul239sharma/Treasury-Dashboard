frappe.pages["treasury-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Treasury Dashboard"),
		single_column: true,
	});

	frappe.require(["treasury_dashboard.bundle.js", "treasury_dashboard.bundle.css"], () => {
		wrapper.treasury_dashboard = new treasury_dashboard.TreasuryDashboard(wrapper);
	});
};

frappe.pages["treasury-dashboard"].on_page_show = function (wrapper) {
	wrapper.treasury_dashboard?.on_show();
};
