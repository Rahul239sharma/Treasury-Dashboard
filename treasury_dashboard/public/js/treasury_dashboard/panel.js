import { approve_dialog, reason_dialog } from "./dialogs";
import {
	call,
	category_pill,
	esc,
	icon,
	money_parts,
	nice_date,
	number,
	route_for,
	status_pill,
	strip_abbr,
} from "./utils";

const ACTIONS = {
	submit: { label: __("Submit for Approval"), icon: "send", cls: "td-btn--primary" },
	approve: { label: __("Approve"), icon: "check", cls: "td-btn--approve" },
	reject: { label: __("Reject"), icon: "x", cls: "td-btn--reject" },
	create_payment_entry: {
		label: __("Create Payment Entry"),
		icon: "doc",
		cls: "td-btn--primary",
	},
	cancel: { label: __("Cancel Request"), icon: "x", cls: "btn-default td-btn--quiet" },
};

const TRAIL_TONE = {
	Created: "gray",
	"Submitted for Approval": "orange",
	Approved: "blue",
	"Payment Entry Created": "blue",
	"Payment Entry Submitted": "green",
	Rejected: "red",
	Cancelled: "gray",
	"Payment Entry Cancelled": "red",
	"Payment Entry Deleted": "gray",
};

export class DetailPanel {
	constructor({ parent, dashboard }) {
		this.dashboard = dashboard;
		this.$el = $(
			`<aside class="td-panel" role="dialog" aria-modal="false" aria-label="${__(
				"Transaction details"
			)}" aria-live="polite"></aside>`
		).appendTo(parent);
		this.$backdrop = $(`<div class="td-backdrop"></div>`).appendTo(parent);
		this.bind();
	}

	bind() {
		this.$el.on("click", "[data-panel-action]", (e) =>
			this.run($(e.currentTarget).data("panel-action"))
		);
		this.$el.on("click", ".td-panel__close", () => this.dashboard.select(null));
		this.$backdrop.on("click", () => this.dashboard.select(null));
		$(document).on("keydown.treasury_panel", (e) => {
			if (e.key === "Escape" && this.detail && !$(".modal.show").length)
				this.dashboard.select(null);
		});
	}

	close() {
		this.detail = null;
		this.$el.removeClass("is-open");
		this.$backdrop.removeClass("is-open");
		$("body").removeClass("td-drawer-open");
	}

	async load(doctype, name) {
		this.$el.addClass("is-open is-loading");
		this.$backdrop.addClass("is-open");
		$("body").addClass("td-drawer-open");
		if (!this.detail || this.detail.name !== name) {
			this.$el.html(`<div class="td-panel__skeleton">
				<div class="td-skel td-skel--sm"></div><div class="td-skel td-skel--lg"></div>
				<div class="td-skel"></div><div class="td-skel"></div><div class="td-skel td-skel--md"></div></div>`);
		}
		try {
			const detail = await call("dashboard.get_transaction_detail", { doctype, name });
			if (this.dashboard.selected?.name !== name) return;
			this.render(detail);
		} catch (e) {
			this.$el.html(
				`<div class="td-panel__empty"><div class="td-empty__title">${__(
					"Could not load this record"
				)}</div></div>`
			);
		} finally {
			this.$el.removeClass("is-loading");
		}
	}

	render(detail) {
		this.detail = detail;
		const amount = money_parts(detail.amount, detail.currency);
		const sign = detail.flow === "in" ? "+" : detail.flow === "out" ? "−" : "";

		this.$el.html(`
			<header class="td-panel__head">
				<div class="td-panel__pills">${category_pill(detail.category)} ${status_pill(detail.status)}</div>
				<button type="button" class="td-icon-btn td-panel__close" aria-label="${__("Close")}">${icon(
			"x",
			14
		)}</button>
				<h3 class="td-panel__title">${esc(detail.title || detail.name)}</h3>
				<div class="td-panel__meta">
					<a href="${route_for(detail.doctype, detail.name)}" class="td-docname">${esc(detail.name)}</a>
					<span>·</span><span>${esc(nice_date(detail.posting_date))}</span>
					<span>·</span><span>${esc(detail.company)}</span>
				</div>
				<div class="td-panel__amount td-amount--${detail.flow}">
					<span class="td-kpi__ccy">${esc(amount.currency)}</span>${sign}${
			amount.whole
		}<span class="td-kpi__fils">${amount.fraction}</span>
				</div>
			</header>
			${this.workflow_banner(detail)}
			${this.actions_html(detail)}
			<section class="td-panel__section">
				<h4>${__("Details")}</h4>
				<dl class="td-fields">${detail.fields
					.map((f) => `<dt>${esc(f.label)}</dt><dd>${esc(f.value)}</dd>`)
					.join("")}</dl>
			</section>
			${this.linked_html(detail)}
			${this.lines_html(detail)}
			${this.ledger_html(detail)}
			${this.trail_html(detail)}
		`);
	}

