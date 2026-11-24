# Demo evidence

End-to-end walkthrough of the ISP Subscription Management Platform running in the Docker stack,
recorded on 23 November 2026. It follows the demo flow in BRD section 19:
login → create subscription → pricing breakdown → dashboard → Celery task triggered → subscription auto-suspended.

Demo data: eight customers with Active subscriptions whose contracts end at different times, including
Kagiso Molefe, whose contract ended 35 days ago (past the 30-day grace period).

| # | Screenshot | Shows |
|---|-----------|-------|
| 1 | [01_login_page.png](01_login_page.png) | Staff login page (session login for the dashboard and Django Admin) |
| 2 | [02_jwt_token.png](02_jwt_token.png) | `POST /api/auth/token/` returns an access and a refresh token (200) |
| 3 | [02b_swagger_authorize.png](02b_swagger_authorize.png) | The access token entered in Swagger's Authorize box (Bearer authentication) |
| 4 | [03_create_customer.png](03_create_customer.png) | `POST /api/customers/` creates a new customer (201), assigned to the logged-in user |
| 5 | [04_create_subscription_request.png](04_create_subscription_request.png) | `POST /api/subscriptions/` request: only the customer, package, contract term, add-ons and installation date are sent, no prices |
| 6 | [05_pricing_breakdown.png](05_pricing_breakdown.png) | 201 response with the server-side pricing: base 699.00 + add-ons 250.00 = subtotal 949.00, New Customer discount −94.90, monthly total 854.10, installation fee 500.00, first month 1354.10; contract 23 Nov 2026 → 23 Nov 2027 (365 days) |
| 7 | [06_dashboard_before.png](06_dashboard_before.png) | Dashboard before the tasks run: 8 active subscribers, R7,475.55 monthly revenue, 0 pending alerts, 7 contracts ending within 30 days |
| 8 | [07_celery_tasks.png](07_celery_tasks.png) | Worker log: both tasks received through RabbitMQ and succeeded: `check_expiring_subscriptions` created 5 alerts, `auto_suspend_overdue_subscriptions` suspended 1 subscription |
| 9 | [08_suspended_subscription.png](08_suspended_subscription.png) | `GET /api/subscriptions/?status=Suspended`: Kagiso's subscription (contract ended 19 Oct 2026) is now Suspended |
| 10 | [09_audit_log_system.png](09_audit_log_system.png) | `GET /api/subscriptions/{id}/logs/`: Active → Suspended by "System" with the note "Auto-suspended: contract expired beyond grace period", after Pending → Active (Admin1) and creation (agent1) |
| 11 | [10_dashboard_after.png](10_dashboard_after.png) | Dashboard after the tasks: 7 active subscribers, R7,062.59 monthly revenue, 5 pending renewal alerts |
| 12 | [11_idor_agent_403.png](11_idor_agent_403.png) | Support Agent agent1 requests a customer assigned to Admin1: 403 Forbidden (IDOR prevention) |
| 13 | [12_invalid_transition_400.png](12_invalid_transition_400.png) | Cancelled subscription cannot be reactivated: PATCH status to Active returns 400 |

Revenue check: R7,475.55 − R412.96 (Kagiso's monthly total) = R7,062.59, so the dashboard reflects the
automatic suspension exactly.
