import express from 'express';
import type { Express } from 'express';
import amqplib from 'amqplib';
import crypto from 'crypto';

const RABBITMQ_URL = process.env.RABBITMQ_URL || "amqp://guest:guest@localhost:5672/";
const ERP_HMAC_SECRET = process.env.ERP_HMAC_SECRET || "erp_secret_123";

let channel: amqplib.Channel;

async function connectRabbitMQ() {
  try {
    const conn = await amqplib.connect(RABBITMQ_URL);
    channel = await conn.createChannel();
    await channel.assertQueue('erp_ingestion', { durable: true });
    console.log("🚀 Connected to RabbitMQ for ERP webhooks.");
  } catch (error) {
    console.error("❌ Failed to connect to RabbitMQ from webhook routes:", error);
  }
}

export function registerWebhookRoutes(app: Express) {
  // Connect to AMQP asynchronously
  connectRabbitMQ();

  const router = express.Router();
  
  router.post('/erp', async (req, res) => {
    // 1. Signature Validation (HMAC)
    const signature = req.headers['x-erp-signature'] as string;
    
    if (req.rawBody && signature) {
      const expectedSig = crypto.createHmac('sha256', ERP_HMAC_SECRET)
        .update(req.rawBody as Buffer)
        .digest('hex');
      
      if (signature !== expectedSig) {
        return res.status(401).json({ error: "Invalid signature" });
      }
    } else if (!signature) {
      // In strict production mode, reject without signature. Since this is testing, we log it.
      console.warn("⚠️ ERP Webhook received without signature. Proceeding for dev.");
    }

    if (!channel) {
       return res.status(503).json({ error: "Message broker temporarily offline." });
    }
    
    const event = req.body;
    
    // 2. Publish to AMQP
    try {
      const messageBuffer = Buffer.from(JSON.stringify(event));
      channel.sendToQueue('erp_ingestion', messageBuffer, { persistent: true });
      return res.status(200).json({ status: "success", message: "Event queued for RL processing" });
    } catch (e) {
      console.error("Failed to enqueue ERP webhook:", e);
      return res.status(500).json({ status: "error", error: "Internal processing error" });
    }
  });

  router.post('/notify/training-complete', async (req, res) => {
    try {
      // Need to import dynamically to avoid circular dependencies if any
      const { sendTrainingCompleteNotification } = await import('./email');
      const { db } = await import('./db');
      const { users } = await import('@shared/schema');
      const allUsers = await db.select().from(users);
      
      const payload = req.body || {};
      
      if (allUsers.length > 0) {
        for (const user of allUsers) {
          await sendTrainingCompleteNotification(user.username, payload);
        }
      } else if (process.env.SMTP_USER) {
        await sendTrainingCompleteNotification(process.env.SMTP_USER, payload); // fallback
      }
      return res.status(200).json({ status: "success", message: "Notification sent successfully" });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ status: "error", error: "Failed to send notification" });
    }
  });

  // Mount at /api/webhooks
  app.use('/api/webhooks', router);
}
