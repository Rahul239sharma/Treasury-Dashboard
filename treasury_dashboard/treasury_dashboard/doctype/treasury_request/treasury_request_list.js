const TREASURY_STATUS_COLOR = {
	Draft: "gray",
	"Pending Approval": "orange",
	Approved: "blue",
	Posted: "green",
	Rejected: "red",
	Cancelled: "gray",
};

frappe.listview_settings["Treasury Request"] = {
	add_fields: ["status", "request_type", "payment_entry"],
	get_indicator(doc) {
		return [
			__(doc.status),
			TREASURY_STATUS_COLOR[doc.status] || "gray",
			`status,=,${doc.status}`,
		];
	},
	onload(listview) {
		listview.page.add_inner_button(__("Treasury Dashboard"), () =>
			frappe.set_route("treasury-dashboard")
		);
	},
};
