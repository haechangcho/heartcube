/* eslint-disable global-require,no-restricted-syntax */
import dotenv from '@cubejs-backend/dotenv';
import { CubePreAggregationConverter, CubeSchemaConverter, ScaffoldingTemplate, SchemaFormat } from '@cubejs-backend/schema-compiler';
import spawn from 'cross-spawn';
import path from 'path';
import fs from 'fs-extra';
import { getRequestIdFromRequest } from '@cubejs-backend/api-gateway';
import { LivePreviewWatcher } from '@cubejs-backend/cloud';
import { AppContainer, DependencyTree, PackageFetcher, DevPackageFetcher } from '@cubejs-backend/templates';
import jwt from 'jsonwebtoken';
import isDocker from 'is-docker';
import type { Application as ExpressApplication, NextFunction, Request, Response } from 'express';
import type { ChildProcess } from 'child_process';
import { executeCommand, getAnonymousId, getEnv, keyByDataSource, packageExists } from '@cubejs-backend/shared';
import crypto from 'crypto';

import type { BaseDriver } from '@cubejs-backend/query-orchestrator';

import { CubejsServerCore } from './server';
import { ExternalDbTypeFn, ServerCoreInitializedOptions, DatabaseType } from './types';
import DriverDependencies from './DriverDependencies';

const repo = {
  owner: 'cube-js',
  name: 'cubejs-playground-templates'
};

type DevServerOptions = {
  externalDbTypeFn: ExternalDbTypeFn;
  isReadyForQueryProcessing: () => boolean;
  dockerVersion?: string;
};

type WebSecurityContext = {
  sub: string;
  groups: string[];
  [key: string]: any;
};

type WebLoginUser = {
  password: string;
  securityContext: WebSecurityContext;
};

type WebSession = {
  securityContext: WebSecurityContext;
  iat: number;
  exp: number;
};

const WEB_SESSION_COOKIE = 'heartcube_session';

function timingSafeEqual(a: string, b: string): boolean {
  const aBuffer = Buffer.from(a);
  const bBuffer = Buffer.from(b);

  if (aBuffer.length !== bBuffer.length) {
    return false;
  }

  return crypto.timingSafeEqual(aBuffer, bBuffer);
}

function parseCookies(cookieHeader?: string): Record<string, string> {
  if (!cookieHeader) {
    return {};
  }

  return cookieHeader.split(';').reduce((cookies, rawCookie) => {
    const separatorIndex = rawCookie.indexOf('=');
    if (separatorIndex === -1) {
      return cookies;
    }

    const name = rawCookie.slice(0, separatorIndex).trim();
    const value = rawCookie.slice(separatorIndex + 1).trim();
    if (name) {
      cookies[name] = decodeURIComponent(value);
    }
    return cookies;
  }, {} as Record<string, string>);
}

function serializeCookie(name: string, value: string, options: {
  httpOnly?: boolean;
  maxAge?: number;
  sameSite?: 'Lax' | 'Strict' | 'None';
  secure?: boolean;
  path?: string;
} = {}): string {
  const parts = [
    `${name}=${encodeURIComponent(value)}`,
    `Path=${options.path || '/'}`,
  ];

  if (options.maxAge !== undefined) {
    parts.push(`Max-Age=${options.maxAge}`);
  }
  if (options.httpOnly) {
    parts.push('HttpOnly');
  }
  if (options.sameSite) {
    parts.push(`SameSite=${options.sameSite}`);
  }
  if (options.secure) {
    parts.push('Secure');
  }

  return parts.join('; ');
}

function signSession(session: WebSession, secret: string): string {
  const payload = Buffer.from(JSON.stringify(session)).toString('base64url');
  const signature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('base64url');

  return `${payload}.${signature}`;
}

function verifySession(value: string | undefined, secret: string): WebSession | null {
  if (!value) {
    return null;
  }

  const [payload, signature, ...rest] = value.split('.');
  if (!payload || !signature || rest.length > 0) {
    return null;
  }

  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('base64url');

  if (!timingSafeEqual(signature, expectedSignature)) {
    return null;
  }

  try {
    const session = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')) as WebSession;
    if (!session || typeof session.exp !== 'number' || Date.now() / 1000 >= session.exp) {
      return null;
    }
    if (!isValidSecurityContext(session.securityContext)) {
      return null;
    }
    return session;
  } catch (e) {
    return null;
  }
}

function isValidSecurityContext(securityContext: any): securityContext is WebSecurityContext {
  return Boolean(
    securityContext &&
    typeof securityContext.sub === 'string' &&
    securityContext.sub.trim() &&
    Array.isArray(securityContext.groups) &&
    securityContext.groups.length > 0 &&
    securityContext.groups.every((group) => typeof group === 'string' && group.trim())
  );
}

