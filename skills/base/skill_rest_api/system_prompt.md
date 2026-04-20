## Skill: REST API Design

Apply these REST conventions in all API designs:

- Resources as nouns, plural: `/users`, `/tasks`, `/orders`
- HTTP verbs: GET (read), POST (create), PUT/PATCH (update), DELETE (remove)
- Status codes: 200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity, 500 Internal Server Error
- Consistent error envelope: `{"detail": "message", "code": "ERROR_CODE"}`
- Pagination: `?page=1&size=20`, response includes `total`, `page`, `size`, `items`
- Versioning via URL prefix: `/api/v1/`
- Never expose internal IDs in sequential integers — use UUIDs for public resources
