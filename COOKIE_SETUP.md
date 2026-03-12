# Cookie Setup Guide

Clay's internal API authenticates via a session cookie from your browser. No tokens, no OAuth — just your existing browser session.

---

## Step 1 — Log in to Clay

Go to [app.clay.com](https://app.clay.com) and log in normally.

---

## Step 2 — Open DevTools

Press **F12** (Windows/Linux) or **Cmd + Option + I** (Mac) to open Chrome DevTools.

---

## Step 3 — Find the session cookie

**Option A — Application tab (easiest):**

1. Click the **Application** tab in DevTools
2. In the left sidebar, expand **Storage → Cookies**
3. Click **`https://clay.com`** (or **`https://app.clay.com`**)
4. In the cookie list, find the row named **`claysession`**
5. Copy the full value from the **Value** column

**Option B — Network tab (alternative):**

1. Click the **Network** tab in DevTools
2. Refresh the page or click anything in Clay
3. Click any request to `api.clay.com`
4. Go to the **Headers** tab → **Request Headers**
5. Find the `Cookie:` header
6. Copy the `claysession=...` portion (everything from `claysession=` to the next `;`)

---

## Step 4 — Create `clay-session.json`

In the same directory as `clay_client.py`, create a file called `clay-session.json`:

```json
{
  "claysession": "s%3Ayour-full-cookie-value-here..."
}
```

The value typically starts with `s%3A` (URL-encoded `s:`).

---

## How long does it last?

The session cookie expires after a few weeks. When requests start returning 401 errors, repeat Steps 2–4 to refresh it.

---

## Security note

`clay-session.json` is listed in `.gitignore`. **Never commit it to a repository.**
