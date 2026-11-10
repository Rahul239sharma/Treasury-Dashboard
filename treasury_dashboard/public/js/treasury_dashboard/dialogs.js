import { call, esc, money, strip_abbr } from "./utils";

const INVOICE_DOCTYPE = {
	"Receipt|Customer": "Sales Invoice",
	"Payment|Supplier": "Purchase Invoice",
};

export function request_dialog(dashboard, request_type) {
	const boot = dashboard.bootinfo;
	const is_receipt = request_type === "Receipt";
	const schools = boot.companies.filter((c) => !c.is_group).map((c) => c.name);
	const mode_type = Object.fromEntries(boot.modes_of_payment.map((m) => [m.name, m.type]));
	let context = null;
	// field onchange handlers can fire while the dialog is still being built
	let dialog = null;

	const invoice_doctype = () =>
		dialog && INVOICE_DOCTYPE[`${request_type}|${dialog.get_value("party_type")}`];

	dialog = new frappe.ui.Dialog({
		title: is_receipt ? __("New Receipt Request") : __("New Payment Request"),
		size: "large",
		fields: [
			{
				fieldtype: "Select",
				fieldname: "company",
				label: __("School"),
				options: schools,
				reqd: 1,
				default: dashboard.single_company() || (schools.length === 1 ? schools[0] : ""),
				onchange: () => dialog && load_context(),
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Date",
				fieldname: "posting_date",
				label: __("Posting Date"),
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldtype: "Section Break",
				label: is_receipt ? __("Received From") : __("Paid To"),
			},
			{
				fieldtype: "Select",
				fieldname: "party_type",
				label: __("Party Type"),
				options: ["Customer", "Supplier"],
				default: is_receipt ? "Customer" : "Supplier",
				description: is_receipt
					? __("Parents and sponsors are customers")
					: __("Use Customer for fee refunds"),
				onchange: () => {
					if (!dialog) return;
					dialog.set_value("party", "");
					toggle_invoice();
				},
			},
			{
				fieldtype: "Dynamic Link",
				fieldname: "party",
				label: __("Party"),
				options: "party_type",
				reqd: 1,
				get_options: () => dialog?.get_value("party_type"),
				onchange: () => dialog?.set_value("against_invoice", ""),
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Dynamic Link",
				fieldname: "against_invoice",
				label: is_receipt ? __("Against Sales Invoice") : __("Against Purchase Invoice"),
				description: __("Optional. Only open invoices of this party are listed."),
				get_options: () => invoice_doctype(),
				get_query: () => ({
					query: "treasury_dashboard.api.requests.invoice_query",
					filters: {
						company: dialog.get_value("company"),
						party_type: dialog.get_value("party_type"),
						party: dialog.get_value("party"),
						request_type,
					},
				}),
				onchange: () => dialog && fill_from_invoice(),
			},
			{ fieldtype: "HTML", fieldname: "invoice_hint" },
			{ fieldtype: "Section Break", label: __("Payment") },
			{
				fieldtype: "Link",
				fieldname: "mode_of_payment",
				label: __("Mode of Payment"),
				options: "Mode of Payment",
				reqd: 1,
				default: is_receipt ? "Cash" : "Wire Transfer",
				get_query: () => ({ filters: { enabled: 1 } }),
				onchange: () => dialog && apply_mode(),
			},
			{
				fieldtype: "Link",
				fieldname: "account",
				label: is_receipt ? __("Received Into") : __("Paid From"),
				options: "Account",
				reqd: 1,
				get_query: () => ({
					query: "treasury_dashboard.api.requests.account_query",
					filters: { company: dialog.get_value("company") },
				}),
			},
			{ fieldtype: "Data", fieldname: "currency", hidden: 1, default: dashboard.currency },
			{
				fieldtype: "Currency",
				fieldname: "amount",
				label: __("Amount"),
				options: "currency",
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{ fieldtype: "Data", fieldname: "reference_no", label: __("Cheque / Reference No") },
			{
				fieldtype: "Date",
				fieldname: "reference_date",
				label: __("Cheque / Reference Date"),
				description: __("Post-dated cheques are accepted"),
			},
			{ fieldtype: "Section Break" },
			{
				fieldtype: "Small Text",
				fieldname: "purpose",
				label: __("Purpose"),
				reqd: 1,
				placeholder: is_receipt
					? __("e.g. Term 2 tuition fee, Year 5")
					: __("e.g. October bus service invoice"),
			},
			{
				fieldtype: "HTML",
				fieldname: "note",
				options: `<div class="td-dialog-note">${__(
					"Another user with the Treasury Approver role must approve this request. On approval a draft Payment Entry is created for accounts to post."
				)}</div>`,
			},
		],
		primary_action_label: __("Submit for Approval"),
		primary_action: () => save(1),
		secondary_action_label: __("Save as Draft"),
		secondary_action: () => save(0),
	});

	async function load_context() {
		const company = dialog.get_value("company");
		if (!company) return;
		context = await call("requests.get_request_context", { company, request_type });
		dialog.set_value("currency", context.currency);
		dialog.set_value("against_invoice", "");
		apply_mode(true);
	}

	function apply_mode(reset_account = false) {
		const mode = dialog.get_value("mode_of_payment");
		const type = mode_type[mode];
		const is_bank = type === "Bank";
		dialog.set_df_property("reference_no", "reqd", is_bank);
		dialog.set_df_property("reference_date", "reqd", is_bank);
		if (is_bank && !dialog.get_value("reference_date")) {
			dialog.set_value("reference_date", dialog.get_value("posting_date"));
		}
		if (!context) return;
		const current = dialog.get_value("account");
		const valid = context.accounts.find((a) => a.name === current);
		const fits =
			valid &&
			(!type || type === "General" || type === "Phone" || valid.account_type === type);
		if (reset_account || !fits) {
			const fallback =
				type === "Cash" ? context.default_cash_account : context.default_bank_account;
			dialog.set_value("account", context.mode_accounts[mode] || fallback || "");
		}
	}

	function toggle_invoice() {
		const doctype = invoice_doctype();
		dialog.set_df_property("against_invoice", "hidden", !doctype);
		dialog.set_value("against_invoice", "");
		dialog.fields_dict.invoice_hint.$wrapper.empty();
	}

	async function fill_from_invoice() {
		const name = dialog.get_value("against_invoice");
		const $hint = dialog.fields_dict.invoice_hint.$wrapper;
		if (!name) return $hint.empty();
		const doctype = invoice_doctype();
		const { message } = await frappe.db.get_value(doctype, name, [
			"outstanding_amount",
			"grand_total",
			"due_date",
		]);
		if (!message) return;
		dialog.set_value("amount", message.outstanding_amount);
		if (!dialog.get_value("purpose")) {
			dialog.set_value(
				"purpose",
				is_receipt ? __("Settlement of {0}", [name]) : __("Payment of {0}", [name])
			);
		}
		$hint.html(`<div class="td-dialog-note td-dialog-note--info">
			${__("Invoice total {0} · outstanding {1} · due {2}", [
				money(message.grand_total, context?.currency),
				`<b>${money(message.outstanding_amount, context?.currency)}</b>`,
				esc(frappe.datetime.str_to_user(message.due_date)),
			])}</div>`);
	}

	async function save(submit) {
		const values = dialog.get_values();
		if (!values) return;
		if (flt(values.amount) <= 0) {
			frappe.msgprint(__("Amount must be greater than zero."));
			return;
		}
		const payload = {
			request_type,
			company: values.company,
			posting_date: values.posting_date,
			party_type: values.party_type,
			party: values.party,
			against_invoice: values.against_invoice || null,
			mode_of_payment: values.mode_of_payment,
			account: values.account,
			amount: values.amount,
			reference_no: values.reference_no,
			reference_date: values.reference_date,
			purpose: values.purpose,
		};
		dialog.disable_primary_action();
		try {
			const detail = await call(
				"requests.create_request",
				{ values: payload, submit },
				{ freeze: true }
			);
			dialog.hide();
			frappe.show_alert(
				{
					message: submit
						? __("{0} sent for approval", [detail.name])
						: __("{0} saved as draft", [detail.name]),
					indicator: "green",
				},
				5
			);
			dashboard.after_request_created(detail);
		} finally {
			dialog.enable_primary_action();
		}
	}

	dialog.show();
	toggle_invoice();
	load_context();
	return dialog;
}

export function approve_dialog(detail, on_approve) {
	const party = detail.fields.find((f) => f.label === __("Party"));
	const account = detail.fields.find((f) =>
		[__("Received Into"), __("Paid From")].includes(f.label)
	);
	const dialog = new frappe.ui.Dialog({
		title: __("Approve {0}", [detail.name]),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "summary",
				options: `<div class="td-approve-summary">
					<div class="td-approve-summary__amount">${money(detail.amount, detail.currency)}</div>
					<div>${esc(__(detail.category))} · ${esc(party?.value || detail.title)}</div>
					${account ? `<div class="td-sub">${esc(strip_abbr(account.value))}</div>` : ""}
					<div class="td-dialog-note">${__(
						"Approving creates one draft {0} Payment Entry. It is not posted until accounts submit it.",
						[detail.category === "Receipt" ? __("Receive") : __("Pay")]
					)}</div>
				</div>`,
			},
			{ fieldtype: "Small Text", fieldname: "remarks", label: __("Remarks (optional)") },
		],
		primary_action_label: __("Approve"),
		primary_action: async ({ remarks }) => {
			dialog.disable_primary_action();
			try {
				await on_approve(remarks);
				dialog.hide();
			} finally {
				dialog.enable_primary_action();
			}
		},
	});
	dialog.get_primary_btn().addClass("td-btn--approve");
	dialog.show();
}

export function reason_dialog({ title, label, description, primary, danger, on_submit }) {
	const dialog = new frappe.ui.Dialog({
		title,
		fields: [{ fieldtype: "Small Text", fieldname: "reason", label, reqd: 1, description }],
		primary_action_label: primary,
		primary_action: async ({ reason }) => {
			if ((reason || "").trim().length < 5) {
				frappe.msgprint(__("Please write a short reason (at least 5 characters)."));
				return;
			}
			dialog.disable_primary_action();
			try {
				await on_submit(reason.trim());
				dialog.hide();
			} finally {
				dialog.enable_primary_action();
			}
		},
	});
	if (danger) dialog.get_primary_btn().removeClass("btn-primary").addClass("btn-danger");
	dialog.show();
}
