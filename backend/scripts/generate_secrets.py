import secrets

print("SECRET_KEY=" + secrets.token_urlsafe(64))
print("JWT_SIGNING_KEY=" + secrets.token_urlsafe(64))
