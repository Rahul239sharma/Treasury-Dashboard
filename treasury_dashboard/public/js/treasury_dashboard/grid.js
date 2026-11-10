import { CATEGORY_ICON } from "./actions";
import {
	CATEGORY_LABEL,
	category_pill,
	debounce,
	esc,
	icon,
	money,
	short_date,
	signed_amount,
	status_pill,
	strip_abbr,
} from "./utils";

const SOURCE_LABEL = {
	"Treasury Request": __("Request"),
	"Payment Entry": __("Payment Entry"),
	"Journal Entry": __("Journal Entry"),
};

const SORTABLE = { posting_date: __("Date"), party_name: __("Party"), amount: __("Amount") };

export class Grid {
	constructor({ parent, dashboard }) {
		this.dashboard = dashboard;
		this.state = dashboard.state;
		this.$el = $(
			`<section class="td-grid" aria-label="${__("Transactions")}"></section>`
		).appendTo(parent);
		this.$el.html(`
			<div class="td-grid__toolbar">
				<div class="td-grid__tabs" role="tablist" aria-label="${__("Transaction type")}"></div>
				<div class="td-grid__filters">
					<label class="td-field td-field--status">
						${icon("filter", 15)}
						<select class="td-field__input" data-filter="status" aria-label="${__("Status")}"></select>
					</label>
					<label class="td-field td-field--search">
						${icon("search", 15)}
						<input type="search" class="td-field__input" data-filter="search" autocomplete="off"
							placeholder="${__("Search party, reference, document")}" aria-label="${__("Search")}">
						<kbd class="td-kbd" title="${__("Press / to search")}">/</kbd>
					</label>
				</div>
			</div>
			<div class="td-grid__banner"></div>
			<div class="td-grid__scroll"><table class="td-table"><thead></thead><tbody></tbody></table></div>
			<div class="td-grid__footer"></div>
		`);
		this.render_status_options();
		this.bind();
		this.sync_controls();
	}

	render_status_options() {
		const statuses = this.dashboard.bootinfo.statuses;
		this.$el
			.find("[data-filter=status]")
			.html(
				[`<option value="">${__("All statuses")}</option>`]
					.concat(
						statuses.map((s) => `<option value="${esc(s)}">${esc(__(s))}</option>`)
					)
					.join("")
			);
	}

	sync_controls() {
		this.$el.find("[data-filter=status]").val(this.state.status || "");
		const $search = this.$el.find("[data-filter=search]");
		if ($search.val() !== (this.state.search || "")) $search.val(this.state.search || "");
		this.$el.find(".td-field--status").toggleClass("is-set", !!this.state.status);
	}

	focus_search() {
		this.$el.find("[data-filter=search]").trigger("focus").select();
	}

	bind() {
		this.$el.on("click", "[data-tab]", (e) => {
			this.state.category = $(e.currentTarget).data("tab") || "";
			this.dashboard.on_filters_changed();
		});
		this.$el.on("change", "[data-filter=status]", (e) => {
			this.state.status = $(e.currentTarget).val();
			this.dashboard.on_filters_changed();
		});
		const on_search = debounce((value) => {
			if (value === (this.state.search || "")) return;
			this.state.search = value;
			this.dashboard.on_filters_changed();
		}, 350);
		this.$el.on("input", "[data-filter=search]", (e) =>
			on_search(e.currentTarget.value.trim())
		);

		this.$el.on("click", "th[data-sort]", (e) => {
			const key = $(e.currentTarget).data("sort");
			if (this.state.sort_by === key) {
				this.state.sort_order = this.state.sort_order === "desc" ? "asc" : "desc";
			} else {
				this.state.sort_by = key;
				this.state.sort_order = key === "party_name" ? "asc" : "desc";
			}
			this.state.start = 0;
			this.dashboard.load_transactions();
		});
		this.$el.on("click", "tbody tr[data-name]", (e) => {
			if ($(e.target).closest("a").length) return;
			const $row = $(e.currentTarget);
			this.dashboard.select($row.data("doctype"), $row.data("name"));
		});
		this.$el.on("keydown", "tbody tr[data-name]", (e) => {
			if (e.key === "Enter") $(e.currentTarget).trigger("click");
			if (e.key === "ArrowDown") $(e.currentTarget).next().trigger("focus");
			if (e.key === "ArrowUp") $(e.currentTarget).prev().trigger("focus");
		});
		this.$el.on("click", "[data-page]", (e) => {
			const dir = $(e.currentTarget).data("page");
			this.state.start = Math.max(
				0,
				this.state.start + (dir === "next" ? 1 : -1) * this.state.page_length
			);
			this.dashboard.load_transactions();
		});
		this.$el.on("change", ".td-page-size", (e) => {
			this.state.page_length = cint($(e.currentTarget).val());
			this.state.start = 0;
			this.dashboard.load_transactions();
		});
		this.$el.on("click", ".td-clear-filters", () =>
			this.dashboard.reset_filters({ keep_dates: true })
		);
		this.$el.on("click", "[data-new-standard]", (e) =>
			this.dashboard.open_standard($(e.currentTarget).data("new-standard"))
		);
	}

