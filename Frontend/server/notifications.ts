import amqplib from 'amqplib';
import { io } from './index';

const RABBITMQ_URL = process.env.RABBITMQ_URL || "amqp://guest:guest@localhost:5672/";

export async function setupNotifications() {
  try {
    const conn = await amqplib.connect(RABBITMQ_URL);
    const channel = await conn.createChannel();
    
    // Assert the fanout exchange where Python worker broadcasts
    await channel.assertExchange('ui_updates', 'fanout', { durable: false });
    
    // Create an exclusive queue for this Node.js instance
    const q = await channel.assertQueue('', { exclusive: true });
    
    // Bind our queue to the exchange
    await channel.bindQueue(q.queue, 'ui_updates', '');
    
    channel.consume(q.queue, (msg) => {
      if (msg) {
        try {
          const content = msg.content.toString();
          const parsed = JSON.parse(content);
          // Broadcast to all connected socket.io clients
          io.emit('notification', parsed);
        } catch (e) {
          console.error("Failed to parse ui_update message:", e);
        }
      }
    }, { noAck: true });
    
    console.log("🚀 Connected to RabbitMQ for UI notifications.");
  } catch (err) {
    console.error("❌ Failed to connect to RabbitMQ for notifications:", err);
  }
}