	workflow_banner(detail) {
		if (detail.workflow === "erpnext") {
			return `<div class="td-banner td-banner--info">${icon("info", 16)}
				<div>${__("Recorded as a {0}. Use Open to review or change it.", [esc(__(detail.doctype))])}</div>
			</div>`;
		}
		if (detail.workflow === "standard") {
			return `<div class="td-banner td-banner--info">${icon("info", 16)}
				<div>${__("Entered directly as a {0}, without a treasury request, so it has no approval trail.", [
					esc(__(detail.doctype)),
				])}</div></div>`;
		}
		if (
			detail.doctype === "Treasury Request" &&
			detail.status === "Pending Approval" &&
			detail.is_own_request
		) {
			return `<div class="td-banner td-banner--info">${icon("lock", 16)}
				<div>${__(
					"Waiting for an approver. You raised this request, so you cannot approve or reject it."
				)}</div></div>`;
		}
		if (detail.doctype === "Treasury Request" && detail.status === "Approved") {
			const entry = detail.linked.find((l) => l.doctype === "Payment Entry");
			return entry
				? `<div class="td-banner td-banner--info">${icon("send", 16)}
					<div>${__("Approved. Draft Payment Entry {0} is waiting to be posted by accounts.", [
						`<a href="${route_for("Payment Entry", entry.name)}">${esc(
							entry.name
						)}</a>`,
					])}</div></div>`
				: `<div class="td-banner td-banner--warn">${icon("info", 16)}
					<div>${__(
						"Approved, but no live Payment Entry is linked. Create a new draft entry to continue."
					)}</div></div>`;
		}
		return "";
	}

	actions_html(detail) {
		const buttons = (detail.actions || []).map((key) => {
			const a = ACTIONS[key];
			return `<button type="button" class="btn btn-sm td-btn ${
				a.cls
			}" data-panel-action="${key}">${icon(a.icon, 15)}<span>${a.label}</span></button>`;
		});
		buttons.push(
			`<a class="btn btn-sm btn-default td-btn td-btn--quiet" href="${route_for(
				detail.doctype,
				detail.name
			)}">${icon("open", 14)}<span>${__("Open")}</span></a>`
		);
		return `<div class="td-panel__actions">${buttons.join("")}</div>`;
	}

	linked_html(detail) {
		if (!detail.linked?.length) return "";
		return `<section class="td-panel__section"><h4>${__("Linked Documents")}</h4>
			<ul class="td-linked">${detail.linked
				.map(
					(l) => `<li>
					<span class="td-linked__icon">${icon("doc", 16)}</span>
					<div class="td-linked__body">
						<a href="${route_for(l.doctype, l.name)}" class="td-docname">${esc(l.name)}</a>
						<div class="td-sub">${esc(__(l.doctype))}${
						l.posting_date ? ` · ${esc(nice_date(l.posting_date))}` : ""
					}</div>
					</div>
					<div class="td-linked__side">
						${l.status ? status_pill(l.status === "Submitted" ? "Posted" : l.status) : ""}
						${l.amount != null ? `<div class="td-sub">${number(l.amount)}</div>` : ""}
						${l.outstanding ? `<div class="td-sub">${__("Outstanding")} ${number(l.outstanding)}</div>` : ""}
					</div>
				</li>`
				)
				.join("")}</ul></section>`;
	}

	lines_html(detail) {
		if (!detail.lines?.length) return "";
		return `<section class="td-panel__section"><h4>${__("Journal Lines")}</h4>${this.table(
			detail.lines
		)}</section>`;
	}

