# JWT Auth Best Practices

- SECRET_KEY must be at least 32 random bytes — load from environment, never hardcode
- Access tokens: short-lived (15min), stateless — no DB lookup needed for validation
- Refresh tokens: long-lived (7d), stored in DB so they can be revoked
- Always validate `exp`, `iat`, and `sub` claims on every request
- Rate-limit the `/auth/login` endpoint to prevent brute force
- On password reset, invalidate all existing refresh tokens for that user