function defaultWebLoginUsers(): Record<string, WebLoginUser> {
  return {
    guest: {
      password: process.env.CUBEJS_WEB_GUEST_PASSWORD || 'guest',
      securityContext: {
        sub: 'guest_01',
        groups: ['guest'],
      },
    },
    analyst: {
      password: process.env.CUBEJS_WEB_ANALYST_PASSWORD || 'analyst',
      securityContext: {
        sub: 'analyst_01',
        groups: ['analyst'],
      },
    },
    audit: {
      password: process.env.CUBEJS_WEB_AUDIT_PASSWORD || 'audit',
      securityContext: {
        sub: 'audit_01',
        groups: ['audit'],
      },
    },
    manager_seoul: {
      password: process.env.CUBEJS_WEB_MANAGER_SEOUL_PASSWORD || 'manager_seoul',
      securityContext: {
        sub: 'manager_seoul_01',
        groups: ['regional_manager'],
        claim_center: '서울본부',
      },
    },
    admin: {
      password: process.env.CUBEJS_WEB_ADMIN_PASSWORD || 'admin',
      securityContext: {
        sub: 'admin_01',
        groups: ['admin'],
      },
    },
  };
}

function loadWebLoginUsers(): Record<string, WebLoginUser> {
  const users = defaultWebLoginUsers();

  Object.entries(users).forEach(([username, user]) => {
    if (
      !user ||
      typeof user.password !== 'string' ||
      !user.password ||
      !isValidSecurityContext(user.securityContext)
    ) {
      throw new Error(`Invalid web login user entry for "${username}"`);
    }
  });

  return users;
}

