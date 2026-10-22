from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User, UserProfile


class RegistrationForm(UserCreationForm):
    """Sign-up form: creates the User and its UserProfile (with optional photo) together."""

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    photo = forms.ImageField(required=False, help_text="Optional profile photo.")

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                photo=self.cleaned_data.get("photo"),
            )
        return user


class UserBasicInfoForm(forms.ModelForm):
    """Lets a logged-in user edit their own name/email (not username or permissions)."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class ProfileForm(forms.ModelForm):
    """Lets a logged-in user edit their own profile photo/bio."""

    class Meta:
        model = UserProfile
        fields = ["photo", "bio"]