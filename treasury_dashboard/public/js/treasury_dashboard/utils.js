export const API = "treasury_dashboard.api";

export function call(method, args = {}, opts = {}) {
	return frappe
		.call({
			method: `${API}.${method}`,
			args,
			freeze: opts.freeze,
			freeze_message: opts.freeze_message,
		})
		.then((r) => r.message);
}

export const esc = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

// AED and most Gulf currencies group in thousands; the site default may be Indian (lakh) grouping
let number_format = "#,###.##";

export function set_currency_format(currency) {
	number_format = (currency && get_number_format(currency)) || number_format;
}

export function number(value, decimals = 2) {
	return format_number(flt(value), number_format, decimals);
}

export function money(value, currency, decimals = 2) {
	return `${esc(currency || "")} ${number(value, decimals)}`.trim();
}

// KPI style: whole units large, fils small
export function money_parts(value, currency) {
	const formatted = number(Math.abs(flt(value)), 2);
	const sep = formatted.length - 3;
	return {
		sign: flt(value) < 0 ? "−" : "",
		currency: currency || "",
		whole: formatted.slice(0, sep),
		fraction: formatted.slice(sep),
	};
}

export function signed_amount(value, flow, currency) {
	const sign = flow === "in" ? "+" : flow === "out" ? "−" : "";
	return `${sign}${number(value)}${
		currency ? ` <span class="td-ccy">${esc(currency)}</span>` : ""
	}`;
}

export function nice_date(value) {
	if (!value) return "";
	return moment(value).format("DD MMM YYYY");
}

export function short_date(value) {
	if (!value) return "";
	const m = moment(value);
	return m.year() === moment().year() ? m.format("DD MMM") : m.format("DD MMM YY");
}

export function strip_abbr(account) {
	return (account || "").replace(/ - [^-]+$/, "");
}

export function route_for(doctype, name) {
	return `/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}`;
}

export const STATUS_COLOR = {
	Draft: "gray",
	"Pending Approval": "orange",
	Approved: "blue",
	Posted: "green",
	Rejected: "red",
	Cancelled: "gray",
	Submitted: "green",
	Paid: "green",
	Unpaid: "orange",
	Overdue: "red",
	"Partly Paid": "yellow",
};

export function status_pill(status) {
	const color = STATUS_COLOR[status] || "gray";
	return `<span class="indicator-pill ${color} td-status">${esc(__(status))}</span>`;
}

export const CATEGORY_KEY = {
	Receipt: "receipt",
	Payment: "payment",
	"Internal Transfer": "transfer",
	"Advance / Custody": "custody",
	Settlement: "settlement",
};

export const CATEGORY_LABEL = {
	Receipt: __("Receipts"),
	Payment: __("Payments"),
	"Internal Transfer": __("Internal Transfers"),
	"Advance / Custody": __("Advances / Custody"),
	Settlement: __("Settlements"),
};

export function category_pill(category) {
	return `<span class="td-cat td-cat--${CATEGORY_KEY[category] || "other"}">${esc(
		__(category)
	)}</span>`;
}

const PATHS = {
	cash: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 9.5v.01M18 14.5v.01"/>',
	bank: '<path d="M3 10h18M5 10v7M9.5 10v7M14.5 10v7M19 10v7M3 20h18M12 3l9 5H3z"/>',
	in: '<path d="M17 7L7 17M7 9v8h8"/>',
	out: '<path d="M7 17L17 7M9 7h8v8"/>',
	clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
	plus: '<path d="M12 5v14M5 12h14"/>',
	check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
	x: '<path d="M6 6l12 12M18 6L6 18"/>',
	send: '<path d="M4 12l16-8-6 16-2.5-6.5z"/>',
	transfer: '<path d="M4 8h14l-3-3M20 16H6l3 3"/>',
	custody:
		'<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.8-3.2 3-5 5.5-5s4.7 1.8 5.5 5M15.5 11.5h5M18 9v5"/>',
	settle: '<path d="M8 4h8l3 3v13H5V4z"/><path d="M9 12l2 2 4-4"/>',
	open: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/>',
	refresh: '<path d="M20 11a8 8 0 10-2.3 5.7M20 5v6h-6"/>',
	search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
	doc: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
	queue: '<path d="M4 6h16M4 12h10M4 18h7"/><circle cx="18" cy="17" r="3"/>',
	info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/>',
	lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
	calendar:
		'<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
	chevron: '<path d="M6 9l6 6 6-6"/>',
	filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
	empty: '<path d="M4 13l2.5-7h11L20 13v5a1 1 0 01-1 1H5a1 1 0 01-1-1z"/><path d="M4 13h5l1 2h4l1-2h5"/>',
};

export function icon(name, size = 18) {
	return `<svg class="td-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${
		PATHS[name] || ""
	}</svg>`;
}

export function debounce(fn, wait = 300) {
	let timer;
	return (...args) => {
		clearTimeout(timer);
		timer = setTimeout(() => fn(...args), wait);
	};
}

export function storage_get(key) {
	try {
		return JSON.parse(localStorage.getItem(key) || "null");
	} catch (e) {
		return null;
	}
}

export function storage_set(key, value) {
	try {
		localStorage.setItem(key, JSON.stringify(value));
	} catch (e) {
		// private mode or quota; filters just won't persist
	}
}
