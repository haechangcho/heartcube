#!/usr/bin/env node

const jwt = require('jsonwebtoken');

function readArg(name, fallback = undefined) {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) {
    return fallback;
  }

  return process.argv[index + 1];
}

function readListArg(name, fallback = []) {
  const value = readArg(name);
  if (!value) {
    return fallback;
  }

  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

const secret = process.env.CUBEJS_API_SECRET;
if (!secret) {
  console.error('CUBEJS_API_SECRET is required');
  process.exit(1);
}

const sub = readArg('--sub', 'analyst_01');
const groups = readListArg('--groups', ['analyst']);
const claimCenter = readArg('--claim-center');
const tenantId = readArg('--tenant-id');
const issuer = readArg('--issuer');
const audience = readArg('--audience');
const expiresIn = readArg('--expires-in', '1h');

const payload = {
  sub,
  groups,
};

if (claimCenter) {
  payload.claim_center = claimCenter;
}

if (tenantId) {
  payload.tenant_id = tenantId;
}

const signOptions = {
  algorithm: 'HS256',
  expiresIn,
};

if (issuer) {
  signOptions.issuer = issuer;
}

if (audience) {
  signOptions.audience = audience;
}

const token = jwt.sign(payload, secret, signOptions);
process.stdout.write(`${token}\n`);
