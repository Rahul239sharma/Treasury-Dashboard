import { HeaderActions } from "./actions";
import { request_dialog } from "./dialogs";
import { ScopeBar, preset_range } from "./filters";
import { Grid } from "./grid";
import { KpiCards } from "./kpis";
import { DetailPanel } from "./panel";
import { call, debounce, esc, icon, set_currency_format, storage_get, storage_set } from "./utils";

const DEFAULT_PRESET = "last_30";
const PERSISTED = [
	"company",
	"preset",
	"from_date",
	"to_date",
	"category",
	"status",
	"page_length",
];

export class TreasuryDashboard {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.selected = null;
		this.request_seq = 0;
		this.storage_key = `treasury_dashboard:${frappe.session.user}`;
		$(wrapper).addClass("td-page");
		this.$root = $(`<div class="td-root"></div>`).appendTo(this.page.main);
		this.start();
	}

	async start() {
		this.$root.html(`<div class="td-boot"><div class="td-skel td-skel--md"></div></div>`);
		try {
			this.bootinfo = await call("dashboard.get_bootstrap");
		} catch (e) {
			this.$root.html(`<div class="td-boot td-boot--error">
				${icon("lock", 28)}<div>${__(
				"You do not have access to the Treasury Dashboard. Ask your administrator for a treasury role."
			)}</div></div>`);
			return;
		}

		this.abbr_by_company = Object.fromEntries(
			this.bootinfo.companies.map((c) => [c.name, c.abbr])
		);
		this.state = this.initial_state();
		this.apply_route_options();
		this.render_shell();
		this.bind_global();
		await this.refresh();
	}

	initial_state() {
		const saved = storage_get(this.storage_key) || {};
		const permitted = this.bootinfo.companies.map((c) => c.name);
		const state = {
			company: this.bootinfo.default_company || "",
			preset: DEFAULT_PRESET,
			category: "",
			status: "",
			search: "",
			start: 0,
			page_length: 25,
			sort_by: "posting_date",
			sort_order: "desc",
		};
		for (const key of PERSISTED) {
			if (saved[key] !== undefined) state[key] = saved[key];
		}
		if (state.company && !permitted.includes(state.company)) {
			state.company = this.bootinfo.default_company || "";
		}
		if (state.preset !== "custom" || !state.from_date || !state.to_date) {
			if (state.preset === "custom") state.preset = DEFAULT_PRESET;
			[state.from_date, state.to_date] = preset_range(state.preset);
		}
		return state;
	}

	apply_route_options() {
		const options = frappe.route_options;
		if (!options) return false;
		frappe.route_options = null;
		let changed = false;
		for (const key of ["company", "category", "status", "search"]) {
			if (options[key] !== undefined) {
				this.state[key] = options[key];
				changed = true;
			}
		}
		this.state.start = 0;
		return changed;
	}

	render_shell() {
		const first_name = (this.bootinfo.user.full_name || "").split(" ")[0];
		const hour = moment().hour();
		const greeting =
			hour < 12 ? __("Good morning") : hour < 17 ? __("Good afternoon") : __("Good evening");

		this.$root.html(`
			<section class="td-band">
			<header class="td-header">
				<div class="td-header__intro">
					<div class="td-eyebrow">${__("Treasury Dashboard")}</div>
					<h1 class="td-title">${esc(greeting)}${first_name ? `, ${esc(first_name)}` : ""}</h1>
					<div class="td-subtitle">
						<span class="td-scope-label"></span>
						<span class="td-dot-sep"></span>
						<span class="td-live" title="${__("Updates automatically when treasury records change")}"></span>
						<span class="td-updated"></span>
					</div>
				</div>
			</header>
			<div class="td-scope-slot"></div>
			</section>
			<div class="td-kpis-slot"></div>
			<div class="td-grid-slot"></div>
		`);

		this.actions = new HeaderActions({
			parent: this.$root.find(".td-header"),
			dashboard: this,
		});
		this.actions.render();
		this.scope = new ScopeBar({ parent: this.$root.find(".td-scope-slot"), dashboard: this });
		this.kpis = new KpiCards({ parent: this.$root.find(".td-kpis-slot"), dashboard: this });
		this.grid = new Grid({ parent: this.$root.find(".td-grid-slot"), dashboard: this });
		this.panel = new DetailPanel({ parent: this.$root, dashboard: this });
	}

	bind_global() {
		this.schedule_refresh = debounce(
			() => this.refresh({ keep_selection: true, quiet: true }),
			800
		);
		frappe.realtime.off(this.bootinfo.realtime_event);
		frappe.realtime.on(this.bootinfo.realtime_event, (data) => {
			if (data?.company && !this.companies_in_scope().includes(data.company)) return;
			if (this.is_visible()) this.schedule_refresh();
			else this.stale = true;
		});

		$(document)
			.off("keydown.treasury_dashboard")
			.on("keydown.treasury_dashboard", (e) => {
				if (
					!this.is_visible() ||
					e.key !== "/" ||
					$(e.target).is("input, textarea, select, [contenteditable]")
				)
					return;
				if ($(".modal.show").length) return;
				e.preventDefault();
				this.grid.focus_search();
			});
	}

	is_visible() {
		return frappe.get_route_str() === "treasury-dashboard";
	}

	on_show() {
		if (!this.state) return;
		const routed = this.apply_route_options();
		if (routed) this.sync_controls();
		if (routed || this.stale) {
			this.stale = false;
			this.refresh({ keep_selection: !routed });
		}
	}

	// ------------------------------------------------------------------ data

	query_args() {
		const s = this.state;
		return {
			company: s.company || null,
			from_date: s.from_date,
			to_date: s.to_date,
			category: s.category || null,
			statuses: s.status ? JSON.stringify([s.status]) : null,
			search: s.search || null,
			start: s.start,
			page_length: s.page_length,
			sort_by: s.sort_by,
			sort_order: s.sort_order,
		};
	}

	async refresh({ keep_selection = false, quiet = false } = {}) {
		const seq = ++this.request_seq;
		this.persist();
		this.update_scope_label();
		if (!quiet) {
			this.grid.set_loading(true);
			this.$root.addClass("is-refreshing");
		}
		try {
			const data = await call("dashboard.get_dashboard", this.query_args());
			if (seq !== this.request_seq) return;
			this.currency = data.kpis.currency || this.currency;
			set_currency_format(this.currency);
			this.kpis.render(data.kpis);
			this.actions.render(data.kpis.groups?.[0]?.pending || {});
			this.grid.render(data.transactions);
			this.mark_updated();
			if (keep_selection && this.selected) {
				this.panel.load(this.selected.doctype, this.selected.name);
			} else if (!keep_selection) {
				this.select(null);
			}
		} finally {
			if (seq === this.request_seq) {
				this.grid.set_loading(false);
				this.$root.removeClass("is-refreshing");
			}
		}
	}

	async load_transactions() {
		const seq = ++this.request_seq;
		this.persist();
		this.grid.set_loading(true);
		try {
			const data = await call("dashboard.get_transactions", this.query_args());
			if (seq !== this.request_seq) return;
			this.grid.render(data);
			this.mark_updated();
		} finally {
			if (seq === this.request_seq) this.grid.set_loading(false);
		}
	}

	sync_controls() {
		this.scope.sync();
		this.grid.sync_controls();
	}

	on_filters_changed() {
		this.state.start = 0;
		this.sync_controls();
		this.refresh();
	}

	is_default_scope() {
		return (
			(this.state.company || "") === (this.bootinfo.default_company || "") &&
			this.state.preset === DEFAULT_PRESET
		);
	}

	reset_filters({ keep_dates = false } = {}) {
		Object.assign(this.state, {
			company: keep_dates ? this.state.company : this.bootinfo.default_company || "",
			category: "",
			status: "",
			search: "",
			start: 0,
		});
		if (!keep_dates) {
			this.state.preset = DEFAULT_PRESET;
			[this.state.from_date, this.state.to_date] = preset_range(DEFAULT_PRESET);
		}
		this.sync_controls();
		this.refresh();
	}

	apply_quick_filter(action, value) {
		const quick = {
			show_receipts: { category: "Receipt", status: "Posted" },
			show_payments: { category: "Payment", status: "Posted" },
			show_pending: { category: "", status: "Pending Approval" },
			show_awaiting: { category: "", status: "Approved" },
			category: { category: value, status: "" },
		}[action];
		if (!quick) return;
		Object.assign(this.state, quick, { search: "", start: 0 });
		this.sync_controls();
		this.refresh();
		this.grid.$el[0]?.scrollIntoView({ behavior: "smooth", block: "start" });
	}

	persist() {
		const snapshot = {};
		for (const key of PERSISTED) snapshot[key] = this.state[key];
		storage_set(this.storage_key, snapshot);
	}

	// --------------------------------------------------------------- helpers

	single_company() {
		const company = this.bootinfo.companies.find((c) => c.name === this.state.company);
		if (company && !company.is_group) return company.name;
		const leaves = this.bootinfo.companies.filter((c) => !c.is_group);
		return leaves.length === 1 ? leaves[0].name : null;
	}

	companies_in_scope() {
		const all = this.bootinfo.companies;
		if (!this.state?.company) return all.filter((c) => !c.is_group).map((c) => c.name);
		const children = (parent) =>
			all
				.filter((c) => c.parent_company === parent)
				.flatMap((c) => [c.name, ...children(c.name)]);
		const selected = all.find((c) => c.name === this.state.company);
		return selected?.is_group
			? children(selected.name).filter((n) => !all.find((c) => c.name === n).is_group)
			: [this.state.company];
	}

	update_scope_label() {
		const scope = this.companies_in_scope();
		const label = this.state.company
			? esc(this.state.company)
			: `${__("All my schools")} · ${scope
					.map((n) => esc(this.abbr_by_company[n]))
					.join(", ")}`;
		this.$root.find(".td-scope-label").html(label);
	}

	mark_updated() {
		this.$root.find(".td-updated").text(__("Updated {0}", [moment().format("HH:mm")]));
	}

	select(doctype, name) {
		if (!doctype) {
			this.selected = null;
			this.grid.highlight(null);
			this.panel.close();
			return;
		}
		this.selected = { doctype, name };
		this.grid.highlight(this.selected);
		this.panel.load(doctype, name);
	}

	new_request(type) {
		request_dialog(this, type);
	}

	open_standard(category) {
		const info = this.bootinfo.categories.find((c) => c.category === category);
		if (!info?.standard) return;
		const values = { ...info.standard.values };
		const company = this.single_company();
		if (company) values.company = company;
		frappe.new_doc(info.standard.doctype, values);
	}

	after_request_created(detail) {
		this.selected = { doctype: detail.doctype, name: detail.name };
		this.refresh({ keep_selection: true });
	}
}
