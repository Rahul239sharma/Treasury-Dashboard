# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TreasuryAuditLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action: DF.Data | None
		company: DF.Link | None
		from_status: DF.Data | None
		linked_doctype: DF.Link | None
		linked_name: DF.DynamicLink | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		remarks: DF.SmallText | None
		timestamp: DF.Datetime | None
		to_status: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if not self.is_new():
			frappe.throw(_("Treasury audit entries cannot be modified."))

	def on_trash(self):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Treasury audit entries cannot be deleted."))
