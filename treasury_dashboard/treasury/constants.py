ROLE_CASHIER = "Treasury Cashier"
ROLE_OFFICER = "Treasury Officer"
ROLE_APPROVER = "Treasury Approver"
TREASURY_ROLES = (ROLE_CASHIER, ROLE_OFFICER, ROLE_APPROVER)

# can open the dashboard read-only without holding a treasury role
VIEWER_ROLES = ("Accounts Manager", "Accounts User")
SUPER_ROLES = ("System Manager",)

REQUEST_RECEIPT = "Receipt"
REQUEST_PAYMENT = "Payment"
REQUEST_TYPES = (REQUEST_RECEIPT, REQUEST_PAYMENT)

PAYMENT_TYPE_FOR_REQUEST = {REQUEST_RECEIPT: "Receive", REQUEST_PAYMENT: "Pay"}
ALLOWED_PARTY_TYPES = ("Customer", "Supplier")

# invoice a request may be allocated against, keyed by (request type, party type)
INVOICE_DOCTYPE_FOR = {
	(REQUEST_RECEIPT, "Customer"): "Sales Invoice",
	(REQUEST_PAYMENT, "Supplier"): "Purchase Invoice",
}

DRAFT = "Draft"
PENDING = "Pending Approval"
APPROVED = "Approved"
POSTED = "Posted"
REJECTED = "Rejected"
CANCELLED = "Cancelled"
REQUEST_STATUSES = (DRAFT, PENDING, APPROVED, POSTED, REJECTED, CANCELLED)
OPEN_STATUSES = (DRAFT, PENDING, APPROVED)

STATUS_TRANSITIONS = {
	DRAFT: {PENDING, CANCELLED},
	PENDING: {APPROVED, REJECTED, CANCELLED},
	APPROVED: {POSTED, CANCELLED},
	POSTED: {APPROVED},  # only when the linked Payment Entry is cancelled
	REJECTED: set(),
	CANCELLED: set(),
}

# grid categories
CAT_RECEIPT = "Receipt"
CAT_PAYMENT = "Payment"
CAT_TRANSFER = "Internal Transfer"
CAT_ADVANCE = "Advance / Custody"
CAT_SETTLEMENT = "Settlement"
CATEGORIES = (CAT_RECEIPT, CAT_PAYMENT, CAT_TRANSFER, CAT_ADVANCE, CAT_SETTLEMENT)

# categories with a request/approval flow inside this app; the rest are read from
# standard ERPNext documents and handed off to the native forms
WORKFLOW_CATEGORIES = (CAT_RECEIPT, CAT_PAYMENT)

MIN_REASON_LENGTH = 5

REALTIME_EVENT = "treasury_dashboard_update"
