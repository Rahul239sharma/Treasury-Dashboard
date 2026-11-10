import { CATEGORY_LABEL, esc, icon } from "./utils";

export const CATEGORY_ICON = {
	"Internal Transfer": "transfer",
	"Advance / Custody": "custody",
	Settlement: "settle",
};

// Role-aware buttons in the page header, plus a menu for the categories that are handled in
// their standard document forms.
export class HeaderActions {
	constructor({ parent, dashboard }) {
		this.dashboard = dashboard;
		this.$el = $(`<div class="td-header__actions"></div>`).appendTo(parent);
		this.bind();
	}

	render(pending = {}) {
		const boot = this.dashboard.bootinfo;
		const caps = boot.capabilities;
		const buttons = [this.more_menu(boot, pending, caps)];

		if (caps.can_approve && !caps.can_create) {
			buttons.push(
				`<button type="button" class="btn td-btn td-btn--primary" data-action="show_pending">
					${icon("queue", 16)}<span>${__("Review Queue")}</span>
					${this.badge(pending.raised_by_others)}
				</button>`
			);
		}
		if (caps.can_create) {
			buttons.push(
				`<button type="button" class="btn td-btn td-btn--secondary" data-action="new_payment">
					${icon("out", 16)}<span>${__("New Payment")}</span>
				</button>`,
				`<button type="button" class="btn td-btn td-btn--primary" data-action="new_receipt">
					${icon("in", 16)}<span>${__("New Receipt")}</span>
				</button>`
			);
		}
		if (caps.is_viewer_only) {
			buttons.unshift(
				`<span class="td-viewer-note">${icon("lock", 14)} ${__("Read-only access")}</span>`
			);
		}
		this.$el.html(buttons.join(""));
	}

	badge(count) {
		return count ? `<span class="td-badge">${count}</span>` : "";
	}

	more_menu(boot, pending, caps) {
		const items = [];
		if (caps.can_approve) {
			items.push(
				this.item(
					"show_pending",
					"queue",
					__("Approval queue"),
					"",
					pending.raised_by_others
				)
			);
		}
		if (caps.can_approve || caps.can_manage) {
			items.push(
				this.item(
					"show_awaiting",
					"send",
					__("Approved, awaiting posting"),
					"",
					pending.awaiting_posting
				)
			);
		}
		if (items.length) items.push(`<div class="dropdown-divider"></div>`);

		items.push(`<h6 class="dropdown-header">${__("Other treasury categories")}</h6>`);
		for (const c of boot.categories.filter((c) => !c.workflow)) {
			const can_create = c.standard && frappe.model.can_create(c.standard.doctype);
			items.push(
				`<div class="td-menu-cat">
					<button type="button" class="dropdown-item td-menu-cat__main" data-action="view_category" data-category="${esc(
						c.category
					)}">
						<span class="td-menu-cat__icon td-cat-bg--${CATEGORY_ICON[c.category]}">${icon(
					CATEGORY_ICON[c.category],
					15
				)}</span>
						<span>
							<span class="td-menu-cat__title">${esc(CATEGORY_LABEL[c.category] || c.category)}</span>
							<span class="td-menu-cat__note">${__("Opens the standard form")}</span>
						</span>
					</button>
					${
						can_create
							? `<button type="button" class="td-menu-cat__new" data-action="new_standard" data-category="${esc(
									c.category
							  )}"
								title="${__("New {0}", [esc(CATEGORY_LABEL[c.category])])}">${icon("plus", 14)}</button>`
							: ""
					}
				</div>`
			);
		}

		items.push(`<div class="dropdown-divider"></div>`);
		items.push(this.item("route:List/Treasury Request", "doc", __("All treasury requests")));
		items.push(this.item("route:List/Treasury Audit Log", "lock", __("Treasury audit log")));
		items.push(this.item("route:treasury", "open", __("Treasury workspace")));

		return `<div class="dropdown td-more">
			<button type="button" class="btn td-btn td-btn--ghost" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
				<span>${__("More")}</span>${icon("chevron", 14)}
			</button>
			<div class="dropdown-menu dropdown-menu-right td-menu">${items.join("")}</div>
		</div>`;
	}

	item(action, glyph, label, note = "", count = 0) {
		return `<button type="button" class="dropdown-item td-menu__item" data-action="${esc(
			action
		)}">
			${icon(glyph, 15)}<span class="td-menu__label">${label}</span>${note}${
			count ? `<span class="td-badge td-badge--soft">${count}</span>` : ""
		}
		</button>`;
	}

	bind() {
		this.$el.on("click", "[data-action]", (e) => {
			const $btn = $(e.currentTarget);
			const action = String($btn.data("action"));
			const category = $btn.data("category");
			const dashboard = this.dashboard;

			if (action.startsWith("route:")) {
				return frappe.set_route(...action.slice(6).split("/"));
			}
			switch (action) {
				case "new_receipt":
					return dashboard.new_request("Receipt");
				case "new_payment":
					return dashboard.new_request("Payment");
				case "show_pending":
				case "show_awaiting":
					return dashboard.apply_quick_filter(action);
				case "view_category":
					return dashboard.apply_quick_filter("category", category);
				case "new_standard":
					e.stopPropagation();
					return dashboard.open_standard(category);
			}
		});
	}
}
