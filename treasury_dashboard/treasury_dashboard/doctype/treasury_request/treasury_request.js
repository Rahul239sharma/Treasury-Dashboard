// Copyright (c) 2026, rahul and contributors
// For license information, please see license.txt

const INVOICE_DOCTYPE = {
	"Receipt|Customer": "Sales Invoice",
	"Payment|Supplier": "Purchase Invoice",
};

frappe.ui.form.on("Treasury Request", {
	setup(frm) {
		frm.set_query("party_type", () => ({
			filters: { name: ["in", ["Customer", "Supplier"]] },
		}));
		frm.set_query("account", () => ({
			query: "treasury_dashboard.api.requests.account_query",
			filters: { company: frm.doc.company },
		}));
		frm.set_query("against_invoice", () => ({
			query: "treasury_dashboard.api.requests.invoice_query",
			filters: {
				company: frm.doc.company,
				party_type: frm.doc.party_type,
				party: frm.doc.party,
				request_type: frm.doc.request_type,
			},
		}));
	},

	refresh(frm) {
		frm.toggle_enable("against_invoice", !!frm.events.invoice_doctype(frm));
		if (frm.is_new()) return;

		frm.add_custom_button(__("Treasury Dashboard"), () =>
			frappe.set_route("treasury-dashboard")
		);
		frm.events.show_status_note(frm);
		frappe
			.xcall("treasury_dashboard.api.dashboard.get_transaction_detail", {
				doctype: frm.doctype,
				name: frm.doc.name,
			})
			.then((detail) => frm.events.add_workflow_buttons(frm, detail.actions || []));
	},

	show_status_note(frm) {
		const notes = {
			"Pending Approval": __(
				"Waiting for a Treasury Approver. The requester cannot approve their own request."
			),
			Approved: frm.doc.payment_entry
				? __("Approved. Draft Payment Entry {0} is waiting to be posted.", [
						frm.doc.payment_entry.bold(),
				  ])
				: __("Approved without a live Payment Entry. Create one to continue."),
			Posted: __("Posted through Payment Entry {0}.", [
				(frm.doc.payment_entry || "").bold(),
			]),
			Rejected: __("Rejected: {0}", [
				frappe.utils.escape_html(frm.doc.rejection_reason || ""),
			]),
		};
		const colors = {
			"Pending Approval": "orange",
			Approved: "blue",
			Posted: "green",
			Rejected: "red",
		};
		if (notes[frm.doc.status])
			frm.dashboard.set_headline_alert(notes[frm.doc.status], colors[frm.doc.status]);
	},

	add_workflow_buttons(frm, actions) {
		const api = "treasury_dashboard.api.requests.";
		const run = (method, args, message) =>
			frappe.xcall(api + method, { name: frm.doc.name, ...args }).then(() => {
				frappe.show_alert({ message, indicator: "green" });
				frm.reload_doc();
			});
		const ask_reason = (title, method, message) =>
			frappe.prompt(
				{ fieldtype: "Small Text", fieldname: "reason", label: __("Reason"), reqd: 1 },
				({ reason }) => run(method, { reason }, message),
				title,
				__("Confirm")
			);
		const group = __("Actions");

		if (actions.includes("submit")) {
			frm.add_custom_button(
				__("Submit for Approval"),
				() => run("submit_request", {}, __("Sent for approval")),
				group
			);
		}
		if (actions.includes("approve")) {
			frm.add_custom_button(
				__("Approve"),
				() =>
					frappe.prompt(
						{
							fieldtype: "Small Text",
							fieldname: "remarks",
							label: __("Remarks (optional)"),
						},
						({ remarks }) =>
							run(
								"approve_request",
								{ remarks },
								__("Approved, draft Payment Entry created")
							),
						__("Approve {0}", [frm.doc.name]),
						__("Approve")
					),
				group
			);
		}
		if (actions.includes("reject")) {
			frm.add_custom_button(
				__("Reject"),
				() =>
					ask_reason(__("Reject {0}", [frm.doc.name]), "reject_request", __("Rejected")),
				group
			);
		}
		if (actions.includes("create_payment_entry")) {
			frm.add_custom_button(
				__("Create Payment Entry"),
				() => run("create_payment_entry", {}, __("Draft Payment Entry created")),
				group
			);
		}
		if (actions.includes("cancel")) {
			frm.add_custom_button(
				__("Cancel Request"),
				() =>
					ask_reason(
						__("Cancel {0}", [frm.doc.name]),
						"cancel_request",
						__("Cancelled")
					),
				group
			);
		}
	},

	request_type(frm) {
		frm.set_value("party_type", frm.doc.request_type === "Payment" ? "Supplier" : "Customer");
		frm.events.sync_invoice_doctype(frm);
	},

	party_type(frm) {
		frm.set_value("party", null);
		frm.events.sync_invoice_doctype(frm);
	},

	party(frm) {
		frm.set_value("against_invoice", null);
	},

	sync_invoice_doctype(frm) {
		frm.set_value("against_invoice", null);
		frm.set_value("against_doctype", frm.events.invoice_doctype(frm) || null);
		frm.toggle_enable("against_invoice", !!frm.doc.against_doctype);
	},

	invoice_doctype(frm) {
		return INVOICE_DOCTYPE[`${frm.doc.request_type}|${frm.doc.party_type}`];
	},
});