	ledger_html(detail) {
		if (!detail.ledger?.length) return "";
		return `<section class="td-panel__section"><h4>${__("Ledger Impact")}</h4>${this.table(
			detail.ledger
		)}</section>`;
	}

	table(rows) {
		return `<table class="td-mini"><thead><tr><th>${__(
			"Account"
		)}</th><th class="text-right">${__("Debit")}</th><th class="text-right">${__(
			"Credit"
		)}</th></tr></thead>
			<tbody>${rows
				.map(
					(r) => `<tr><td title="${esc(r.account)}">${esc(strip_abbr(r.account))}${
						r.party ? `<div class="td-sub">${esc(r.party)}</div>` : ""
					}</td>
					<td class="text-right">${r.debit ? number(r.debit) : ""}</td><td class="text-right">${
						r.credit ? number(r.credit) : ""
					}</td></tr>`
				)
				.join("")}</tbody></table>`;
	}

	trail_html(detail) {
		if (!detail.trail?.length) return "";
		return `<section class="td-panel__section"><h4>${__("Approval Trail")}</h4>
			<ol class="td-trail">${detail.trail
				.map(
					(t) => `<li class="td-trail__item td-trail__item--${
						TRAIL_TONE[t.action] || "gray"
					}">
					<div class="td-trail__head"><b>${esc(__(t.action))}</b><span class="td-sub" title="${esc(
						t.timestamp
					)}">${frappe.datetime.comment_when(t.timestamp)}</span></div>
					<div class="td-sub">${esc(t.user_fullname || t.user)}${
						t.linked_name
							? ` · <a href="${route_for(t.linked_doctype, t.linked_name)}">${esc(
									t.linked_name
							  )}</a>`
							: ""
					}</div>
					${t.remarks ? `<blockquote class="td-trail__note">${esc(t.remarks)}</blockquote>` : ""}
				</li>`
				)
				.join("")}</ol></section>`;
	}

	async run(action) {
		const detail = this.detail;
		if (!detail) return;
		const name = detail.name;
		const done = (result, message, indicator = "green") => {
			frappe.show_alert({ message, indicator }, 5);
			this.render(result);
			this.dashboard.refresh({ keep_selection: true });
		};

		if (action === "submit") {
			frappe.confirm(__("Send {0} to an approver?", [`<b>${esc(name)}</b>`]), async () => {
				const result = await call("requests.submit_request", { name }, { freeze: true });
				done(result, __("{0} submitted for approval", [name]));
			});
		} else if (action === "approve") {
			approve_dialog(detail, async (remarks) => {
				const result = await call(
					"requests.approve_request",
					{ name, remarks },
					{ freeze: true, freeze_message: __("Approving…") }
				);
				const entry = result.linked.find((l) => l.doctype === "Payment Entry");
				done(
					result,
					__("Approved. Draft Payment Entry {0} created.", [entry ? entry.name : ""])
				);
			});
		} else if (action === "reject") {
			reason_dialog({
				title: __("Reject {0}", [name]),
				label: __("Reason for rejection"),
				description: __("The requester sees this reason on the request."),
				primary: __("Reject Request"),
				danger: true,
				on_submit: async (reason) => {
					const result = await call(
						"requests.reject_request",
						{ name, reason },
						{ freeze: true }
					);
					done(result, __("{0} rejected", [name]), "red");
				},
			});
		} else if (action === "cancel") {
			const has_entry = detail.linked.some(
				(l) => l.doctype === "Payment Entry" && l.status === "Draft"
			);
			reason_dialog({
				title: __("Cancel {0}", [name]),
				label: __("Reason for cancellation"),
				description: has_entry
					? __("The draft Payment Entry linked to this request will be deleted.")
					: "",
				primary: __("Cancel Request"),
				danger: true,
				on_submit: async (reason) => {
					const result = await call(
						"requests.cancel_request",
						{ name, reason },
						{ freeze: true }
					);
					done(result, __("{0} cancelled", [name]), "gray");
				},
			});
		} else if (action === "create_payment_entry") {
			const result = await call("requests.create_payment_entry", { name }, { freeze: true });
			done(result, __("Draft Payment Entry created"));
		}
	}

	destroy() {
		$(document).off("keydown.treasury_panel");
	}
}
