import frappe
from frappe.utils import now_datetime

from treasury_dashboard.treasury.constants import REALTIME_EVENT


def log_action(
	doc,
	action,
	from_status=None,
	to_status=None,
	remarks=None,
	linked_doctype=None,
	linked_name=None,
):
	entry = frappe.get_doc(
		{
			"doctype": "Treasury Audit Log",
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"company": doc.get("company"),
			"action": action,
			"from_status": from_status,
			"to_status": to_status,
			"remarks": remarks,
			"linked_doctype": linked_doctype,
			"linked_name": linked_name,
			"user": frappe.session.user,
			"timestamp": now_datetime(),
		}
	)
	entry.insert(ignore_permissions=True)
	return entry


def get_trail(doctype, name):
	return frappe.get_all(
		"Treasury Audit Log",
		filters={"reference_doctype": doctype, "reference_name": name},
		fields=[
			"action",
			"from_status",
			"to_status",
			"remarks",
			"linked_doctype",
			"linked_name",
			"user",
			"timestamp",
		],
		order_by="timestamp asc, creation asc",
	)


def notify_dashboards(company):
	# broadcast carries no document data; open dashboards refetch through the permission-checked APIs
	frappe.publish_realtime(REALTIME_EVENT, {"company": company}, after_commit=True)
