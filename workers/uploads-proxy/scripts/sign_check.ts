/**
 * Verify the Worker's SigV4 against the real bucket, without a Workers runtime.
 *
 * The signature is the one part of this Worker that fails invisibly: Garage
 * answers a missigned request with exactly the 403 it gives an unsigned one, so
 * a signing bug and a configuration bug look identical from the browser. This
 * signs a real GET with the same function the Worker uses and reports what came
 * back.
 *
 * Usage (reads the same variable names as the Worker and the backend):
 *
 *   UPLOADS_S3_ENDPOINT_URL=... UPLOADS_S3_BUCKET=... UPLOADS_S3_REGION=... \
 *   UPLOADS_S3_ACCESS_KEY_ID=... UPLOADS_S3_SECRET_ACCESS_KEY=... \
 *   node --experimental-strip-types scripts/sign_check.ts <sha>.<ext>
 */

import { signedHeaders } from '../src/index.ts';

const key = process.argv[2];
if (!key) {
  console.error('usage: sign_check.ts <sha256>.<ext>');
  process.exit(2);
}

const env = (name: string): string => {
  const value = process.env[name];
  if (!value) {
    console.error(`${name} is unset`);
    process.exit(2);
  }
  return value;
};

const endpoint = env('UPLOADS_S3_ENDPOINT_URL').replace(/\/$/, '');
const bucket = env('UPLOADS_S3_BUCKET');
const region = env('UPLOADS_S3_REGION');

const headers = await signedHeaders(
  'GET',
  endpoint,
  bucket,
  key,
  region,
  env('UPLOADS_S3_ACCESS_KEY_ID'),
  env('UPLOADS_S3_SECRET_ACCESS_KEY'),
);

const response = await fetch(`${endpoint}/${bucket}/${key}`, { headers });
const body = await response.arrayBuffer();

console.log(`GET ${endpoint}/${bucket}/${key}`);
console.log(`  status:       ${response.status}`);
console.log(`  content-type: ${response.headers.get('content-type')}`);
console.log(`  bytes:        ${body.byteLength}`);
if (!response.ok) {
  console.log(`  body:         ${new TextDecoder().decode(body).slice(0, 400)}`);
  process.exit(1);
}
