# skill_n8n — n8n Workflow Integration

## What you are building

An **n8n workflow JSON** that connects the SODA-generated services. The workflow is imported directly into n8n — it must be valid JSON that n8n accepts without errors.

## n8n workflow JSON structure

```json
{
  "name": "Project Name — n8n Integration",
  "nodes": [ ...node objects... ],
  "connections": { "Node Name": { "main": [[{ "node": "Next", "type": "main", "index": 0 }]] } },
  "active": false,
  "settings": { "executionOrder": "v1" },
  "versionId": "uuid-v4"
}
```

## Node types to use

| Purpose | type | typeVersion |
|---------|------|-------------|
| Start | `n8n-nodes-base.manualTrigger` | 1 |
| HTTP call | `n8n-nodes-base.httpRequest` | 4.2 |
| Pass-through / label | `n8n-nodes-base.noOp` | 1 |
| Schedule | `n8n-nodes-base.scheduleTrigger` | 1.2 |
| Webhook incoming | `n8n-nodes-base.webhook` | 2 |

## HTTP Request node parameters (typeVersion 4.2)

```json
{
  "method": "GET",
  "url": "http://localhost:3001/api/users",
  "sendHeaders": true,
  "headerParameters": {
    "parameters": [{ "name": "Content-Type", "value": "application/json" }]
  },
  "options": {}
}
```

## Layout rules

- Manual Trigger: position [0, 300]
- First column of service nodes: position [380, y] — space 140px vertically
- Second column (response handlers): position [700, y]

## URL conventions

- Backend services: `http://localhost:{port}/api/{resource}`
- Health checks: `http://localhost:{port}/health`
- Frontend: `http://localhost:{port}/`

## Output

Emit ONE file: `n8n_workflow.json`

Use `<FILE path="n8n_workflow.json">` tag. The JSON must be valid — no trailing commas, no comments.
