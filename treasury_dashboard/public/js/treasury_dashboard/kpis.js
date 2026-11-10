import { esc, icon, money, money_parts, number, strip_abbr } from "./utils";

export class KpiCards {
	constructor({ parent, dashboard }) {
		this.dashboard = dashboard;
		this.$el = $(
			`<section class="td-kpis" aria-label="${__("Key figures")}"></section>`
		).appendTo(parent);
		this.$note = $(`<div class="td-kpis__note"></div>`).appendTo(parent);
		this.open_breakdown = null;
		this.render_skeleton();
		this.bind();
	}

	render_skeleton() {
		this.$el.html(
			Array.from({ length: 5 })
				.map(
					() => `<div class="td-kpi is-loading">
						<div class="td-skel td-skel--sm"></div><div class="td-skel td-skel--lg"></div><div class="td-skel td-skel--md"></div>
					</div>`
				)
				.join("")
		);
	}

	bind() {
		this.$el.on("click", "[data-kpi-action]", (e) => {
			// chips sit inside clickable cards; only the innermost target should act
			e.stopPropagation();
			const action = $(e.currentTarget).data("kpi-action");
			if (action === "breakdown") {
				const key = $(e.currentTarget).data("kpi");
				this.toggle_breakdown(this.open_breakdown === key ? null : key);
				return;
			}
			this.dashboard.apply_quick_filter(action);
		});
		this.$el.on("keydown", "[data-kpi-action]", (e) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				$(e.currentTarget).trigger("click");
			}
		});
		$(document)
			.off("click.treasury_kpis")
			.on("click.treasury_kpis", (e) => {
				if (this.open_breakdown && !$(e.target).closest(".td-kpi.is-expanded").length) {
					this.toggle_breakdown(null);
				}
			});
	}

	toggle_breakdown(key) {
		this.open_breakdown = key;
		this.$el.find(".td-kpi").each((_, el) => {
			const open = $(el).data("kpi") === key;
			$(el)
				.toggleClass("is-expanded", open)
				.find("[data-kpi-action=breakdown]")
				.attr("aria-expanded", open);
		});
	}

	render(kpis) {
		const group = kpis.groups?.[0];
		if (!group) {
			this.$el.html(
				`<div class="td-kpis__empty">${__("No schools available for your account.")}</div>`
			);
			this.$note.empty();
			return;
		}
		const currency = group.currency;
		const days = moment(kpis.to_date).diff(moment(kpis.from_date), "days") + 1;
		const as_of = moment(kpis.to_date).format("DD MMM");

		this.$el.html(
			[
				this.balance_card("cash", __("Cash in hand"), "cash", group.cash, currency, as_of),
				this.balance_card("bank", __("Bank balance"), "bank", group.bank, currency, as_of),
				this.flow_card(
					"receipts",
					__("Receipts"),
					"in",
					group.receipts,
					currency,
					days,
					group.trend,
					"inflow",
					"show_receipts"
				),
				this.flow_card(
					"payments",
					__("Payments"),
					"out",
					group.payments,
					currency,
					days,
					group.trend,
					"outflow",
					"show_payments"
				),
				this.pending_card(group.pending, currency),
			].join("")
		);

		const others = kpis.groups.slice(1);
		this.$note.html(
			others.length
				? `${icon("info", 14)} ${__("Cards show {0}. Schools in other currencies:", [
						esc(currency),
				  ])} ${others
						.map(
							(g) =>
								`<b>${esc(g.currency)}</b> ${__("cash")} ${number(
									g.cash.value,
									0
								)} · ${__("bank")} ${number(g.bank.value, 0)}`
						)
						.join("; ")}`
				: ""
		);
	}

	head(label, glyph, extra = "") {
		return `<header class="td-kpi__head">
			<span class="td-kpi__icon">${icon(glyph, 16)}</span>
			<span class="td-kpi__label">${label}</span>${extra}
		</header>`;
	}

	value_html(value, currency) {
		const p = money_parts(value, currency);
		return `<div class="td-kpi__value"><span class="td-kpi__ccy">${esc(p.currency)}</span>${
			p.sign
		}${p.whole}<span class="td-kpi__fils">${p.fraction}</span></div>`;
	}

	balance_card(key, label, glyph, bucket, currency, as_of) {
		const accounts = bucket.accounts || [];
		const total = Math.abs(bucket.value) || 1;
		const multi = this.dashboard.companies_in_scope().length > 1;
		const school = (a) =>
			multi
				? ` <span class="td-school">${esc(
						this.dashboard.abbr_by_company[a.company] || ""
				  )}</span>`
				: "";
		const rows = accounts
			.map((a) => {
				const share = Math.max(2, Math.min(100, (Math.abs(a.balance) / total) * 100));
				return `<li>
					<div class="td-bd__row">
						<span class="td-bd__name" title="${esc(a.account)}">${esc(strip_abbr(a.account))}${school(
					a
				)}</span>
						<span class="td-bd__amt">${number(a.balance)}</span>
					</div>
					<div class="td-bd__bar"><span style="width:${share.toFixed(1)}%"></span></div>
				</li>`;
			})
			.join("");
		const idle = bucket.idle_accounts
			? `<li class="td-bd__idle">${__("{0} more with nil balance", [
					bucket.idle_accounts,
			  ])}</li>`
			: "";
		const open = this.open_breakdown === key;

		return `<article class="td-kpi td-kpi--${key}${
			open ? " is-expanded" : ""
		}" data-kpi="${key}">
			${this.head(label, glyph)}
			${this.value_html(bucket.value, currency)}
			<button type="button" class="td-kpi__foot td-kpi__link" data-kpi-action="breakdown" data-kpi="${key}" aria-expanded="${open}">
				${__("{0} accounts", [accounts.length])} <span class="td-dot-sep"></span> ${__("as at {0}", [
			as_of,
		])}
				<span class="td-caret" aria-hidden="true"></span>
			</button>
			<div class="td-bd">
				<div class="td-bd__title">${label} ${__("by account")}</div>
				<ul>${rows || `<li class="td-bd__idle">${__("No balances")}</li>`}${idle}</ul>
			</div>
		</article>`;
	}

	flow_card(key, label, glyph, bucket, currency, days, trend, series, action) {
		let delta = `<span class="td-muted">${__("No activity in the previous {0} days", [
			days,
		])}</span>`;
		if (bucket.previous) {
			const pct = ((bucket.value - bucket.previous) / Math.abs(bucket.previous)) * 100;
			const dir = pct > 0.05 ? "up" : pct < -0.05 ? "down" : "flat";
			const arrow = dir === "up" ? "↑" : dir === "down" ? "↓" : "→";
			delta = `<span class="td-delta td-delta--${dir} td-delta--${key}">${arrow} ${Math.abs(
				pct
			).toFixed(1)}%</span><span class="td-muted">${__("vs previous {0} days", [
				days,
			])}</span>`;
		}

		return `<article class="td-kpi td-kpi--${key} is-clickable" data-kpi="${key}" data-kpi-action="${action}"
				tabindex="0" role="button" title="${__("Show these in the list")}">
			${this.head(
				label,
				glyph,
				`<span class="td-kpi__count" title="${__("Vouchers")}">${bucket.count}</span>`
			)}
			${this.value_html(bucket.value, currency)}
			${this.sparkline(trend, series, key)}
			<div class="td-kpi__foot">${delta}</div>
		</article>`;
	}

	pending_card(pending, currency) {
		const caps = this.dashboard.bootinfo.capabilities;
		const chips = [];
		if (caps.can_approve && pending.raised_by_others) {
			chips.push(
				`<span class="td-chip td-chip--warn" data-kpi-action="show_pending" role="button" tabindex="0">${__(
					"{0} for you",
					[pending.raised_by_others]
				)}</span>`
			);
		}
		if (pending.awaiting_posting) {
			chips.push(
				`<span class="td-chip td-chip--info" data-kpi-action="show_awaiting" role="button" tabindex="0">${__(
					"{0} awaiting posting",
					[pending.awaiting_posting]
				)}</span>`
			);
		}
		const active = pending.count > 0;
		return `<article class="td-kpi td-kpi--pending is-clickable${
			active ? " is-active" : ""
		}" data-kpi="pending"
				data-kpi-action="show_pending" tabindex="0" role="button" title="${__("Open the approval queue")}">
			${this.head(__("Pending approvals"), "clock")}
			<div class="td-kpi__value">${pending.count}<span class="td-kpi__unit">${
			pending.count === 1 ? __("request") : __("requests")
		}</span></div>
			<div class="td-kpi__sub">${money(pending.amount, currency)}</div>
			<div class="td-kpi__foot">${
				chips.join("") || `<span class="td-muted">${__("Queue is clear")}</span>`
			}</div>
		</article>`;
	}

	sparkline(trend, series, key) {
		const { from_date, to_date } = this.dashboard.state;
		const days = Math.min(moment(to_date).diff(moment(from_date), "days") + 1, 400);
		if (days < 2) return `<div class="td-spark td-spark--empty"></div>`;

		const by_date = {};
		(trend || []).forEach((d) => (by_date[d.date] = d[series]));
		const points = [];
		for (let i = 0; i < days; i++) {
			points.push(by_date[moment(from_date).add(i, "days").format("YYYY-MM-DD")] || 0);
		}
		const max = Math.max(...points, 1);
		const w = 120;
		const h = 32;
		const step = w / (points.length - 1);
		const coords = points.map((v, i) => [i * step, h - 2 - (v / max) * (h - 6)]);
		const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
		const area = `0,${h} ${line} ${w},${h}`;
		return `<svg class="td-spark td-spark--${key}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
			<polygon points="${area}" class="td-spark__area"/><polyline points="${line}" class="td-spark__line"/>
		</svg>`;
	}
}
