## Skill: MongoDB

You are working with MongoDB. Follow these conventions:

**Node.js (Mongoose):**
- Define schemas with `new mongoose.Schema({...})` and export models
- Use `_id` as the primary key (auto-generated ObjectId)
- Validation in schema definition; use `required`, `unique`, `enum`
- Always `await` all mongoose operations; use try/catch

**Python (Motor):**
- Use `motor.motor_asyncio.AsyncIOMotorClient` for async operations
- Collections accessed via `db["collection_name"]`
- Use `await` for all operations; return `_id` as string in responses

**General:**
- Index frequently queried fields
- Connection string in environment variable (`MONGODB_URI`)
- Never store passwords in plain text — hash with bcrypt before saving
