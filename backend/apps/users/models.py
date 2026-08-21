import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


def avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"avatars/{instance.id}/{uuid.uuid4().hex}.{ext}"


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True, db_index=True)
    display_name = models.CharField(max_length=100)
    bio = models.CharField(max_length=280, blank=True, default="")
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)

    is_email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email"], name="users_user_email_idx")]

    def __str__(self):
        return self.email
