from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from .models import Customer
from .permissions import can_view_all
from .validation import validate_unique_email

User = get_user_model()


# --------------------------------------------------
# LOGIN FORM (Django's form with Bootstrap styling)
# --------------------------------------------------
class BootstrapAuthenticationForm(AuthenticationForm):
    """Same checks as AuthenticationForm, with Bootstrap CSS classes on the inputs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


# --------------------------------------------------
# CUSTOMER FORM
# --------------------------------------------------
class CustomerForm(forms.ModelForm):
    """Create or edit a customer from an HTML page.

    Pass the logged-in user: CustomerForm(request.POST, user=request.user).
    """

    class Meta:
        model = Customer
        fields = [
            "first_name", "last_name", "email", "phone", "address", "assigned_agent",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "email"}
            ),
            # Phones show a number keypad, and browsers can offer autofill.
            "phone": forms.TextInput(
                attrs={"class": "form-control", "type": "tel", "autocomplete": "tel"}
            ),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "assigned_agent": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None and can_view_all(user):
            # Admins and superusers may only pick active Agents or Admins.
            self.fields["assigned_agent"].queryset = User.objects.filter(
                role__in=[User.Role.AGENT, User.Role.ADMIN], is_active=True
            )
        else:
            self.fields.pop("assigned_agent")
            # New customers belong to whoever creates them, matching the
            # API's perform_create and the admin's save_model. Existing
            # customers keep their current agent.
            if user is not None and self.instance.pk is None:
                self.instance.assigned_agent = user

    def clean_first_name(self):
        # strip() so "  Alice  " is saved as "Alice".
        return self.cleaned_data["first_name"].strip()

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        # Same rule as the API: another customer may not have this email.
        validate_unique_email(email, instance=self.instance)
        return email

    # Phone validation is not repeated here: the Customer.phone model field
    # already carries validate_phone_number, and ModelForm applies it.
