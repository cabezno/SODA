## Skill: JWT Authentication

You are implementing JWT-based auth. Follow these conventions:

- Hash passwords with `passlib[bcrypt]` — never store plaintext
- Issue access token (15min) + refresh token (7 days) on login
- Store tokens in httpOnly cookies or Authorization header (Bearer)
- Protect routes with a `get_current_user` dependency that decodes the JWT
- Use `python-jose` or `PyJWT` for token encoding/decoding
- Refresh endpoint: validate refresh token, issue new access token
- Logout: invalidate refresh token (store revoked tokens in DB or cache)
