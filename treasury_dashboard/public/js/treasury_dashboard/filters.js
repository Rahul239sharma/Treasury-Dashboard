import { esc, icon } from "./utils";

export const PRESETS = [
	{ key: "today", label: __("Today") },
	{ key: "week", label: __("This Week") },
	{ key: "month", label: __("This Month") },
	{ key: "last_30", label: __("30 Days") },
	{ key: "last_90", label: __("90 Days") },
	{ key: "custom", label: __("Custom") },
];

export function preset_range(key) {
	const today = moment();
	const fmt = (m) => m.format("YYYY-MM-DD");
	switch (key) {
		case "today":
			return [fmt(today), fmt(today)];
		case "week":
			// UAE working week starts on Monday
			return [fmt(today.clone().isoWeekday(1)), fmt(today)];
		case "month":
			return [fmt(today.clone().startOf("month")), fmt(today)];
		case "last_90":
			return [fmt(today.clone().subtract(89, "days")), fmt(today)];
		default:
			return [fmt(today.clone().subtract(29, "days")), fmt(today)];
	}
}

// School and period: the scope that drives both the cards and the grid.
export class ScopeBar {
	constructor({ parent, dashboard }) {
		this.dashboard = dashboard;
		this.state = dashboard.state;
		this.$el = $(`<div class="td-scope" role="search"></div>`).appendTo(parent);
		this.render();
	}

	render() {
		const companies = this.dashboard.bootinfo.companies;
		this.$el.html(`
			<label class="td-field td-field--school" title="${__("School")}">
				${icon("bank", 16)}
				<select class="td-field__input" data-filter="company" aria-label="${__("School")}">
					${this.school_options(companies)}
				</select>
			</label>
			<div class="td-segmented" role="group" aria-label="${__("Period")}">
				${PRESETS.map(
					(p) =>
						`<button type="button" class="td-seg" data-preset="${p.key}">${p.label}</button>`
				).join("")}
			</div>
			<button type="button" class="td-field td-range" data-open-range title="${__("Choose dates")}">
				${icon("calendar", 16)}<span class="td-range__text"></span>
			</button>
			<div class="td-custom-range">
				<div class="td-date" data-date="from_date"></div>
				<span class="td-muted">→</span>
				<div class="td-date" data-date="to_date"></div>
			</div>
			<div class="td-scope__end">
				<button type="button" class="td-link td-reset">${__("Reset")}</button>
				<button type="button" class="td-icon-btn" data-refresh title="${__("Refresh")}" aria-label="${__(
			"Refresh"
		)}">${icon("refresh", 16)}</button>
			</div>
		`);
		this.make_date_controls();
		this.bind();
		this.sync();
	}

	school_options(companies) {
		const leaves = companies.filter((c) => !c.is_group);
		const options = [];
		if (companies.length > 1) {
			options.push(`<option value="">${__("All my schools")} (${leaves.length})</option>`);
		}
		const depth = {};
		for (const c of companies) {
			depth[c.name] =
				c.parent_company && depth[c.parent_company] !== undefined
					? depth[c.parent_company] + 1
					: 0;
			const pad = "   ".repeat(depth[c.name]);
			const label = c.is_group ? `${c.name} · ${__("group")}` : c.name;
			options.push(`<option value="${esc(c.name)}">${pad}${esc(label)}</option>`);
		}
		return options.join("");
	}

	make_date_controls() {
		this.date_controls = {};
		for (const fieldname of ["from_date", "to_date"]) {
			const control = frappe.ui.form.make_control({
				parent: this.$el.find(`[data-date="${fieldname}"]`),
				df: {
					fieldtype: "Date",
					fieldname,
					placeholder: fieldname === "from_date" ? __("From") : __("To"),
					change: () => {
						if (this._syncing) return;
						const value = control.get_value();
						if (!value || value === this.state[fieldname]) return;
						this.state[fieldname] = value;
						this.state.preset = "custom";
						this.dashboard.on_filters_changed();
					},
				},
				render_input: true,
			});
			this.date_controls[fieldname] = control;
		}
	}

	bind() {
		this.$el.on("change", "[data-filter=company]", (e) => {
			this.state.company = $(e.currentTarget).val();
			this.dashboard.on_filters_changed();
		});
		this.$el.on("click", "[data-preset]", (e) => {
			const key = $(e.currentTarget).data("preset");
			this.state.preset = key;
			if (key === "custom") {
				this.sync();
				this.date_controls.from_date.$input.trigger("focus");
				return;
			}
			[this.state.from_date, this.state.to_date] = preset_range(key);
			this.dashboard.on_filters_changed();
		});
		this.$el.on("click", "[data-open-range]", () => {
			this.state.preset = "custom";
			this.sync();
			this.date_controls.from_date.$input.trigger("focus");
		});
		this.$el.on("click", ".td-reset", () => this.dashboard.reset_filters());
		this.$el.on("click", "[data-refresh]", () =>
			this.dashboard.refresh({ keep_selection: true })
		);
	}

	sync() {
		this._syncing = true;
		this.$el.find("[data-filter=company]").val(this.state.company || "");
		Promise.all([
			this.date_controls.from_date.set_value(this.state.from_date),
			this.date_controls.to_date.set_value(this.state.to_date),
		]).finally(() => (this._syncing = false));

		const custom = this.state.preset === "custom";
		this.$el.toggleClass("is-custom", custom);
		this.$el.find("[data-preset]").each((_, btn) => {
			const active = $(btn).data("preset") === this.state.preset;
			$(btn).toggleClass("is-active", active).attr("aria-pressed", active);
		});
		const from = moment(this.state.from_date);
		const to = moment(this.state.to_date);
		const same_year = from.year() === to.year();
		this.$el
			.find(".td-range__text")
			.text(
				from.isSame(to, "day")
					? to.format("DD MMM YYYY")
					: `${from.format(same_year ? "DD MMM" : "DD MMM YYYY")} – ${to.format(
							"DD MMM YYYY"
					  )}`
			);
		this.$el.find(".td-reset").toggle(!this.dashboard.is_default_scope());
	}
}
