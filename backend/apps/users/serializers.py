from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User
from .tokens import email_verification_token

MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "bio", "avatar", "is_email_verified", "created_at"]
        read_only_fields = fields

    def get_avatar(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "password_confirm", "display_name"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_display_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Display name cannot be empty.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            pk = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=pk)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({"uid": "Invalid or malformed link."})

        # Idempotent: re-posting an already-consumed link succeeds quietly
        # rather than erroring, since the only way to get here is having had
        # a valid link at some point (double-clicks / duplicate tabs).
        if user.is_email_verified:
            attrs["user"] = user
            attrs["already_verified"] = True
            return attrs

        if not email_verification_token.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired link."})

        attrs["user"] = user
        attrs["already_verified"] = False
        return attrs


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            pk = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=pk)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({"uid": "Invalid or malformed link."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired link."})

        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})

        validate_password(attrs["new_password"], user=user)
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        validate_password(attrs["new_password"], user=self.context["request"].user)
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["display_name", "bio"]

    def validate_display_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Display name cannot be empty.")
        return value


class AvatarUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["avatar"]

    def validate_avatar(self, value):
        if value.size > MAX_AVATAR_SIZE_BYTES:
            raise serializers.ValidationError("Avatar must be 2MB or smaller.")
        content_type = getattr(value, "content_type", None)
        if content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise serializers.ValidationError("Avatar must be a JPEG, PNG, or WebP image.")
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Adds a couple of convenience claims to the access token and embeds the
    serialized user in the login response body. The refresh token itself is
    stripped back out in LoginView before the response is sent — it only
    ever leaves the server as an HttpOnly cookie (Phase 1 architecture doc,
    Section 8 / 11).
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["display_name"] = user.display_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data
