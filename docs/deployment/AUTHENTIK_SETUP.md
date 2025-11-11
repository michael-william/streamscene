# Authentik OAuth2 Setup Guide for StreamScene

**Purpose:** Configure Authentik to provide OAuth2/OIDC authentication for StreamScene web application.

**Authentik URL:** http://192.168.1.108:9000

---

## 📋 Prerequisites

- [ ] Authentik is running and accessible at http://192.168.1.108:9000
- [ ] You have admin credentials for Authentik
- [ ] StreamScene app is installed at `/root/streamscene`
- [ ] `.env` file exists and is ready to be updated

---

## 🔐 Step 1: Login to Authentik

1. Open browser and navigate to: **http://192.168.1.108:9000**
2. Login with your Authentik admin credentials
3. You should see the Authentik admin dashboard

---

## 🔧 Step 2: Create OAuth2/OIDC Provider

### 2.1 Navigate to Providers
1. In the left sidebar, click **Applications**
2. Click on the **Providers** tab at the top
3. Click the **Create** button (top right)

### 2.2 Select Provider Type
1. Choose **OAuth2/OpenID Provider**
2. Click **Next**

### 2.3 Configure Provider Settings

Fill in the following fields:

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | `StreamScene OAuth Provider` | Descriptive name |
| **Authorization flow** | `default-provider-authorization-implicit-consent` | Select from dropdown |
| **Client type** | `Confidential` | For server-side apps |
| **Client ID** | `streamscene` | Simple identifier (auto-generated if left empty) |
| **Client Secret** | *auto-generated* | **COPY THIS** - you'll need it for .env |
| **Redirect URIs/Origins (RegEx)** | See below ⬇️ | Critical for OAuth flow |

**Redirect URIs (one per line):**
```
http://localhost:3000/.*
http://localhost:8000/.*
https://streamscene.dataandstories.com/.*
http://streamscene.dataandstories.com/.*
```

**Additional Settings:**
- **Scopes:** Leave default (`openid`, `email`, `profile`)
- **Subject mode:** `Based on the User's UUID` (recommended)
- **Token validity:**
  - Access Token: `minutes=10` (default)
  - Refresh Token: `days=30` (default)

### 2.4 Save Provider
1. Click **Finish** at the bottom
2. **IMPORTANT:** Copy the **Client ID** and **Client Secret**
3. Store them temporarily in a text file - you'll add them to `.env` shortly

---

## 📱 Step 3: Create Application

### 3.1 Navigate to Applications
1. In the left sidebar, click **Applications**
2. You should see the **Applications** tab (not Providers)
3. Click the **Create** button

### 3.2 Configure Application

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | `StreamScene` | User-facing name |
| **Slug** | `streamscene` | URL-safe identifier |
| **Provider** | `StreamScene OAuth Provider` | Select the provider you just created |
| **Launch URL** | `https://streamscene.dataandstories.com` | Main app URL |
| **UI Settings** | Optional | Can add logo, description, etc. |

### 3.3 Save Application
1. Click **Create**
2. You should see the new StreamScene application in the list

---

## 🎨 Step 4: (Optional) Customize Application Appearance

### 4.1 Add Logo
1. Click on the **StreamScene** application
2. Click **Edit** (top right)
3. Under **UI Settings**:
   - **Icon:** Upload a logo image (optional)
   - **Description:** "Family E Ink Message Board"
   - **Publisher:** Your name/organization

### 4.2 Save Changes
1. Click **Update**

---

## 🔑 Step 5: Update StreamScene .env File

Now that you have the **Client ID** and **Client Secret** from Step 2.4:

1. Open the `.env` file:
   ```bash
   cd /root/streamscene
   nano .env
   ```

2. Find these lines:
   ```env
   AUTHENTIK_CLIENT_ID=streamscene
   AUTHENTIK_CLIENT_SECRET=CHANGE_ME_AFTER_AUTHENTIK_SETUP
   ```

3. Replace with your actual values:
   ```env
   AUTHENTIK_CLIENT_ID=streamscene
   AUTHENTIK_CLIENT_SECRET=<paste-the-secret-from-authentik>
   ```