	set_loading(loading) {
		this.$el.toggleClass("is-loading", loading);
		if (loading && !this.has_rows) {
			this.$el.find("tbody").html(
				Array.from({ length: 8 })
					.map(
						() =>
							`<tr class="td-skel-row"><td colspan="7"><div class="td-skel"></div></td></tr>`
					)
					.join("")
			);
		}
	}

	render(data) {
		this.data = data;
		this.has_rows = data.rows.length > 0;
		this.multi_school = this.dashboard.companies_in_scope().length > 1;
		this.sync_controls();
		this.render_tabs(data.categories);
		this.render_banner();
		this.render_head();
		this.render_rows(data.rows);
		this.render_footer(data);
		this.highlight(this.dashboard.selected);
	}

	render_tabs(counts) {
		const all = Object.values(counts || {}).reduce((a, b) => a + b, 0);
		const tabs = [{ key: "", label: __("All"), count: all }].concat(
			this.dashboard.bootinfo.categories.map((c) => ({
				key: c.category,
				label: CATEGORY_LABEL[c.category] || c.category,
				count: counts?.[c.category] || 0,
				standard: !c.workflow,
			}))
		);
		this.$el.find(".td-grid__tabs").html(
			tabs
				.map((t) => {
					const active = (this.state.category || "") === t.key;
					return `<button type="button" role="tab" class="td-tab${
						active ? " is-active" : ""
					}"
						aria-selected="${active}" data-tab="${esc(t.key)}"
						>
						${esc(t.label)}<span class="td-tab__count">${t.count}</span>
						
					</button>`;
				})
				.join("")
		);
	}

