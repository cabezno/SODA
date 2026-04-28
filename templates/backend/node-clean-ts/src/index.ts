# --- METADATA SODA ---
# goal_id: backend-entrypoint
# role: main-orchestrator
# ---

import Fastify from 'fastify';

const fastify = Fastify({ logger: true });

const start = async () => {
  try {
    await fastify.listen({ port: 3000, host: '0.0.0.0' });
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};

start();
