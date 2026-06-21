import { Resend } from "resend";

const RESEND_API_KEY = process.env.RESEND_API_KEY;
if (!RESEND_API_KEY) {
  throw new Error("RESEND_API_KEY environment variable is required.");
}
// Resend uses HTTPS (port 443) — never blocked by cloud providers.
// SMTP (ports 25/465/587) is blocked by DigitalOcean by default.
const resend = new Resend(RESEND_API_KEY);

// The "from" address must be a verified domain or use Resend's shared domain for testing.
// For testing without a custom domain: "onboarding@resend.dev" (only delivers to your own email)
// For production with a custom domain: "Replenix <noreply@yourdomain.com>"
const RESEND_FROM_EMAIL = process.env.RESEND_FROM;
if (!RESEND_FROM_EMAIL) {
  throw new Error("RESEND_FROM environment variable is required.");
}
const FROM_ADDRESS = RESEND_FROM_EMAIL.includes("<") ? RESEND_FROM_EMAIL : `Replenix <${RESEND_FROM_EMAIL}>`;
const ADMIN_EMAIL = process.env.SMTP_USER || process.env.RESEND_TO || "";

/**
 * Send an email notification when a user logs in.
 */
export async function sendLoginNotification(username: string, email: string) {
  try {
    const { data, error } = await resend.emails.send({
      from: FROM_ADDRESS,
      to: [email],
      subject: "🔔 New Login: Replenix System",
      html: `<p>Hello,</p><p>A new login was detected on the <b>Replenix System</b> for the user: <b>${username}</b>.</p><p>Time: ${new Date().toLocaleString()}</p><br/><p>Regards,<br/>Replenix Automated System</p>`,
    });
    if (error) {
      console.error("Login email error from Resend:", error);
    } else {
      console.log("Login email notification sent:", data?.id);
    }
  } catch (error) {
    console.error("Error sending login email notification:", error);
  }
}

/**
 * Send an email notification when training is complete.
 */
export async function sendTrainingCompleteNotification(email: string, payload: any = {}) {
  try {
    const {
      sku = "Unknown",
      episodes = 0,
      best_reward = 0,
      rl_reward = 0,
      oracle_reward = 0,
      rule_reward = 0,
      rl_vs_oracle_pct = 0,
      run_id = "N/A",
    } = payload;

    const formatter = new Intl.NumberFormat("en-US");

    const htmlBody = `<div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; line-height: 1.6;">
      <h2 style="color: #4F46E5;">Training Complete: Replenix Model</h2>
      <p>Hello,</p>
      <p>The recent AI model training pipeline has <b>successfully finished running</b> for SKU: <b>${sku}</b>.</p>
      
      <div style="background-color: #F3F4F6; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <h3 style="margin-top: 0; color: #111827;">Training Summary</h3>
        <ul style="list-style-type: none; padding-left: 0;">
          <li><b>SKU:</b> ${sku}</li>
          <li><b>Run ID:</b> ${run_id}</li>
          <li><b>Episodes Trained:</b> ${episodes}</li>
          <li><b>Best Training Reward:</b> ${formatter.format(best_reward)}</li>
        </ul>
      </div>

      <div style="background-color: #F3F4F6; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <h3 style="margin-top: 0; color: #111827;">Evaluation Performance (vs Baselines)</h3>
        <table style="width: 100%; border-collapse: collapse;">
          <tr>
            <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB;">🤖 RL Agent Reward</td>
            <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB; text-align: right; font-weight: bold;">${formatter.format(rl_reward)}</td>
          </tr>
          <tr>
            <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB;">📏 Rule-based Reward</td>
            <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB; text-align: right; font-weight: bold;">${formatter.format(rule_reward)}</td>
          </tr>
          <tr>
            <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB;">🔮 Perfect Oracle Reward</td>
            <td style="padding: 8px 0; border-bottom: 1px solid #E5E7EB; text-align: right; font-weight: bold;">${formatter.format(oracle_reward)}</td>
          </tr>
          <tr>
            <td style="padding: 8px 0;">📊 Performance vs Oracle</td>
            <td style="padding: 8px 0; text-align: right; font-weight: bold; color: ${rl_vs_oracle_pct > 80 ? "#10B981" : "#F59E0B"};">${rl_vs_oracle_pct ? rl_vs_oracle_pct.toFixed(2) + "%" : "N/A"}</td>
          </tr>
        </table>
      </div>

      <p>You can now review the latest plots, metrics, and updated optimal reorder points directly in the Replenix Dashboard.</p>
      <br/>
      <p style="color: #6B7280; font-size: 0.9em;">Regards,<br/><b>Replenix Automated System</b></p>
    </div>`;

    const { data, error } = await resend.emails.send({
      from: FROM_ADDRESS,
      to: [email],
      subject: `Training Complete: ${sku} | Replenix Model`,
      html: htmlBody,
    });

    if (error) {
      console.error("Training email error from Resend:", error);
    } else {
      console.log("Training complete email notification sent:", data?.id);
    }
  } catch (error) {
    console.error("Error sending training complete email notification:", error);
  }
}

/**
 * Send an email with the exported inventory/training report attached.
 */
export async function sendExportReportEmail(email: string, filename: string, fileBuffer: Buffer) {
  try {
    const htmlBody = `<div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; line-height: 1.6;">
      <h2 style="color: #4F46E5;">Your Replenix Export Report</h2>
      <p>Hello,</p>
      <p>Please find attached the inventory report you requested from the Replenix Dashboard.</p>
      <br/>
      <p style="color: #6B7280; font-size: 0.9em;">Regards,<br/><b>Replenix Automated System</b></p>
    </div>`;

    const { data, error } = await resend.emails.send({
      from: FROM_ADDRESS,
      to: [email],
      subject: `Replenix Export Report: ${filename}`,
      html: htmlBody,
      attachments: [
        {
          filename: filename,
          content: fileBuffer,
        }
      ]
    });

    if (error) {
      console.error("Export email error from Resend:", error);
      throw error;
    } else {
      console.log("Export email sent:", data?.id);
    }
  } catch (error) {
    console.error("Error sending export email:", error);
    throw error;
  }
}