	render_banner() {
		const info = this.dashboard.bootinfo.categories.find(
			(c) => c.category === this.state.category && !c.workflow
		);
		const $banner = this.$el.find(".td-grid__banner");
		if (!info) return $banner.empty().hide();
		const can_create = info.standard && frappe.model.can_create(info.standard.doctype);
		$banner.show().html(`
			<span class="td-grid__banner-icon td-cat-bg--${CATEGORY_ICON[info.category]}">${icon(
			CATEGORY_ICON[info.category],
			16
		)}</span>
			<div class="td-grid__banner-text">
				<b>${esc(info.description)}</b>
				<span>${__("Recorded as Payment Entries and Journal Entries.")}</span>
			</div>
			${
				can_create
					? `<button type="button" class="btn btn-xs btn-default" data-new-standard="${esc(
							info.category
					  )}">${icon("plus", 13)} ${__("New")}</button>`
					: ""
			}
		`);
	}

	render_head() {
		const sort_th = (key, cls = "") => {
			const active = this.state.sort_by === key;
			const dir = active ? this.state.sort_order : "";
			return `<th class="is-sortable ${cls}${active ? " is-sorted" : ""}" data-sort="${key}"
				aria-sort="${active ? (dir === "asc" ? "ascending" : "descending") : "none"}">
				${SORTABLE[key]}<span class="td-sort td-sort--${dir || "none"}"></span></th>`;
		};
		this.$el.find("thead").html(`<tr>
			${sort_th("posting_date", "td-col-date")}
			${sort_th("party_name", "td-col-party")}
			<th class="td-col-type">${__("Type")}</th>
			<th class="td-col-account">${__("Cash / Bank account")}</th>
			${sort_th("amount", "td-col-amount")}
			<th class="td-col-status">${__("Status")}</th>
			<th class="td-col-linked">${__("Linked document")}</th>
		</tr>`);
	}

	render_rows(rows) {
		const $body = this.$el.find("tbody");
		if (!rows.length) {
			const filtered = this.state.status || this.state.search || this.state.category;
			$body.html(`<tr class="td-empty-row"><td colspan="7">
				<div class="td-empty">
					<span class="td-empty__icon">${icon("empty", 28)}</span>
					<div class="td-empty__title">${__("No transactions found")}</div>
					<div class="td-empty__text">${
						filtered
							? __("Nothing matches these filters for the selected period.")
							: __(
									"There is no treasury activity for the selected schools and dates."
							  )
					}</div>
					${
						filtered
							? `<button type="button" class="btn btn-default btn-sm td-clear-filters">${__(
									"Clear filters"
							  )}</button>`
							: ""
					}
				</div>
			</td></tr>`);
			return;
		}
		const primary = this.dashboard.currency;
		$body.html(rows.map((r) => this.row_html(r, primary)).join(""));
	}

	row_html(r, primary) {
		const abbr = this.dashboard.abbr_by_company;
		const account_title = [r.account, r.counter_account].filter(Boolean).join(" → ");
		const account = r.counter_account
			? `${esc(strip_abbr(r.account))} <span class="td-arrow">→</span> ${esc(
					strip_abbr(r.counter_account)
			  )}`
			: esc(strip_abbr(r.account));
		const meta = [r.mode_of_payment, r.reference_no].filter(Boolean).map(esc).join(" · ");
		const party_name = r.party_name || r.party || __("Own accounts");
		const school = this.multi_school
			? `<span class="td-school" title="${esc(r.company)}">${esc(
					abbr[r.company] || ""
			  )}</span>`
			: "";
		const linked = r.linked_name
			? `<a class="td-doc-link" href="/app/payment-entry/${encodeURIComponent(
					r.linked_name
			  )}">${esc(r.linked_name)}</a><div class="td-sub">${esc(
					__(r.linked_status === "Submitted" ? "Posted" : r.linked_status || "")
			  )}</div>`
			: `<span class="td-muted">—</span>`;

		return `<tr tabindex="0" data-doctype="${esc(r.doctype)}" data-name="${esc(
			r.name
		)}" class="td-row">
			<td class="td-col-date">${esc(short_date(r.posting_date))}</td>
			<td class="td-col-party">
				<div class="td-party" title="${esc(party_name)}">${esc(party_name)}</div>
				<div class="td-sub"><span class="td-docname">${esc(r.name)}</span> · ${esc(
			SOURCE_LABEL[r.doctype] || r.doctype
		)} ${school}</div>
			</td>
			<td class="td-col-type">${category_pill(r.category)}</td>
			<td class="td-col-account">
				<div class="td-account" title="${esc(account_title)}">${account}</div>
				${meta ? `<div class="td-sub">${meta}</div>` : ""}
			</td>
			<td class="td-col-amount td-amount td-amount--${r.flow}">${signed_amount(
			r.amount,
			r.flow,
			r.currency !== primary ? r.currency : ""
		)}</td>
			<td class="td-col-status">${status_pill(r.status)}</td>
			<td class="td-col-linked">${linked}</td>
		</tr>`;
	}

	render_footer(data) {
		const currency = this.dashboard.currency;
		const totals = data.totals?.[currency] || { in: 0, out: 0, neutral: 0 };
		const sums = [];
		if (totals.in)
			sums.push(
				`<span class="td-sum td-sum--in">${__("In")} <b>${money(
					totals.in,
					currency
				)}</b></span>`
			);
		if (totals.out)
			sums.push(
				`<span class="td-sum td-sum--out">${__("Out")} <b>${money(
					totals.out,
					currency
				)}</b></span>`
			);
		if (totals.neutral)
			sums.push(
				`<span class="td-sum td-sum--neutral">${__("Between own accounts")} <b>${money(
					totals.neutral,
					currency
				)}</b></span>`
			);

		const from = data.total ? data.start + 1 : 0;
		const to = Math.min(data.start + data.rows.length, data.total);
		const sizes = [25, 50, 100]
			.map(
				(n) =>
					`<option value="${n}" ${
						n === this.state.page_length ? "selected" : ""
					}>${n}</option>`
			)
			.join("");
		this.$el.find(".td-grid__footer").html(`
			<div class="td-grid__sums" title="${__(
				"Totals for the current filters, excluding rejected and cancelled items"
			)}">
				${sums.join("") || `<span class="td-muted">${__("No amounts")}</span>`}
			</div>
			<div class="td-pager">
				<span class="td-muted">${__("{0}–{1} of {2}", [from, to, data.total])}</span>
				<select class="td-page-size" aria-label="${__("Rows per page")}">${sizes}</select>
				<button type="button" class="td-icon-btn" data-page="prev" ${
					data.start <= 0 ? "disabled" : ""
				} aria-label="${__("Previous page")}">‹</button>
				<button type="button" class="td-icon-btn" data-page="next" ${
					to >= data.total ? "disabled" : ""
				} aria-label="${__("Next page")}">›</button>
			</div>
		`);
	}

	highlight(selected) {
		this.$el.find("tbody tr").removeClass("is-selected");
		if (!selected) return;
		this.$el
			.find("tbody tr")
			.filter(
				(_, el) =>
					$(el).data("doctype") === selected.doctype &&
					$(el).data("name") === selected.name
			)
			.addClass("is-selected");
	}
}
