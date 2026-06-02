import nodemailer from "nodemailer";

// Configure Nodemailer transporter using provided environment variables
const transporter = nodemailer.createTransport({
  service: "gmail",
  host: process.env.SMTP_HOST || "smtp.gmail.com",
  port: parseInt(process.env.SMTP_PORT || "587"),
  secure: false, // true for 465, false for other ports
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS,
  },
});

/**
 * Send an email notification when a user logs in.
 * @param username The username that just logged in.
 * @param email The user's email address (or admin address if we want to notify admins).
 */
export async function sendLoginNotification(username: string, email: string) {
  try {
    const info = await transporter.sendMail({
      from: `"Replenix System" <${process.env.SMTP_USER}>`, // sender address
      to: email, // list of receivers
      subject: "🔔 New Login: Replenix System", // Subject line
      text: `Hello,\n\nA new login was detected on the Replenix System for the user: ${username}.\nTime: ${new Date().toLocaleString()}\n\nRegards,\nReplenix Automated System`, // plain text body
      html: `<p>Hello,</p><p>A new login was detected on the <b>Replenix System</b> for the user: <b>${username}</b>.</p><p>Time: ${new Date().toLocaleString()}</p><br/><p>Regards,<br/>Replenix Automated System</p>`, // html body
    });
    console.log("Login email notification sent: %s", info.messageId);
  } catch (error) {
    console.error("Error sending login email notification:", error);
  }
}

/**
 * Send an email notification when training is complete.
 * @param email The user's email address (or admin address).
 */
export async function sendTrainingCompleteNotification(email: string, payload: any = {}) {
  try {
    const {
      sku = 'Unknown',
      episodes = 0,
      best_reward = 0,
      rl_reward = 0,
      oracle_reward = 0,
      rule_reward = 0,
      rl_vs_oracle_pct = 0,
      run_id = 'N/A'
    } = payload;

    const formatter = new Intl.NumberFormat('en-US');

    // Attempt to format a nicely structured email with the results
    const textBody = `Hello,

The recent AI model training pipeline has successfully finished running for SKU: ${sku}.

Training Summary:
- Episodes Trained: ${episodes}
- Best Training Reward: ${formatter.format(best_reward)}

Evaluation Performance (vs Baselines):
- RL Agent Reward: ${formatter.format(rl_reward)}
- Rule-based Reward: ${formatter.format(rule_reward)}
- Perfect Oracle Reward: ${formatter.format(oracle_reward)}
- Performance vs Oracle: ${rl_vs_oracle_pct ? rl_vs_oracle_pct.toFixed(2) + '%' : 'N/A'}

You can now review the latest metrics and updated optimal reorder points in the dashboard.

Regards,
Replenix Automated System`;

    const htmlBody = `<div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; line-height: 1.6;">
      <h2 style="color: #4F46E5;">Training Complete: Replenix Model</h2>
      <p>Hello,</p>
      <p>The recent AI model training pipeline has <b>successfully finished running</b> for SKU: <b>${sku}</b>.</p>
      
      <div style="background-color: #F3F4F6; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <h3 style="margin-top: 0; color: #111827;">Training Summary</h3>
        <ul style="list-style-type: none; padding-left: 0;">
          <li><b>SKU:</b> ${sku}</li>
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
            <td style="padding: 8px 0; text-align: right; font-weight: bold; color: ${rl_vs_oracle_pct > 80 ? '#10B981' : '#F59E0B'};">${rl_vs_oracle_pct ? rl_vs_oracle_pct.toFixed(2) + '%' : 'N/A'}</td>
          </tr>
        </table>
      </div>

      <p>You can now review the latest plots, metrics, and updated optimal reorder points directly in the Replenix Dashboard.</p>
      
      <br/>
      <p style="color: #6B7280; font-size: 0.9em;">Regards,<br/><b>Replenix Automated System</b></p>
    </div>`;

    const info = await transporter.sendMail({
      from: `"Replenix System" <${process.env.SMTP_USER}>`,
      to: email,
      subject: `Training Complete: ${sku} | Replenix Model`,
      text: textBody,
      html: htmlBody,
    });
    console.log("Training complete email notification sent: %s", info.messageId);
  } catch (error) {
    console.error("Error sending training complete email notification:", error);
  }
}