4. Save the file (Ctrl+O, Enter, Ctrl+X in nano)

---

## 📝 Step 6: Document Credentials

Add the Authentik credentials to `CREDENTIALS.md`:

```bash
cd /root/streamscene
nano CREDENTIALS.md
```

Add this section:

```markdown
## Authentik OAuth Configuration

**Status:** ✅ Configured

- **Authentik URL:** http://192.168.1.108:9000
- **Application Name:** StreamScene
- **Provider Name:** StreamScene OAuth Provider
- **Client ID:** streamscene
- **Client Secret:** <paste-the-secret-here>
- **Scopes:** openid, email, profile
- **Redirect URIs:**
  - http://localhost:3000/.*
  - http://localhost:8000/.*
  - https://streamscene.dataandstories.com/.*

**Last Updated:** November 2, 2025
```

---

## ✅ Step 7: Verify Configuration

### 7.1 Check Provider Settings
1. In Authentik, go to **Applications → Providers**
2. Click on **StreamScene OAuth Provider**
3. Verify:
   - ✅ Client type is "Confidential"
   - ✅ Redirect URIs include all needed URLs
   - ✅ Scopes include openid, email, profile

### 7.2 Check Application Settings
1. In Authentik, go to **Applications**
2. Click on **StreamScene**
3. Verify:
   - ✅ Provider is linked correctly
   - ✅ Launch URL is set

### 7.3 Test OAuth Flow (Later)
This will be tested when we implement the Reflex authentication integration in Phase 1.

---

## 🔧 Step 8: (Optional) Create Test Users

If you want to create test users for development:

1. In Authentik sidebar, click **Directory → Users**
2. Click **Create**
3. Fill in:
   - **Username:** testuser1
   - **Email:** testuser1@example.com
   - **Name:** Test User One
   - **Password:** Set a test password
4. Click **Create**
5. Repeat for additional test users

---

## 🚨 Troubleshooting

### Common Issues

**Issue:** "Invalid redirect URI" error during OAuth flow
- **Solution:** Check that redirect URIs in Authentik match your app's callback URLs
- **Solution:** Make sure to use `.*` regex pattern, not exact URLs

**Issue:** "Invalid client" error
- **Solution:** Verify Client ID in `.env` matches the one in Authentik
- **Solution:** Check that Client Secret is copied correctly (no extra spaces)

**Issue:** Can't access Authentik at http://192.168.1.108:9000
- **Solution:** Check that Authentik container is running in Proxmox
- **Solution:** Verify network connectivity from this LXC to the Authentik LXC

**Issue:** Token expires too quickly
- **Solution:** Adjust token validity in Provider settings
- **Solution:** Access Token: increase to `minutes=60` for development

---

## 📊 Next Steps After Setup

Once Authentik OAuth is configured:

1. ✅ Update `.env` with Client ID and Secret (Step 5)
2. ✅ Document credentials in `CREDENTIALS.md` (Step 6)
3. 🔄 Implement Authentik integration in Reflex app (Phase 1)
4. 🔄 Create login/logout UI components
5. 🔄 Test OAuth flow end-to-end
6. 🔄 Configure user permissions and groups (as needed)

---

## 🔗 Useful Authentik Documentation

- **OAuth2 Provider Setup:** https://docs.goauthentik.io/docs/providers/oauth2
- **Applications:** https://docs.goauthentik.io/docs/applications
- **Flows:** https://docs.goauthentik.io/docs/flow
- **User Management:** https://docs.goauthentik.io/docs/users-sources

---

## 📋 Quick Reference

**After completing this guide, you should have:**
- [x] OAuth2 Provider created in Authentik
- [x] StreamScene Application created in Authentik
- [x] Client ID and Client Secret documented
- [x] `.env` file updated with credentials
- [x] `CREDENTIALS.md` updated with Authentik info
- [x] (Optional) Test users created

**Your Authentik Configuration:**
```
Provider Type: OAuth2/OIDC
Client ID: streamscene
Client Type: Confidential
Authorization Flow: default-provider-authorization-implicit-consent
Scopes: openid, email, profile
```

---

**Setup Complete!** ✅

Next: Implement OAuth integration in the Reflex application.