function renderLoginPage(error?: string): string {
  const safeError = error ? String(error).replace(/[<>&"]/g, '') : '';

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Heartcube Login</title>
  <style>
    :root {
      --dark-02-color: #14171f;
      --surface: #ffffff;
      --border: #d9d9d9;
      --primary: #1890ff;
      --primary-hover: #40a9ff;
      --text: rgba(0, 0, 0, 0.85);
      --muted: rgba(0, 0, 0, 0.45);
      color: var(--text);
      background: #f0f2f5;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    body {
      min-height: 100vh;
      margin: 0;
      background: linear-gradient(180deg, #f7f9fc 0%, #eef1f7 100%);
    }
    header {
      height: 48px;
      padding: 0 16px;
      display: flex;
      align-items: center;
      background: var(--dark-02-color);
      box-sizing: border-box;
    }
    header img {
      height: 28px;
      margin-right: 28px;
    }
    header span {
      color: rgba(255, 255, 255, 0.72);
      font-size: 15px;
      font-weight: 500;
      line-height: 48px;
    }
    .page {
      min-height: calc(100vh - 48px);
      display: grid;
      place-items: center;
      padding: 32px 16px;
      box-sizing: border-box;
    }
    main {
      width: min(380px, 100%);
      padding: 32px;
      border: 1px solid var(--border);
      border-radius: 2px;
      background: var(--surface);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
      box-sizing: border-box;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 24px;
      font-weight: 600;
      letter-spacing: -0.02em;
    }
    p {
      margin: 0 0 24px;
      color: var(--muted);
      font-size: 14px;
    }
    label {
      display: block;
      margin: 16px 0 8px;
      font-size: 14px;
      font-weight: 500;
    }
    input {
      box-sizing: border-box;
      width: 100%;
      height: 40px;
      padding: 4px 11px;
      border: 1px solid var(--border);
      border-radius: 2px;
      background: #fff;
      color: var(--text);
      font: inherit;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
      outline: 0;
    }
    button {
      width: 100%;
      height: 40px;
      margin-top: 24px;
      padding: 4px 15px;
      border: 1px solid var(--primary);
      border-radius: 2px;
      background: var(--primary);
      color: #fff;
      cursor: pointer;
      font: inherit;
      line-height: 1.5715;
      transition: background 0.2s, border-color 0.2s;
    }
    button:hover {
      border-color: var(--primary-hover);
      background: var(--primary-hover);
    }
    .error {
      display: ${safeError ? 'block' : 'none'};
      margin-bottom: 16px;
      padding: 8px 12px;
      border: 1px solid #ffccc7;
      border-radius: 2px;
      background: #fff2f0;
      color: #cf1322;
      font-size: 14px;
    }
  </style>
</head>
<body>
  <header>
    <img src="./cube-core-logo-adapted_for_dark_bg.svg" alt="Cube" />
    <span>Heartcube Playground</span>
  </header>
  <div class="page">
    <main>
      <h1>Sign in</h1>
      <p>Use a test account to open the Cube Playground.</p>
      <div id="error" class="error">${safeError}</div>
      <form id="login-form">
        <label for="username">ID</label>
        <input id="username" name="username" autocomplete="username" autofocus required />
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="submit">Sign in</button>
      </form>
    </main>
  </div>
  <script>
    const form = document.getElementById('login-form');
    const error = document.getElementById('error');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      error.style.display = 'none';
      const body = {
        username: form.username.value,
        password: form.password.value,
      };
      const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (response.ok) {
        window.location.assign('/');
        return;
      }
      const json = await response.json().catch(() => ({ error: 'Login failed' }));
      error.textContent = json.error || 'Login failed';
      error.style.display = 'block';
    });
  </script>
</body>
</html>`;
}

export class DevServer {
  protected applyTemplatePackagesPromise: Promise<any> | null = null;

  protected dashboardAppProcess: ChildProcess & { dashboardUrlPromise?: Promise<any> } | null = null;

  protected livePreviewWatcher = new LivePreviewWatcher();

  public constructor(
    protected readonly cubejsServer: CubejsServerCore,
    protected readonly options: DevServerOptions
  ) {
  }

  public initDevEnv(app: ExpressApplication, options: ServerCoreInitializedOptions) {
    const port = process.env.PORT || 4000; // TODO
    const apiUrl = process.env.CUBEJS_API_URL || `http://localhost:${port}`;
    const webLoginEnabled = process.env.CUBEJS_WEB_LOGIN_ENABLED !== 'false';
    const webLoginUsers = webLoginEnabled ? loadWebLoginUsers() : {};
    const webSessionTtlSeconds = Number(process.env.CUBEJS_WEB_SESSION_TTL_SECONDS || 8 * 60 * 60);
    const webSessionSecret = options.apiSecret || 'secret';
    const isSecureCookie = process.env.CUBEJS_WEB_SECURE_COOKIE === 'true';

    const playgroundSecurityContext: WebSecurityContext = {
      sub: process.env.CUBEJS_PLAYGROUND_SUB || 'playground_admin',
      groups: (process.env.CUBEJS_PLAYGROUND_GROUPS || 'admin')
        .split(',')
        .map((group) => group.trim())
        .filter(Boolean),
    };

    const createCubejsToken = (securityContext: WebSecurityContext) => jwt.sign(
      securityContext,
      options.apiSecret || 'secret',
      { expiresIn: process.env.CUBEJS_WEB_JWT_TTL || '1h' }
    );

    const getWebSession = (req: Request): WebSession | null => {
      if (!webLoginEnabled) {
        const now = Math.floor(Date.now() / 1000);
        return {
          securityContext: playgroundSecurityContext,
          iat: now,
          exp: now + webSessionTtlSeconds,
        };
      }

      return verifySession(parseCookies(req.headers.cookie)[WEB_SESSION_COOKIE], webSessionSecret);
    };

    const isAdminSession = (session: WebSession | null): boolean => (
      Boolean(session?.securityContext.groups.includes('admin'))
    );

    const redirectOrRejectLogin = (req: Request, res: Response) => {
      if ((req.headers.accept || '').includes('text/html')) {
        res.redirect('/login');
        return;
      }
      res.status(401).json({ error: 'Login required' });
    };

    const requireWebSession = (req: Request, res: Response): WebSession | null => {
      const session = getWebSession(req);
      if (!session) {
        redirectOrRejectLogin(req, res);
        return null;
      }
      return session;
    };

    const requireWebAdmin = (req: Request, res: Response): WebSession | null => {
      const session = requireWebSession(req, res);
      if (!session) {
        return null;
      }
      if (!isAdminSession(session)) {
        res.status(403).json({ error: 'Admin permission required' });
        return null;
      }
      return session;
    };

    const setSessionCookie = (res: Response, securityContext: WebSecurityContext) => {
      const now = Math.floor(Date.now() / 1000);
      const session: WebSession = {
        securityContext,
        iat: now,
        exp: now + webSessionTtlSeconds,
      };
      res.setHeader('Set-Cookie', serializeCookie(
        WEB_SESSION_COOKIE,
        signSession(session, webSessionSecret),
        {
          httpOnly: true,
          sameSite: 'Lax',
          secure: isSecureCookie,
          maxAge: webSessionTtlSeconds,
        }
      ));
    };

    const clearSessionCookie = (res: Response) => {
      res.setHeader('Set-Cookie', serializeCookie(WEB_SESSION_COOKIE, '', {
        httpOnly: true,
        sameSite: 'Lax',
        secure: isSecureCookie,
        maxAge: 0,
      }));
    };

    if (process.env.NODE_ENV !== 'production') {
      console.log('🔓 Authentication checks are disabled in developer mode. Please use NODE_ENV=production to enable it.');
    } else {
      console.log(`🔒 Heartcube web login is ${webLoginEnabled ? 'enabled' : 'disabled'}.`);
    }
    console.log(`🦅 Dev environment available at ${apiUrl}`);

    if (
      (
        this.options.externalDbTypeFn({
          authInfo: null,
          securityContext: null,
          requestId: '',
        }) || ''
      ).toLowerCase() !== 'cubestore'
    ) {
      console.log('⚠️  Your pre-aggregations will be on an external database. It is recommended to use Cube Store for optimal performance');
    }

    this.cubejsServer.event('Dev Server Start');
    const serveStatic = require('serve-static');

    const catchErrors = (handler) => async (req, res, next) => {
      try {
        await handler(req, res, next);
      } catch (e) {
        const errorString = ((e as Error).stack || e).toString();
        console.error(errorString);
        this.cubejsServer.event('Dev Server Error', { error: errorString });

        // We don't know what state response is left at here:
        // It could be corked, headers could be sent, body could be sent completely or partially

        // Also, because we pass `next` to handler without any wrapper we don't know if it was called or not
        // Hence, we shouldn't call it for error handling

        try {
          while (res.writableCorked > 0) {
            res.uncork();
          }

          if (res.writableEnded) {
            // There's nothing we can do for response, error happened after call to end()
          } else if (res.headersSent) {
            // If header is already sent, we can't alter any of it, so best we can do is just terminate body
            res.end();
          } else {
            res.status(500).json({ error: errorString });
          }
        } catch (send500Error) {
          const send500ErrorString = ((send500Error as Error).stack || send500Error).toString();
          console.error(send500ErrorString);
          this.cubejsServer.event('Dev Server Error', { error: send500ErrorString });
          res.destroy(send500Error);
        }
      }
    };

    app.get('/login', catchErrors((req: Request, res: Response) => {
      if (!webLoginEnabled) {
        res.redirect('/');
        return;
      }
      if (getWebSession(req)) {
        res.redirect('/');
        return;
      }
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.send(renderLoginPage());
    }));

    app.post('/login', catchErrors((req: Request, res: Response) => {
      if (!webLoginEnabled) {
        res.json({ ok: true });
        return;
      }

      const { username = '', password = '' } = req.body || {};
      const user = webLoginUsers[String(username)];
      if (!user || !timingSafeEqual(String(password), user.password)) {
        res.status(401).json({ error: 'Invalid ID or password' });
        return;
      }

      setSessionCookie(res, user.securityContext);
      res.json({ ok: true, redirect: '/' });
    }));

    app.get('/logout', catchErrors((req: Request, res: Response) => {
      void req;
      clearSessionCookie(res);
      res.redirect('/login');
    }));

    app.post('/logout', catchErrors((req: Request, res: Response) => {
      void req;
      clearSessionCookie(res);
      res.json({ ok: true });
    }));

    app.get(['/', '/index.html'], (req: Request, res: Response, next: NextFunction) => {
      if (!webLoginEnabled || getWebSession(req)) {
        next();
        return;
      }
      res.redirect('/login');
    });

    app.use('/playground', (req: Request, res: Response, next: NextFunction) => {
      if (!webLoginEnabled || getWebSession(req)) {
        next();
        return;
      }
      res.status(401).json({ error: 'Login required' });
    });

    app.get('/playground/context', catchErrors((req, res) => {
      this.cubejsServer.event('Dev Server Env Open');
      const session = requireWebSession(req, res);
      if (!session) {
        return;
      }

      res.json({
        cubejsToken: createCubejsToken(session.securityContext),
        securityContext: {
          sub: session.securityContext.sub,
          groups: session.securityContext.groups,
        },
        basePath: options.basePath,
        anonymousId: getAnonymousId(),
        coreServerVersion: this.cubejsServer.coreServerVersion,
        dockerVersion: this.options.dockerVersion || null,
        projectFingerprint: this.cubejsServer.projectFingerprint,
        dbType: options.dbType || null,
        shouldStartConnectionWizardFlow: !this.options.isReadyForQueryProcessing(),
        livePreview: options.livePreview,
        isDocker: isDocker(),
        telemetry: options.telemetry,
        identifier: this.getIdentifier(options.apiSecret),
        previewFeatures: getEnv('previewFeatures'),
      });
    }));

    app.get('/playground/db-schema', catchErrors(async (req, res) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      this.cubejsServer.event('Dev Server DB Schema Load');
      const driver = await this.cubejsServer.getDriver({
        dataSource: req.body.dataSource || 'default',
        authInfo: null,
        securityContext: null,
        requestId: getRequestIdFromRequest(req),
      });

      const tablesSchema = await driver.tablesSchema();

      this.cubejsServer.event('Dev Server DB Schema Load Success');
      if (Object.keys(tablesSchema || {}).length === 0) {
        this.cubejsServer.event('Dev Server DB Schema Load Empty');
      }
      res.json({ tablesSchema });
    }));

    app.get('/playground/files', catchErrors(async (req, res) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      this.cubejsServer.event('Dev Server Files Load');
      const files = await this.cubejsServer.repository.dataSchemaFiles();
      res.json({
        files: files.map(f => ({
          ...f,
          absPath: path.resolve(path.join(this.cubejsServer.repository.localPath(), f.fileName))
        }))
      });
    }));

    app.post('/playground/generate-schema', catchErrors(async (req, res) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      this.cubejsServer.event('Dev Server Generate Schema');
      if (!req.body) {
        throw new Error('Your express app config is missing body-parser middleware. Typical config can look like: `app.use(bodyParser.json({ limit: \'50mb\' }));`');
      }

      if (!req.body.tables) {
        throw new Error('You have to select at least one table');
      }

      const dataSource = req.body.dataSource || 'default';

      const driver = await this.cubejsServer.getDriver({
        dataSource,
        authInfo: null,
        securityContext: null,
        requestId: getRequestIdFromRequest(req),
      });
      const tablesSchema = req.body.tablesSchema || (await driver.tablesSchema());

      if (!Object.values(SchemaFormat).includes(req.body.format)) {
        throw new Error(`Unknown schema format. Must be one of ${Object.values(SchemaFormat)}`);
      }

      const scaffoldingTemplate = new ScaffoldingTemplate(tablesSchema, driver, {
        format: req.body.format,
        snakeCase: true
      });
      const files = scaffoldingTemplate.generateFilesByTableNames(req.body.tables, { dataSource });

      await fs.emptyDir(path.join(options.schemaPath, 'cubes'));
      await fs.emptyDir(path.join(options.schemaPath, 'views'));

      await fs.writeFile(path.join(options.schemaPath, 'views', 'example_view.yml'), `# In Cube, views are used to expose slices of your data graph and act as data marts.
# You can control which measures and dimensions are exposed to BIs or data apps,
# as well as the direction of joins between the exposed cubes.
# You can learn more about views in documentation here - https://cube.dev/docs/schema/reference/view


# The following example shows a view defined on top of orders and customers cubes.
# Both orders and customers cubes are exposed using the "includes" parameter to
# control which measures and dimensions are exposed.
# Prefixes can also be applied when exposing measures or dimensions.
# In this case, the customers' city dimension is prefixed with the cube name,
# resulting in "customers_city" when querying the view.

# views:
#   - name: example_view
#
#     cubes:
#       - join_path: orders
#         includes:
#           - status
#           - created_date
#
#           - total_amount
#           - count
#
#       - join_path: orders.customers
#         prefix: true
#         includes:
#           - city`);
      await Promise.all(files.map(file => fs.writeFile(path.join(options.schemaPath, 'cubes', file.fileName), file.content)));

      res.json({ files });
    }));

    let lastApplyTemplatePackagesError = null;

    app.get('/playground/dashboard-app-create-status', catchErrors(async (req, res) => {
      const sourcePath = path.join(options.dashboardAppPath, 'src');

      if (lastApplyTemplatePackagesError) {
        const toThrow = lastApplyTemplatePackagesError;
        lastApplyTemplatePackagesError = null;
        throw toThrow;
      }

      if (this.applyTemplatePackagesPromise) {
        if (req.query.instant) {
          res.status(404).json({ error: 'Dashboard app creating' });
          return;
        }

        await this.applyTemplatePackagesPromise;
      }

      // docker-compose share a volume for /dashboard-app and directory will be empty
      if (!fs.pathExistsSync(options.dashboardAppPath) || fs.readdirSync(options.dashboardAppPath).length === 0) {
        res.status(404).json({
          error: `Dashboard app not found in '${path.resolve(options.dashboardAppPath)}' directory`
        });

        return;
      }

      if (!fs.pathExistsSync(sourcePath)) {
        res.status(404).json({
          error: `Dashboard app corrupted. Please remove '${path.resolve(options.dashboardAppPath)}' directory and recreate it`
        });

        return;
      }

      res.json({
        status: 'created',
        installedTemplates: AppContainer.getPackageVersions(options.dashboardAppPath)
      });
    }));

    app.get('/playground/start-dashboard-app', catchErrors(async (req, res) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      this.cubejsServer.event('Dev Server Start Dashboard App');

      if (!this.dashboardAppProcess) {
        const { dashboardAppPort = 3000 } = options;
        this.dashboardAppProcess = spawn('npm', [
          'run',
          'start',
          '--',
          '--port',
          dashboardAppPort.toString(),
          ...(isDocker() ? ['--host', '0.0.0.0'] : [])
        ], {
          cwd: options.dashboardAppPath,
          env: <any>{
            ...process.env,
            PORT: dashboardAppPort
          }
        });

        this.dashboardAppProcess.dashboardUrlPromise = new Promise((resolve) => {
          this.dashboardAppProcess.stdout.on('data', (data) => {
            console.log(data.toString());
            if (data.toString().match(/Compiled/)) {
              resolve(options.dashboardAppPort);
            }
          });
        });

        this.dashboardAppProcess.on('close', exitCode => {
          if (exitCode !== 0) {
            console.log(`Dashboard react-app failed with exit code ${exitCode}`);
            this.cubejsServer.event('Dev Server Dashboard App Failed', { exitCode });
          }
          this.dashboardAppProcess = null;
        });
      }

      await this.dashboardAppProcess.dashboardUrlPromise;
      res.json({ dashboardPort: options.dashboardAppPort });
    }));

    app.get('/playground/dashboard-app-status', catchErrors(async (req, res) => {
      this.cubejsServer.event('Dev Server Dashboard App Status');
      const dashboardPort = this.dashboardAppProcess && await this.dashboardAppProcess.dashboardUrlPromise;
      res.json({
        running: !!dashboardPort,
        dashboardPort,
        dashboardAppPath: path.resolve(options.dashboardAppPath)
      });
    }));

    let driverPromise: Promise<void> | null = null;
    let driverError: Error | null = null;

    app.get('/playground/driver', catchErrors(async (req: Request, res: Response) => {
      const { driver } = req.query;

      if (!driver || typeof driver !== 'string' || !DriverDependencies[driver as keyof typeof DriverDependencies]) {
        return res.status(400).json('Wrong driver');
      }

      if (packageExists(DriverDependencies[driver as keyof typeof DriverDependencies])) {
        return res.json({ status: 'installed' });
      } else if (driverPromise) {
        return res.json({ status: 'installing' });
      } else if (driverError) {
        return res.status(500).json({
          status: 'error',
          error: driverError.toString()
        });
      }

      return res.json({ status: null });
    }));

    app.post('/playground/driver', catchErrors((req, res) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      const { driver } = req.body;

      if (!driver || typeof driver !== 'string' || !DriverDependencies[driver as keyof typeof DriverDependencies]) {
        return res.status(400).json(`'${driver}' driver dependency not found`);
      }

      const driverKey = driver as keyof typeof DriverDependencies;

      async function installDriver() {
        driverError = null;

        try {
          await executeCommand(
            'npm',
            ['install', DriverDependencies[driverKey], '--save-dev'],
            { cwd: path.resolve('.') }
          );
        } catch (error) {
          driverError = error as Error;
        } finally {
          driverPromise = null;
        }
      }

      if (!driverPromise) {
        driverPromise = installDriver();
      }

      return res.json({
        dependency: DriverDependencies[driverKey]
      });
    }));

    app.post('/playground/apply-template-packages', catchErrors(async (req, res) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      this.cubejsServer.event('Dev Server Download Template Packages');

      const fetcher = process.env.TEST_TEMPLATES ? new DevPackageFetcher(repo) : new PackageFetcher(repo);

      this.cubejsServer.event('Dev Server App File Write');
      const { toApply, templateConfig } = req.body;

      const applyTemplates = async () => {
        const manifestJson = await fetcher.manifestJSON();
        const response = await fetcher.downloadPackages();

        let templatePackages: string[];
        if (typeof toApply === 'string') {
          const template = manifestJson.templates.find(({ name }) => name === toApply);
          templatePackages = template.templatePackages;
        } else {
          templatePackages = toApply;
        }

        const dt = new DependencyTree(manifestJson, templatePackages);

        const appContainer = new AppContainer(
          dt.getRootNode(),
          {
            appPath: options.dashboardAppPath,
            packagesPath: response.packagesPath
          },
          templateConfig
        );

        this.cubejsServer.event('Dev Server Create Dashboard App');
        await appContainer.applyTemplates();
        this.cubejsServer.event('Dev Server Create Dashboard App Success');

        this.cubejsServer.event('Dev Server Dashboard Npm Install');

        await appContainer.ensureDependencies();
        this.cubejsServer.event('Dev Server Dashboard Npm Install Success');

        fetcher.cleanup();
      };

      if (this.applyTemplatePackagesPromise) {
        this.applyTemplatePackagesPromise = this.applyTemplatePackagesPromise.then(applyTemplates);
      } else {
        this.applyTemplatePackagesPromise = applyTemplates();
      }
      const promise = this.applyTemplatePackagesPromise;

      promise.then(() => {
        if (promise === this.applyTemplatePackagesPromise) {
          this.applyTemplatePackagesPromise = null;
        }
      }, (err) => {
        lastApplyTemplatePackagesError = err;
        if (promise === this.applyTemplatePackagesPromise) {
          this.applyTemplatePackagesPromise = null;
        }
      });
      res.json(true); // TODO
    }));

    app.get('/playground/manifest', catchErrors(async (_, res) => {
      const fetcher = process.env.TEST_TEMPLATES ? new DevPackageFetcher(repo) : new PackageFetcher(repo);
      res.json(await fetcher.manifestJSON());
    }));

    app.get('/playground/live-preview/start/:token', catchErrors(async (req: Request, res: Response) => {
      this.livePreviewWatcher.setAuth(req.params.token);
      this.livePreviewWatcher.startWatch();

      res.setHeader('Content-Type', 'text/html');
      res.write('<html><body><script>window.close();</script></body></html>');
      res.end();
    }));

    app.get('/playground/live-preview/stop', catchErrors(async (req, res) => {
      this.livePreviewWatcher.stopWatch();
      res.json({ active: false });
    }));

    app.get('/playground/live-preview/status', catchErrors(async (req, res) => {
      const statusObj = await this.livePreviewWatcher.getStatus();
      res.json(statusObj);
    }));

    app.post('/playground/live-preview/token', catchErrors(async (req, res) => {
      const token = await this.livePreviewWatcher.createTokenWithPayload(req.body);
      res.json({ token });
    }));

    app.use(serveStatic(path.join(__dirname, '../../../playground'), {
      lastModified: false,
      etag: false,
      setHeaders: (res, url) => {
        if (url.indexOf('/index.html') !== -1) {
          res.setHeader('Cache-Control', 'no-cache');
        }
      }
    }));

    /**
     * The `/playground/test-connection` endpoint request.
     */
    type TestConnectionRequest = {
      body: {
        dataSource?: string,
        variables: {
          [env: string]: string,
        },
      },
    };

    app.post('/playground/test-connection', catchErrors(
      async (req: TestConnectionRequest, res) => {
        if (!requireWebAdmin(req as unknown as Request, res)) {
          return;
        }
        const { dataSource, variables } = req.body || {};

        // With multiple data sources enabled, we need to use
        // CUBEJS_DS_<dataSource>_DB_TYPE environment variable
        // instead of CUBEJS_DB_TYPE.
        const type = keyByDataSource('CUBEJS_DB_TYPE', dataSource);

        let driver: BaseDriver | null = null;

        try {
          if (!variables || !variables[type]) {
            throw new Error(`${type} is required`);
          }

          // Backup env variables for restoring
          const originalProcessEnv = process.env;
          process.env = {
            ...process.env,
          };

          // We suppose that variables names passed to the endpoint have their
          // final form depending on whether multiple data sources are enabled
          // or not. So, we don't need to convert anything here.
          for (const [envName, value] of Object.entries(variables)) {
            process.env[envName] = <string>value;
          }

          // With multiple data sources enabled, we need to put the dataSource
          // parameter to the driver instance to read an appropriate set of
          // driver configuration parameters. It can be undefined if multiple
          // data source is disabled.
          driver = CubejsServerCore.createDriver(
            <DatabaseType>variables[type],
            { dataSource },
          );

          // Restore original process.env
          process.env = originalProcessEnv;

          await driver.testConnection();

          this.cubejsServer.event('test_database_connection_success');

          return res.json('ok');
        } catch (error) {
          this.cubejsServer.event('test_database_connection_error');

          return res.status(400).json({
            error: error.toString()
          });
        } finally {
          if (driver && (<any>driver).release) {
            await (<any>driver).release();
          }
        }
      }
    ));

    app.post('/playground/env', catchErrors(async (req, res) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      let { variables = {} } = req.body || {};

      if (!variables.CUBEJS_API_SECRET) {
        variables.CUBEJS_API_SECRET = options.apiSecret;
      }

      let envs: Record<string, string> = {};
      const envPath = path.join(process.cwd(), '.env');
      if (fs.existsSync(envPath)) {
        envs = dotenv.parse(fs.readFileSync(envPath));
      }

      const schemaPath = envs.CUBEJS_SCHEMA_PATH || process.env.CUBEJS_SCHEMA_PATH || 'model';

      variables.CUBEJS_EXTERNAL_DEFAULT = 'true';
      variables.CUBEJS_SCHEDULED_REFRESH_DEFAULT = 'true';
      variables.CUBEJS_DEV_MODE = 'true';
      variables.CUBEJS_SCHEMA_PATH = schemaPath;
      variables = Object.entries(variables).map(([key, value]) => ([key, value].join('=')));

      const repositoryPath = path.join(process.cwd(), schemaPath);

      if (!fs.existsSync(repositoryPath)) {
        fs.mkdirSync(repositoryPath);
      }

      fs.writeFileSync(path.join(process.cwd(), '.env'), variables.join('\n'));

      if (!fs.existsSync(path.join(process.cwd(), 'package.json'))) {
        fs.writeFileSync(
          path.join(process.cwd(), 'package.json'),
          JSON.stringify({
            name: 'cube-docker',
            version: '0.0.1',
            private: true,
            createdAt: new Date().toJSON(),
            dependencies: {}
          }, null, 2)
        );
      }

      dotenv.config({ override: true });

      await this.cubejsServer.resetInstanceState();

      res.status(200).json(req.body.variables || {});
    }));

    app.post('/playground/token', catchErrors(async (req, res) => {
      const session = requireWebSession(req, res);
      if (!session) {
        return;
      }
      const token = createCubejsToken(session.securityContext);

      res.json({ token });
    }));

    // Data Model IDE endpoints
    app.post('/playground/model/save', catchErrors(async (req: Request, res: Response) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      const { fileName, content } = req.body;
      if (!fileName || content === undefined) {
        return res.status(400).json({ error: 'fileName and content are required' });
      }

      const repoPath = this.cubejsServer.repository.localPath();
      const absPath = path.resolve(repoPath, fileName);
      if (!absPath.startsWith(repoPath)) {
        return res.status(400).json({ error: 'Invalid file path' });
      }

      this.cubejsServer.repository.writeDataSchemaFile(fileName, content);
      this.cubejsServer.event('Dev Server Model File Save');
      return res.json({ fileName });
    }));

    app.post('/playground/model/create', catchErrors(async (req: Request, res: Response) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      const { fileName, content = '' } = req.body;
      if (!fileName) {
        return res.status(400).json({ error: 'fileName is required' });
      }

      const repoPath = this.cubejsServer.repository.localPath();
      const absPath = path.resolve(repoPath, fileName);
      if (!absPath.startsWith(repoPath)) {
        return res.status(400).json({ error: 'Invalid file path' });
      }
      if (fs.existsSync(absPath)) {
        return res.status(400).json({ error: `File "${fileName}" already exists` });
      }

      fs.ensureDirSync(path.dirname(absPath));
      this.cubejsServer.repository.writeDataSchemaFile(fileName, content);
      this.cubejsServer.event('Dev Server Model File Create');
      return res.json({ fileName });
    }));

    app.delete('/playground/model', catchErrors(async (req: Request, res: Response) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      const { fileName } = req.body;
      if (!fileName) {
        return res.status(400).json({ error: 'fileName is required' });
      }

      this.cubejsServer.repository.deleteDataSchemaFile(fileName);
      this.cubejsServer.event('Dev Server Model File Delete');
      return res.json({ fileName });
    }));

    app.post('/playground/model/rename', catchErrors(async (req: Request, res: Response) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      const { oldFileName, newFileName } = req.body;
      if (!oldFileName || !newFileName) {
        return res.status(400).json({ error: 'oldFileName and newFileName are required' });
      }

      this.cubejsServer.repository.renameDataSchemaFile(oldFileName, newFileName);
      this.cubejsServer.event('Dev Server Model File Rename');
      return res.json({ oldFileName, newFileName });
    }));

    app.post('/playground/schema/pre-aggregation', catchErrors(async (req: Request, res: Response) => {
      if (!requireWebAdmin(req, res)) {
        return;
      }
      const { cubeName, preAggregationName, code } = req.body;

      /**
       * Important note:
       * JS code for pre-agg includes the content of the pre-aggregation object
       * without name, which is passed as preAggregationName.
       * While yaml code for pre-agg includes whole yaml object including name.
       */
      const schemaConverter = new CubeSchemaConverter(this.cubejsServer.repository, [
        new CubePreAggregationConverter({
          cubeName,
          preAggregationName,
          code
        })
      ]);

      try {
        await schemaConverter.generate(cubeName);
      } catch (error) {
        return res.status(400).json({ error: (error as Error).message || error });
      }

      const file = schemaConverter.getSourceFiles().find(
        ({ cubeName: currentCubeName }) => currentCubeName === cubeName
      );

      if (!file) {
        return res.status(400).json({ error: `The schema file for "${cubeName}" cube was not found or could not be updated. Only JS and non-templated YAML files are supported.` });
      }

      this.cubejsServer.repository.writeDataSchemaFile(file.fileName, file.source);
      return res.json('ok');
    }));
  }

  protected getIdentifier(apiSecret: string): string {
    return crypto.createHash('md5')
      .update(apiSecret)
      .digest('hex')
      .replace(/[^\d]/g, '')
      .slice(0, 10);
  }
}
