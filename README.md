## Treasury Dashboard

One treasury screen for a multi-school group running ERPNext. Cashiers raise receipt and payment requests,
approvers decide on them, and every approved request becomes a draft ERPNext Payment Entry for accounts to
post. The same screen shows cash and bank balances, period receipts and payments, the approval queue and a
single list of all cash and bank movements across the schools a user is allowed to see.

Built for Frappe / ERPNext v15. Sample data models a Dubai school group: AED, UAE chart of accounts, local
banks, 5% VAT on supplier bills, WPS payroll and post-dated cheques.

The full user handbook (roles, workflow, every screen function, how-tos by role) is published separately as the
Treasury Handbook.

### What is included

- **Treasury Dashboard** desk page: role-aware header actions (new receipt / payment, review queue), school and
  period bar, cash, bank, receipts, payments and approval cards, one grid for every cash and bank movement with
  type tabs, status filter and search, and a slide-over details panel with approve / reject / cancel and the
  approval trail. Works in light and dark mode and on phones.
- **Treasury Request** with a receipt and payment approval flow that ends in a draft ERPNext Payment Entry.
- **Treasury Audit Log** of every decision.
- **Treasury** workspace with live number cards and a **Treasury Dashboard** sidebar entry; all other workspaces are hidden.
- **Treasury Voucher** print format: English / Arabic receipt and payment voucher with amount in words.
- Sample data for two Dubai schools, loaded automatically on install, and 62 backend tests.

### Status

| Phase | Scope | State |
|---|---|---|
| 1 | Backend, permissions, request workflow, APIs, sample data, tests | Done |
| 2 | Treasury Dashboard desk page | Done |
| 3 | Workspace, form actions, print format, handbook | Done |

### Installation

```bash
cd ~/frappe-bench
bench get-app <repo-url> --branch develop
bench --site <site> install-app treasury_dashboard
bench --site <site> migrate
```

`install-app` and every `migrate` create the three treasury roles, add the `Treasury Request` link field to
Payment Entry, grant the roles read access to the ERPNext documents the dashboard shows, set the Treasury
workspace as the landing page for treasury roles and hide every other public workspace, so the sidebar shows only
**Treasury** and **Treasury Dashboard**. System Managers can still open hidden workspaces by URL or search. To show
them again:

```bash
bench --site <site> execute treasury_dashboard.setup.workspace.restore_hidden_workspaces
```

Front-end assets are built by `bench build --app treasury_dashboard` (run automatically by `bench setup` /
`bench update`). Open the dashboard at `/app/treasury-dashboard` or from the **Treasury** workspace. Every user
lands on the Treasury workspace, including from the logo.

### Sample data

Sample data loads automatically: during `install-app` if the ERPNext setup wizard is already complete, otherwise
as soon as the wizard finishes. Loading takes a few minutes. To install without it, run this before
`install-app`:

```bash
bench --site <site> set-config treasury_skip_sample_data 1
```

To load it by hand later:

```bash
bench --site <site> execute treasury_dashboard.setup.demo.create_demo_data
```

It creates **Ghaf Education Holding** with two schools and about one term of activity ending today:

| | Ghaf British School Al Barsha (GBS) | Ghaf International Academy Mirdif (GIA) |
|---|---|---|
| Banks | Emirates NBD operating, Mashreq fee collection | ADCB operating, Dubai Islamic Bank fee collection |
| Cash | Main safe, fee counter, petty cash | Main safe, fee counter, petty cash |
| Activity | Term 1 fee invoices and collections (transfer, cheque incl. post-dated, card, cash), re-enrolment deposits, supplier bills with 5% VAT, WPS payroll, cash deposits, bank sweeps, staff custody and settlements | same pattern, different volumes |
| Requests | one in each status: draft, pending, approved (draft Payment Entry), posted, rejected, cancelled | same |

The script also sets the site to Dubai conventions: time zone Asia/Dubai, thousands grouping (`1,234,567.00`),
AED as the default currency and `AED` as its symbol. It is safe to run more than once. To rebuild the
transactions from scratch (masters and users are kept):

```bash
bench --site <site> execute treasury_dashboard.setup.demo.reset_demo_activity
bench --site <site> execute treasury_dashboard.setup.demo.create_demo_data
```

Demo users, password `Ghaf@2026`:

| User | Role | Sees |
|---|---|---|
| cashier.barsha@ghaf-edu.ae | Treasury Cashier | Al Barsha |
| approver.barsha@ghaf-edu.ae | Treasury Approver | Al Barsha |
| cashier.mirdif@ghaf-edu.ae | Treasury Cashier | Mirdif |
| approver.mirdif@ghaf-edu.ae | Treasury Approver | Mirdif |
| treasury.manager@ghaf-edu.ae | Treasury Officer + Approver | Holding, both schools |

### Roles

| Action | Cashier | Officer | Approver |
|---|---|---|---|
| View dashboard for permitted schools | yes | yes | yes |
| Raise receipt / payment request | yes | yes | no |
| Submit for approval | own | any | no |
| Approve / reject | no | no | yes, never own |
| Cancel request | own, before approval | any open | no |
| Re-create a missing Payment Entry | no | yes | yes |
| Post (submit) the draft Payment Entry in ERPNext | no | yes | no |

