import uuid

from django.conf import settings
from django.db import models

class RenewalAlert(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending"
        ACKNOWLEDGED = "Acknowledged"

    alert_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # OneToOne = one alert per subscription (unique), which blocks duplicate alerts
    subscription = models.OneToOneField(
        "subscriptions.Subscription", on_delete=models.CASCADE, related_name="renewal_alert"
    )
    days_until_expiry = models.IntegerField()
    alert_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "renewal_alerts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Alert for {self.subscription_id} ({self.status})"