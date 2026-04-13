import passport from "passport";
import { Strategy as LocalStrategy } from "passport-local";
import { Express } from "express";
import session from "express-session";
import connectPgSimple from "connect-pg-simple";
import { scrypt, randomBytes, timingSafeEqual } from "crypto";
import { promisify } from "util";
import { db, pool } from "./db";
import { users } from "@shared/schema";
import { eq } from "drizzle-orm";

const PgSession = connectPgSimple(session);

const scryptAsync = promisify(scrypt);

async function hashPassword(password: string) {
  const salt = randomBytes(16).toString("hex");
  const buf = (await scryptAsync(password, salt, 64)) as Buffer;
  return `${buf.toString("hex")}.${salt}`;
}

async function comparePasswords(supplied: string, stored: string) {
  const [hashed, salt] = stored.split(".");
  const hashedBuf = Buffer.from(hashed, "hex");
  const suppliedBuf = (await scryptAsync(supplied, salt, 64)) as Buffer;
  return timingSafeEqual(hashedBuf, suppliedBuf);
}

export async function setupAuth(app: Express) {
  if (!process.env.SESSION_SECRET) {
    console.warn("[auth] WARNING: SESSION_SECRET env var not set. Using insecure fallback. Set it in .env for production.");
  }

  // Create the session table if it doesn't exist.
  // We do this manually to avoid connect-pg-simple reading table.sql
  // from a path that breaks inside an esbuild bundle (/app/dist/table.sql).
  await pool.query(`
    CREATE TABLE IF NOT EXISTS "session" (
      "sid" varchar NOT NULL COLLATE "default",
      "sess" json NOT NULL,
      "expire" timestamp(6) NOT NULL,
      CONSTRAINT "session_pkey" PRIMARY KEY ("sid")
    );
    CREATE INDEX IF NOT EXISTS "IDX_session_expire" ON "session" ("expire");
  `);

  // Gracefully alter the users table if columns don't exist (e.g. for already running containers)
  try {
    await pool.query(`ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "first_name" text;`);
    await pool.query(`ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "last_name" text;`);
  } catch (err) {
    console.warn("Could not alter users table:", err);
  }

  // Add trust proxy for container environments
  app.set("trust proxy", 1);

  const sessionSettings: session.SessionOptions = {
    store: new PgSession({
      pool,
      tableName: "session",
    }),
    secret: process.env.SESSION_SECRET || "inventory-optimization-secret",
    resave: true, // Force session to be saved back even if not modified
    saveUninitialized: true, // Force cookie for all visitors
    proxy: true, // Trust the headers set by the proxy (if any)
    cookie: {
      // Use explicit env var to control secure flag (default false for HTTP)
      secure: process.env.SESSION_COOKIE_SECURE === "true",
      httpOnly: true,
      sameSite: "lax",
      maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
    },
  };

  // Setup express-session
  app.use(session(sessionSettings));
  app.use(passport.initialize());
  app.use(passport.session());

  // Passport local strategy
  passport.use(
    new LocalStrategy(async (username, password, done) => {
      try {
        const [user] = await db.select().from(users).where(eq(users.username, username)).limit(1);
        if (!user) {
          return done(null, false, { message: "Incorrect username." });
        }
        const isValid = await comparePasswords(password, user.password);
        if (!isValid) {
          return done(null, false, { message: "Incorrect password." });
        }
        return done(null, user);
      } catch (err) {
        return done(err);
      }
    })
  );

  passport.serializeUser((user: any, done) => {
    done(null, user.id);
  });

  passport.deserializeUser(async (id: number, done) => {
    try {
      const [user] = await db.select().from(users).where(eq(users.id, id)).limit(1);
      done(null, user);
    } catch (err) {
      done(err);
    }
  });

  // Attach auth APIs
  app.post("/api/register", async (req, res, next) => {
    try {
      const { username, password, firstName, lastName } = req.body;
      if (!username || !password) {
        return res.status(400).send("Email and password are required.");
      }
      
      const [existingUser] = await db.select().from(users).where(eq(users.username, username)).limit(1);
      if (existingUser) {
        return res.status(400).send("Email already exists.");
      }

      const hashedPassword = await hashPassword(password);
      const [user] = await db.insert(users).values({
        username,
        password: hashedPassword,
        firstName: firstName || null,
        lastName: lastName || null,
      }).returning();

      req.login(user, (err) => {
        if (err) return next(err);
        req.session.save((err) => {
          if (err) return next(err);
          // Don't send back the password hash
          const { password: _, ...userWithoutPassword } = user;
          return res.json(userWithoutPassword);
        });
      });
    } catch (err) {
      next(err);
    }
  });

  app.patch("/api/user", async (req, res, next) => {
    if (!req.isAuthenticated()) {
      return res.status(401).send("Not authenticated");
    }

    try {
      const { firstName, lastName } = req.body;
      const currentUserId = (req.user as any).id;

      const [updatedUser] = await db
        .update(users)
        .set({
          firstName: firstName !== undefined ? firstName : (req.user as any).firstName,
          lastName: lastName !== undefined ? lastName : (req.user as any).lastName,
        })
        .where(eq(users.id, currentUserId))
        .returning();

      // Don't send back password
      const { password: _, ...userWithoutPassword } = updatedUser;
      
      // Update session payload representation (optional but recommended)
      req.user = updatedUser;

      return res.json(userWithoutPassword);
    } catch (err) {
      next(err);
    }
  });

  app.post("/api/login", (req, res, next) => {
    passport.authenticate("local", (err: any, user: any, info: any) => {
      if (err) return next(err);
      if (!user) return res.status(401).send(info?.message || "Login failed");
      
      req.login(user, (err) => {
        if (err) return next(err);
        req.session.save((err) => {
          if (err) return next(err);
          // Don't send back the password hash
          const { password: _, ...userWithoutPassword } = user;
          return res.json(userWithoutPassword);
        });
      });
    })(req, res, next);
  });

  app.post("/api/logout", (req, res, next) => {
    req.logout((err) => {
      if (err) return next(err);
      req.session.destroy((err) => {
        if (err) return next(err);
        res.send("Logged out");
      });
    });
  });

  app.get("/api/user", (req, res) => {
    if (req.isAuthenticated()) {
      // Don't send back the password hash
      const { password: _, ...userWithoutPassword } = req.user as any;
      return res.json(userWithoutPassword);
    }
    return res.status(401).send("Not authenticated");
  });
}