School access comes from standard Company **User Permissions**. A permission on the holding company covers
every school under it. Accounts Manager and Accounts User can open the dashboard read-only.

### Request lifecycle

```
Draft -> Pending Approval -> Approved -> Posted
             |                  |
             +-> Rejected       +-> Cancelled (draft Payment Entry is removed)
Draft / Pending Approval -> Cancelled
Posted -> Approved            (only when the Payment Entry is cancelled in ERPNext)
```

- Approval creates exactly one draft Payment Entry (Receive or Pay), allocated to the invoice when one was
  selected. Nothing is submitted automatically and nothing is written to the GL by this app.
- Submitting the Payment Entry marks the request Posted. Cancelling it moves the request back to Approved so a
  new entry can be raised. Deleting the draft unlinks it.
- The draft Payment Entry cannot be edited away from the approved amount, party, account or company.
- Every action is written to **Treasury Audit Log** (who, when, from/to status, reason, linked entry).
  Entries cannot be edited.

### Server-side checks

- amount greater than zero, posting date not in the future and inside an open fiscal year, not in a frozen period
- cash/bank account belongs to the request's school, is a ledger, enabled, in company currency
- mode of payment type matches the account (Cash vs Bank)
- cheque/reference number and date required for bank accounts; cheque date may be post-dated
- party exists and is enabled; payments to suppliers on hold are refused
- invoice belongs to the same school and party, is submitted, and the amount fits what is still collectable
  after other open requests against it
- duplicate reference number from the same party (across requests and Payment Entries) is refused, as is an
  identical open request without distinct references
- status only changes through the defined transitions; key fields lock once the request leaves Draft
- requester cannot approve or reject their own request; approvers cannot act on other schools

### API

All methods require login and resolve the user's permitted schools on every call.

| Method | Purpose |
|---|---|
| `treasury_dashboard.api.dashboard.get_bootstrap` | schools, capabilities, categories, statuses |
| `treasury_dashboard.api.dashboard.get_dashboard` | KPIs and the first page of transactions in one call |
| `treasury_dashboard.api.dashboard.get_kpis` | balances, receipts, payments, approval queue |
| `treasury_dashboard.api.dashboard.get_transactions` | unified grid with filters, search, paging, sorting |
| `treasury_dashboard.api.dashboard.get_transaction_detail` | panel data, audit trail, allowed actions |
| `treasury_dashboard.api.requests.create_request` | raise a request, optionally submit it |
| `treasury_dashboard.api.requests.submit_request` / `approve_request` / `reject_request` / `cancel_request` | workflow actions |
| `treasury_dashboard.api.requests.create_payment_entry` | re-create a draft entry after the previous one was cancelled or deleted |

### Where the numbers come from

- **Cash / bank balance**: GL balance of every enabled Cash / Bank ledger of the selected schools up to the
  end date.
- **Receipts / payments**: debits / credits to those ledgers within the period. Transfers between the
  group's own cash and bank accounts (Internal Transfer payment entries, Contra journal entries) and opening
  entries are left out.
- **Pending approvals**: open Treasury Requests in Pending Approval, regardless of date.
- **Grid**: Treasury Requests, Payment Entries entered directly in ERPNext, and Journal Entries that are
  Contra, Bank/Cash entries or touch an employee. A Payment Entry created from a request shows as the
  request's linked document, not as a separate row.

### Tests

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app treasury_dashboard
```

62 tests cover validation, duplicates, transitions, self-approval, cross-school access, Payment Entry
creation and sync, the audit trail, KPI arithmetic, the voucher print format and workspace setup. Each test
module creates two throwaway schools (`_Test Treasury School A/B`) with test users, and deletes them, their
users and their records again when it finishes, so nothing from the suite stays on the site.

### Custom code vs standard ERPNext

| Area | Standard ERPNext / Frappe | Added by this app |
|---|---|---|
| Accounting | Payment Entry, Journal Entry, invoices, GL Entry | Nothing new. Approval creates standard draft Payment Entries; the app never posts to the ledger or submits documents |
| Approval | — | **Treasury Request** DocType with a status flow enforced in its controller |
| Audit | Version history, comments | **Treasury Audit Log** DocType (read-only), plus a comment on each generated Payment Entry |
| Link back | — | Read-only `treasury_request` custom field on Payment Entry (not copied on duplicate) |
| Payment Entry events | — | `validate`, `on_submit`, `on_cancel`, `on_trash` hooks keep the request in step and block edits that drift from the approval |
| School isolation | Company User Permissions | Re-checked in every API call and every query the app runs |
| Roles | Accounts User / Manager | Treasury Cashier, Treasury Officer, Treasury Approver, with read access granted to the documents they need |
| Screens | Desk page, Workspace, Number Card, Print Format frameworks | Treasury Dashboard page, Treasury workspace and sidebar entry, four number cards, Treasury Voucher (EN/AR) |

Transfers, staff custody and custody settlements are shown on the dashboard from standard Payment Entries and
Journal Entries; they have no approval step of their own in this release.

### Troubleshooting

`Unknown column 'tabContact.is_billing_contact'` when saving invoices means ERPNext's Contact/Address custom
fields are missing on the site:

```bash
bench --site <site> execute erpnext.setup.install.create_address_and_contact_custom_fields
```

### License

MIT
