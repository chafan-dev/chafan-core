/**
 * Cloudflare Worker: the public read path for image uploads.
 *
 * The bucket is private. Garage serves no anonymous request at all, and Storm's
 * Static Hosting alternative is per-bucket and leaves a `stormsites.ca` URL
 * permanently reachable, which would let a scraper bypass Cloudflare entirely
 * and bill the egress to us. So instead: nothing is public, this Worker holds a
 * Read Only per-bucket key, signs each GET with SigV4, and streams the object
 * back.
 *
 * What that buys, in the order it matters:
 *
 *   1. Repeat traffic never reaches Storm. `caches.default` answers at the edge,
 *      so Storm egress is roughly one fetch per object per PoP rather than one
 *      per view. NB: the Cache API is a silent no-op on `*.workers.dev`, so this
 *      only holds when the Worker is bound to a real hostname -- see the routes
 *      in `wrangler.toml`.
 *   2. Rate limiting, hotlink rules and bot rules apply, because the hostname is
 *      an ordinary Cloudflare zone entry. They live in the dashboard, not here.
 *   3. No bytes cross the chafan server or its tunnel.
 *
 * KEY_PATTERN is the security boundary, not a nicety: without it this Worker is
 * a signing oracle for the whole bucket, including list operations. It must stay
 * in sync with `_key()` and `_CONTENT_TYPE_EXTENSIONS` in
 * `chafan_core/app/object_storage.py`, which produce `<sha256>.<ext>`.
 */

export interface Env {
  UPLOADS_S3_ENDPOINT_URL: string;
  UPLOADS_S3_BUCKET: string;
  UPLOADS_S3_REGION: string;
  UPLOADS_S3_ACCESS_KEY_ID: string;
  UPLOADS_S3_SECRET_ACCESS_KEY: string;
}

const KEY_PATTERN = /^[0-9a-f]{64}\.(jpg|png|gif|webp)$/;

// SHA-256 of the empty string: every request here is a bodiless GET/HEAD.
const EMPTY_PAYLOAD_SHA256 =
  'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

// Content is addressed by hash, so a cached copy can never go stale.
const CACHE_CONTROL = 'public, max-age=31536000, immutable';

function hex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function sha256Hex(text: string): Promise<string> {
  return hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
}

async function hmac(key: BufferSource, message: string): Promise<ArrayBuffer> {
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    key,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  return crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(message));
}

/**
 * Build the SigV4 `Authorization` header for a bodiless request to the bucket.
 *
 * Exported so `scripts/sign_check.ts` can sign a real request against Storm
 * without a Workers runtime -- the signature is the one part of this Worker
 * that fails invisibly (any mistake reads as a 403 from Garage, the same way an
 * unsigned request does).
 */
export async function signedHeaders(
  method: 'GET' | 'HEAD',
  endpoint: string,
  bucket: string,
  key: string,
  region: string,
  accessKeyId: string,
  secretAccessKey: string,
  now: Date = new Date(),
): Promise<Record<string, string>> {
  const host = new URL(endpoint).host;
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, '');
  const dateStamp = amzDate.slice(0, 8);
  const scope = `${dateStamp}/${region}/s3/aws4_request`;

  // Path-style addressing: Storm provides no wildcard DNS for virtual-hosted
  // style. The key is constrained to hex + a known extension by KEY_PATTERN, so
  // there is nothing here that needs percent-encoding.
  const canonicalUri = `/${bucket}/${key}`;
  const canonicalHeaders =
    `host:${host}\n` +
    `x-amz-content-sha256:${EMPTY_PAYLOAD_SHA256}\n` +
    `x-amz-date:${amzDate}\n`;
  const signedHeaderList = 'host;x-amz-content-sha256;x-amz-date';

  const canonicalRequest = [
    method,
    canonicalUri,
    '',
    canonicalHeaders,
    signedHeaderList,
    EMPTY_PAYLOAD_SHA256,
  ].join('\n');

  const stringToSign = [
    'AWS4-HMAC-SHA256',
    amzDate,
    scope,
    await sha256Hex(canonicalRequest),
  ].join('\n');

  let signingKey: BufferSource = new TextEncoder().encode(`AWS4${secretAccessKey}`);
  for (const part of [dateStamp, region, 's3', 'aws4_request']) {
    signingKey = new Uint8Array(await hmac(signingKey, part));
  }
  const signature = hex(await hmac(signingKey, stringToSign));

  return {
    host,
    'x-amz-content-sha256': EMPTY_PAYLOAD_SHA256,
    'x-amz-date': amzDate,
    authorization:
      `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${scope}, ` +
      `SignedHeaders=${signedHeaderList}, Signature=${signature}`,
  };
}

function plain(status: number, body: string): Response {
  return new Response(body, {
    status,
    headers: { 'content-type': 'text/plain; charset=utf-8' },
  });
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return plain(405, 'Method not allowed');
    }

    const url = new URL(request.url);
    const key = url.pathname.slice(1);
    if (!KEY_PATTERN.test(key)) {
      return plain(404, 'Not found');
    }

    // Normalize the cache key: query strings are ignored (nothing here varies by
    // them) and HEAD shares GET's entry, since the Cache API only stores GETs.
    const cacheKey = new Request(`${url.origin}/${key}`, { method: 'GET' });
    const cache = caches.default;
    const cached = await cache.match(cacheKey);
    if (cached) {
      return cached;
    }

    const headers = await signedHeaders(
      'GET',
      env.UPLOADS_S3_ENDPOINT_URL,
      env.UPLOADS_S3_BUCKET,
      key,
      env.UPLOADS_S3_REGION,
      env.UPLOADS_S3_ACCESS_KEY_ID,
      env.UPLOADS_S3_SECRET_ACCESS_KEY,
    );
    const upstream = await fetch(
      `${env.UPLOADS_S3_ENDPOINT_URL.replace(/\/$/, '')}/${env.UPLOADS_S3_BUCKET}/${key}`,
      { method: 'GET', headers },
    );

    if (!upstream.ok) {
      // Never pass Garage's XML through: a 403 caused by a rotated key would
      // otherwise reach readers as a confusing "AccessDenied" page. 404 is the
      // honest answer to "is there an image here", whatever went wrong upstream.
      return plain(upstream.status === 404 ? 404 : 502, 'Not found');
    }

    // Rebuild the response from a known header set rather than forwarding
    // upstream's, which carries x-amz-* and Garage's own cache directives.
    const out = new Response(upstream.body, {
      status: 200,
      headers: {
        'content-type': upstream.headers.get('content-type') ?? 'application/octet-stream',
        'cache-control': CACHE_CONTROL,
        'access-control-allow-origin': '*',
        'x-content-type-options': 'nosniff',
        ...(upstream.headers.get('etag') ? { etag: upstream.headers.get('etag')! } : {}),
        ...(upstream.headers.get('content-length')
          ? { 'content-length': upstream.headers.get('content-length')! }
          : {}),
      },
    });

    ctx.waitUntil(cache.put(cacheKey, out.clone()));
    return request.method === 'HEAD' ? new Response(null, out) : out;
  },
};
