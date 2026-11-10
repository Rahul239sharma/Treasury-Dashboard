import frappe


class InvalidStatusTransition(frappe.ValidationError):
	pass


class LockedFieldError(frappe.ValidationError):
	pass


class DuplicateRequestError(frappe.ValidationError):
	pass


class DuplicatePaymentEntryError(frappe.ValidationError):
	pass


class CompanyMismatchError(frappe.ValidationError):
	pass


class SelfApprovalError(frappe.PermissionError):
	pass
