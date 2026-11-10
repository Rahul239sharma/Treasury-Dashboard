// Sidebar and landing fixes for the treasury desk.
// 1. The "Treasury Dashboard" sidebar entry shares its URL with the desk page of the same name. The
//    workspace view registers it as a workspace after load, so that route is sent to the page.
// 2. Home is hidden; anything that still lands there (history, old bookmarks) goes to Treasury.
const ENTRY = "treasury-dashboard";
const HOME = "home";
const LANDING = "treasury";

function forget_entry() {
	if (frappe.workspaces) delete frappe.workspaces[ENTRY];
}

function go_to_landing() {
	setTimeout(() => {
		frappe.route_flags.replace_route = true;
		frappe.set_route(LANDING);
	}, 0);
}

function check_route() {
	const route = frappe.get_route() || [];
	// users without access to the hidden Home workspace get a bare ["home"] route
	if (route.length === 1 && frappe.router.slug(route[0] || "") === HOME) return go_to_landing();
	if (route[0] !== "Workspaces") return;
	const slug = frappe.router.slug(route[route.length - 1] || "");

	if (slug === ENTRY) {
		setTimeout(() => {
			forget_entry();
			frappe.route_flags.replace_route = true;
			// on /app/treasury-dashboard already: re-resolve the URL; otherwise go there
			if (window.location.pathname === `/app/${ENTRY}`) frappe.router.route();
			else frappe.set_route(ENTRY);
		}, 0);
	} else if (slug === HOME && route.length === 2) {
		go_to_landing();
	}
}

$(document).on("app_ready", () => {
	forget_entry();
	// the first page is rendered before app_ready, so check it once as well
	check_route();
	frappe.router.on("change", check_route);
});
