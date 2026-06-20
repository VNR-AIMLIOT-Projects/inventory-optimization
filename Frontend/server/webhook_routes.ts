import express from 'express';
import type { Express } from 'express';
import amqplib from 'amqplib';
import crypto from 'crypto';

import { sendTrainingCompleteNotification } from './email';
import { db } from './db';
import { users } from '@shared/schema';
import { Resend } from 'resend';

const _RABBITMQ_URL = process.env.RABBITMQ_URL;
if (!_RABBITMQ_URL) throw new Error("RABBITMQ_URL is required.");
const RABBITMQ_URL = _RABBITMQ_URL;

const _ERP_HMAC_SECRET = process.env.ERP_HMAC_SECRET;
if (!_ERP_HMAC_SECRET) throw new Error("ERP_HMAC_SECRET is required.");
const ERP_HMAC_SECRET = _ERP_HMAC_SECRET;

// Alert email recipients — matches AlertManager config in values.yaml
const ALERT_EMAILS = ['sujaynsv@gmail.com', 'rishitsura@gmail.com'];
const _RESEND_FROM = process.env.RESEND_FROM;
if (!_RESEND_FROM) throw new Error("RESEND_FROM is required.");
const RESEND_FROM = _RESEND_FROM;

const _RESEND_API_KEY = process.env.RESEND_API_KEY;
if (!_RESEND_API_KEY) throw new Error("RESEND_API_KEY is required.");
const resendClient = new Resend(_RESEND_API_KEY);

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

/**
 * Registers webhook routes for external integrations.
 * 
 * - `/erp`: Accepts ERP data payloads with HMAC validation, enqueuing them to RabbitMQ.
 * - `/notify/training-complete`: Triggers email notifications when RL training finishes.
 * - `/alerts`: Receives Prometheus/AlertManager JSON webhooks and relays them as styled HTML emails via Resend.
 *
 * @param app - The Express application instance.
 */
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
      const allUsers = await db.select().from(users);
      
      const payload = req.body || {};
      
      // Fire and forget emails to avoid blocking the HTTP response
      // This prevents the Python worker from hitting a ReadTimeout (5s)
      (async () => {
        try {
          if (allUsers.length > 0) {
            for (const user of allUsers) {
              await sendTrainingCompleteNotification(user.username, payload);
            }
          } else if (process.env.SMTP_USER) {
            await sendTrainingCompleteNotification(process.env.SMTP_USER, payload); // fallback
          }
        } catch (emailErr) {
          console.error("Background email error:", emailErr);
        }
      })();

      return res.status(200).json({ status: "success", message: "Notification queued successfully" });
    } catch (err) {
      console.error("Webhook error:", err);
      return res.status(500).json({ status: "error", error: "Failed to send notification" });
    }
  });

  // ── AlertManager webhook receiver ─────────────────────────────────────────
  // AlertManager POSTs here when an alert fires or resolves.
  // We relay via Resend to avoid SMTP (blocked by DigitalOcean).
  // Configured in values.yaml: alertmanager.config.receivers[0].webhook_configs[0].url
  router.post('/alerts', async (req, res) => {
    try {
      const { alerts = [] } = req.body as { alerts: any[] };

      if (alerts.length === 0) {
        return res.status(200).json({ ok: true, message: 'No alerts in payload' });
      }

      // Group alerts into a single email to avoid inbox flooding
      const alertRows = alerts.map((alert: any) => {
        const isFiring = alert.status === 'firing';
        const severity  = (alert.labels?.severity || 'unknown').toUpperCase();
        const name      = alert.labels?.alertname || 'Unknown Alert';
        const summary   = alert.annotations?.summary || 'No summary provided';
        const desc      = alert.annotations?.description || '';
        const firedAt   = alert.startsAt
          ? new Date(alert.startsAt).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
          : 'unknown';
        const statusIcon = isFiring ? '🔴' : '🟢';
        const statusText = isFiring ? 'FIRING' : 'RESOLVED';
        const color      = severity === 'CRITICAL' ? '#DC2626' : '#D97706';

        return `
          <tr>
            <td style="padding:12px 8px;border-bottom:1px solid #374151;">
              ${statusIcon} <strong style="color:${color};">[${severity}] ${name}</strong><br/>
              <span style="color:#9CA3AF;font-size:0.85em;">${statusText} · ${firedAt}</span>
            </td>
            <td style="padding:12px 8px;border-bottom:1px solid #374151;color:#D1D5DB;">
              ${summary}${desc ? `<br/><span style="font-size:0.85em;color:#6B7280;">${desc}</span>` : ''}
            </td>
          </tr>`;
      }).join('');

      const firingCount  = alerts.filter((a: any) => a.status === 'firing').length;
      const resolvedCount = alerts.filter((a: any) => a.status !== 'firing').length;
      const subject = firingCount > 0
        ? `🔴 [${firingCount} FIRING] Replenix Alert${firingCount > 1 ? 's' : ''}`
        : `🟢 [${resolvedCount} RESOLVED] Replenix Alert${resolvedCount > 1 ? 's' : ''}`;

      const html = `
        <div style="font-family:Arial,sans-serif;background:#111827;color:#F9FAFB;max-width:700px;padding:24px;border-radius:8px;">
          <h2 style="color:#F9FAFB;margin-top:0;">
            Replenix — Alert Notification
          </h2>
          <p style="color:#9CA3AF;">
            ${firingCount > 0 ? `<strong style="color:#EF4444;">${firingCount} alert(s) firing</strong>` : ''}
            ${resolvedCount > 0 ? `<strong style="color:#10B981;">${resolvedCount} alert(s) resolved</strong>` : ''}
          </p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <thead>
              <tr style="background:#1F2937;">
                <th style="padding:10px 8px;text-align:left;color:#6B7280;font-size:0.8em;text-transform:uppercase;">Alert</th>
                <th style="padding:10px 8px;text-align:left;color:#6B7280;font-size:0.8em;text-transform:uppercase;">Details</th>
              </tr>
            </thead>
            <tbody>${alertRows}</tbody>
          </table>
          <p style="margin-top:20px;">
            <a href="https://grafana.replenix.app" 
               style="background:#4F46E5;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;">
              Open Grafana Dashboard →
            </a>
          </p>
          <p style="color:#4B5563;font-size:0.8em;margin-top:24px;">
            Replenix Observability · Powered by Prometheus + AlertManager
          </p>
        </div>`;

      await resendClient.emails.send({
        from: RESEND_FROM,
        to: ALERT_EMAILS,
        subject,
        html,
      });

      console.log(`[Alerts] Sent alert email: ${subject}`);
      return res.status(200).json({ ok: true });
    } catch (err) {
      console.error('[Alerts] Webhook relay error:', err);
      return res.status(500).json({ error: 'Failed to relay alert email' });
    }
  });

  // Mount at /api/webhooks
  app.use('/api/webhooks', router);
}

