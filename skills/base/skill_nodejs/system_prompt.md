## Skill: Node.js / Express

You are building a Node.js application with Express. Follow these conventions:

- Use `express.Router()` for route grouping, mount routers in `app.js` or `index.js`
- Use `async/await` throughout — never callbacks
- Centralized error handling with `next(err)` and an error-handler middleware
- Use `dotenv` for environment variables, never hardcode secrets
- Validate request bodies with `express-validator` or `joi`
- Use `helmet` and `cors` middleware in production setups
- Structure: `routes/`, `controllers/`, `services/`, `middleware/`
- `package.json` must include all dependencies with exact versions
