# Learnings from soda_
*2026-04-24*

## Pattern: Stateful Single-Session Enforcement
Using a dedicated database table (`active_sessions`) to track and enforce a single active session per user is a robust pattern for high-security applications. It provides explicit server-side control over sessions, allowing users to view and revoke access from other devices.

## Pattern: Rotating Refresh Tokens in HttpOnly Cookies
Storing long-lived, rotating refresh tokens in httpOnly cookies, while keeping short-lived access tokens in memory, provides a strong defense against XSS attacks and token theft, a crucial pattern for any production-grade authentication system.

## Pattern: Service-Oriented Modular Architecture
Separating concerns into distinct modules (config, models, db session, services) creates a clean, testable, and maintainable backend. Decoupling business logic (e.g., `user_service`) from the API layer (endpoints) allows for easier evolution and reuse.

## Anti-pattern: Optional Email Verification for SaaS
The blueprint specified optional email verification. For a commercial SaaS product, this is an anti-pattern as it invites spam accounts, complicates user account recovery, and prevents reliable communication, ultimately degrading the service's integrity.

## Preference: Security-First Design
The architecture heavily prioritizes security through multiple layers: bcrypt hashing, rate limiting, JWT rotation, and single-session enforcement. This indicates a preference for building defensively for applications intended for commercial use.

## Preference: Asynchronous-First Stack
The design choice of using asynchronous database sessions and an async Redis client alongside FastAPI demonstrates a clear preference for building high-performance, I/O-bound services that can handle significant concurrent traffic efficiently.

## Preference: Explicit State Management
Instead of a purely stateless JWT approach, the design opts for a hybrid model by explicitly tracking session state in the database. This shows a preference for control and auditability over the simplicity of statelessness, especially for security-critical features.

## Knowledge Suggestion
Implement Refresh Token Reuse Detection. This is a security mechanism where if a previously used (and supposedly rotated) refresh token is presented, the system immediately invalidates the entire family of tokens for that user session, as it indicates a compromised token is being used by an attacker.
