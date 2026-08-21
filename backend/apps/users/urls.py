from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("auth/resend-verification/", views.ResendVerificationView.as_view(), name="resend-verification"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.RefreshView.as_view(), name="refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/password/forgot/", views.ForgotPasswordView.as_view(), name="password-forgot"),
    path("auth/password/reset/", views.ResetPasswordView.as_view(), name="password-reset"),
    path("auth/password/change/", views.ChangePasswordView.as_view(), name="password-change"),
    path("users/me/", views.MeView.as_view(), name="me"),
    path("users/me/avatar/", views.AvatarUploadView.as_view(), name="me-avatar"),
]
