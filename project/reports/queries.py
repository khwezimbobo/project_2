# The one raw SQL query in the project (BRD Module 4). The only value, the status, goes in
# through the %s placeholder. Table and column names cannot be parameters, so they are written
# out in the SQL text. Never build SQL by formatting or joining strings.
from django.db import connection

from subscriptions.models import Subscription

REVENUE_BY_PACKAGE_SQL = """
    SELECT p.name AS package,
           COUNT(s.subscription_id) AS active_subscriptions,
           COALESCE(SUM(s.monthly_total), 0) AS monthly_revenue
    FROM packages AS p
    LEFT JOIN subscriptions AS s
           ON s.package_id = p.package_id
          AND s.status = %s
    GROUP BY p.package_id, p.name
    ORDER BY monthly_revenue DESC, p.name
"""


def revenue_by_package(status=Subscription.Status.ACTIVE):
    """Monthly revenue and subscription count per package, for subscriptions with this status.

    Packages with no matching subscriptions are listed with zero.
    """
    with connection.cursor() as cursor:
        cursor.execute(REVENUE_BY_PACKAGE_SQL, [str(status)])
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]