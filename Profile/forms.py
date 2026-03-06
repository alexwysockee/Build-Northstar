from django import forms
from django.contrib.auth.models import User, Group


class UserAddForm(forms.Form):
    """Form to add a new user (staff/Management/Back Office only)."""
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "username"}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}))
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}))

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password2") and data["password1"] != data["password2"]:
            raise forms.ValidationError("The two password fields didn't match.")
        return data

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )


class UserGroupsForm(forms.Form):
    """Form to edit a user's groups (admin/Management only)."""
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user and not args and "data" not in kwargs:
            self.initial["groups"] = list(user.groups.values_list("pk", flat=True))

    def save(self):
        self.user.groups.set(self.cleaned_data["groups"])


class ProfilePictureForm(forms.Form):
    avatar = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
    )

    def clean_avatar(self):
        f = self.cleaned_data.get("avatar")
        if not f:
            return None
        content_type = (getattr(f, "content_type", "") or "").lower()
        name = (getattr(f, "name", "") or "").lower()
        if not (content_type.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))):
            raise forms.ValidationError("Please upload an image file.")
        # 5MB limit
        if getattr(f, "size", 0) and f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Image is too large (max 5MB).")
        return f


class UserSetPasswordForm(forms.Form):
    password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password2") and data["password1"] != data["password2"]:
            raise forms.ValidationError("The two password fields didn't match.")
        return data
