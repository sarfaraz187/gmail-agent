# Gmail Auth Recovery Runbook

## Purpose

Use this runbook when the deployed email agent is healthy on Cloud Run but Gmail integration is failing.

## Typical Symptoms

### Cloud Run is healthy

These endpoints return successfully:

- `/health` returns `200`
- `/watch-status` returns `200`

But `/watch-status` may report:

```json
{"active": false, "expiration": null}
```

### Gmail auth errors in logs

Common log signatures:

- `invalid_grant`
- `invalid_client`
- `redirect_uri_mismatch`

Examples:

- `google.auth.exceptions.RefreshError: ('invalid_grant: Bad Request', ...)`
- `google.auth.exceptions.RefreshError: ('invalid_client: The provided client secret is invalid.', ...)`
- Browser sign-in error `Error 400: redirect_uri_mismatch`

## What Usually Broke

The app uses two different OAuth artifacts that are easy to confuse:

### 1. OAuth client credentials

File: `scripts/credentials.json`

Purpose:

- Identifies the app to Google
- Contains the OAuth client ID and client secret
- Is required to start the local browser login flow

This file must be for a **Desktop app** OAuth client.

### 2. User OAuth token

Local file: `scripts/token.json`

Cloud secret: `gmail-refresh-token`

Purpose:

- Represents the Gmail user's granted access
- Contains the refresh token and access token
- Is what Cloud Run uses to access Gmail

If this token is revoked, expired, or otherwise invalid, Cloud Run logs `invalid_grant`.

## Failure Mapping

### `invalid_grant`

Meaning:

- The stored user token is no longer accepted by Google

Usually fix by:

- deleting stale local `scripts/token.json`
- generating a new token
- uploading it to Secret Manager

### `invalid_client`

Meaning:

- `scripts/credentials.json` has the wrong client secret, wrong JSON shape, or mismatched client ID and client secret

Usually fix by:

- creating a brand new Desktop app OAuth client
- downloading the JSON directly from Google
- replacing `scripts/credentials.json` exactly as downloaded

### `redirect_uri_mismatch`

Meaning:

- `scripts/credentials.json` is for a Web application client instead of a Desktop app client

Usually fix by:

- creating a **Desktop app** OAuth client
- not adding redirect URIs manually

## Recovery Steps

### 1. Prepare a valid Desktop app OAuth client

In Google Cloud Console:

1. Go to `APIs & Services` -> `Credentials`
2. Create a new OAuth client ID if needed
3. Set `Application type` to `Desktop app`
4. Download the generated JSON immediately

Save it as:

- `scripts/credentials.json`

Do not manually assemble this file.

Expected top-level JSON key:

- `installed`

Not:

- `web`

### 2. Remove the stale local token

```bash
rm -f scripts/token.json
```

### 3. Generate a fresh Gmail user token

Use the project environment, not system Python:

```bash
uv sync
uv run python scripts/gmail_auth.py
```

Expected result:

- browser login opens
- user signs into the Gmail account the agent should control
- `scripts/token.json` is created

### 4. Upload the new token to Secret Manager

```bash
gcloud secrets versions add gmail-refresh-token --data-file=scripts/token.json
```

### 5. Renew the deployed Gmail watch

```bash
curl -X POST https://email-agent-ezgzw36a7a-ew.a.run.app/renew-watch
```

### 6. Verify watch status

```bash
curl https://email-agent-ezgzw36a7a-ew.a.run.app/watch-status
```

Expected result:

- `"active": true`
- non-null `"expiration"`

## Secondary Check: Pub/Sub Delivery

Even if Gmail auth is fixed, the pipeline still needs a Pub/Sub push subscription.

Check:

```bash
gcloud pubsub subscriptions list
```

If no subscription exists, Gmail watch renewal alone is not enough. Pub/Sub must push to:

- `https://email-agent-ezgzw36a7a-ew.a.run.app/webhook/gmail`

## Notes From June 3, 2026 Investigation

- Cloud Run service `email-agent` was healthy
- `/health` returned `200`
- `/watch-status` returned inactive watch state
- Cloud logs showed `invalid_grant` during Gmail credential refresh
- Secret `gmail-refresh-token` existed and had valid JSON structure
- Root cause was not Cloud Run deployment
- Root cause was Gmail OAuth credential failure
- Project also had no Pub/Sub subscriptions configured
