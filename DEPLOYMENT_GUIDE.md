# 🚀 NavTatva Deployment Guide

This guide walks you through deploying NavTatva with:
- **Frontend** on Vercel (free tier)
- **Backend** on Render (free tier)

---

## 📋 Prerequisites

### What You Need to Provide:

1. **GitHub Account** (free)
2. **Vercel Account** (free - sign up at [vercel.com](https://vercel.com))
3. **Render Account** (free - sign up at [render.com](https://render.com))
4. **Git installed** on your computer
5. **GitHub Repository** (you'll create this)

### Optional (for enhanced features):
- **Hugging Face Token** (free - for model downloads from [huggingface.co](https://huggingface.co))
- **AISStream API Key** (free tier available at [aisstream.io](https://aisstream.io))

---

## 📂 Step 1: Prepare Your Repository

### 1.1 Initialize Git Repository (if not already done)

```bash
cd c:\Users\LENOVO\Downloads\SIH-Nav\NavTatva-3

# Initialize git
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit - NavTatva SIH project"
```

### 1.2 Create GitHub Repository

1. Go to [github.com](https://github.com)
2. Click **"New Repository"** (green button)
3. Name it: `navtatva-sih` (or your preferred name)
4. **Keep it PUBLIC** (required for free Vercel/Render)
5. **DO NOT** initialize with README (you already have one)
6. Click **"Create Repository"**

### 1.3 Push to GitHub

```bash
# Add your GitHub repository as remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/navtatva-sih.git

# Push your code
git branch -M main
git push -u origin main
```

**✅ Checkpoint:** Your code should now be visible on GitHub at `https://github.com/YOUR_USERNAME/navtatva-sih`

---

## 🔧 Step 2: Deploy Backend on Render

### 2.1 Create Render Account

1. Go to [render.com](https://render.com)
2. Click **"Get Started"**
3. Sign up with GitHub (easiest option)

### 2.2 Deploy Backend Service

1. Once logged in, click **"New +"** → **"Web Service"**

2. **Connect Your Repository:**
   - Click **"Connect GitHub"**
   - Authorize Render to access your GitHub
   - Select your `navtatva-sih` repository
   - Click **"Connect"**

3. **Configure Service:**
   ```
   Name: navtatva-backend
   Region: Choose closest to you (e.g., Oregon, Frankfurt, Singapore)
   Branch: main
   Root Directory: (leave blank)
   Runtime: Python 3
   Build Command: pip install -r requirements.txt && python scripts/bootstrap_demo.py --minimal
   Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. **Select Plan:**
   - Choose **"Free"** plan
   - Note: Free tier has limitations (spins down after 15 min of inactivity, 512 MB RAM)

5. **Environment Variables:**
   Click **"Advanced"** → **"Add Environment Variable"**
   
   Add these variables:
   ```
   TIDETRACE_OFFLINE = 1
   PYTHON_VERSION = 3.11.0
   ```
   
   **Optional variables** (add if needed):
   ```
   HF_TOKEN = your_huggingface_token_here
   AISSTREAM_API_KEY = your_aisstream_key_here
   ```

6. **Create Web Service:**
   - Click **"Create Web Service"**
   - Wait 5-10 minutes for deployment
   - You'll see build logs in real-time

### 2.3 Get Your Backend URL

Once deployed successfully:
- You'll see: **"Your service is live 🎉"**
- Copy your backend URL (looks like): `https://navtatva-backend-xxxx.onrender.com`
- Test it by visiting: `https://your-url.onrender.com/api/health`

**✅ Checkpoint:** You should see a JSON response with health status

---

## 🌐 Step 3: Deploy Frontend on Vercel

### 3.1 Update Frontend Configuration

Before deploying, update the backend URL in your code:

1. Open `app/static/index.html`
2. Find this line (around line 450):
   ```javascript
   : 'https://your-backend-url.onrender.com';
   ```
3. Replace `your-backend-url.onrender.com` with your actual Render URL
4. Save the file

```bash
# Commit the change
git add app/static/index.html
git commit -m "Update backend URL for production"
git push origin main
```

### 3.2 Create Vercel Account

1. Go to [vercel.com](https://vercel.com)
2. Click **"Sign Up"**
3. Choose **"Continue with GitHub"**
4. Authorize Vercel

### 3.3 Deploy Frontend

1. Once logged in, click **"Add New..."** → **"Project"**

2. **Import Git Repository:**
   - Find your `navtatva-sih` repository
   - Click **"Import"**

3. **Configure Project:**
   ```
   Framework Preset: Other
   Root Directory: ./
   Build Command: (leave empty - we're deploying static files)
   Output Directory: app/static
   Install Command: (leave empty)
   ```

4. **Environment Variables:**
   Click **"Environment Variables"** and add:
   ```
   Name: API_BASE_URL
   Value: https://your-backend-url.onrender.com
   ```
   (Replace with your actual Render URL)

5. **Deploy:**
   - Click **"Deploy"**
   - Wait 1-2 minutes for deployment
   - Vercel will show progress

### 3.4 Update vercel.json

After first deployment, update `vercel.json` with your actual backend URL:

1. Open `vercel.json` in your code
2. Replace this line:
   ```json
   "destination": "https://your-backend-url.onrender.com/api/:path*"
   ```
   With your actual URL:
   ```json
   "destination": "https://navtatva-backend-xxxx.onrender.com/api/:path*"
   ```

3. Commit and push:
   ```bash
   git add vercel.json
   git commit -m "Update API proxy URL"
   git push origin main
   ```

Vercel will automatically redeploy.

### 3.5 Get Your Frontend URL

- Vercel shows: **"Congratulations! 🎉"**
- Your frontend URL: `https://your-project-name.vercel.app`
- Click **"Visit"** to open your deployed app

**✅ Checkpoint:** You should see the NavTatva interface with the map and controls

---

## 🧪 Step 4: Test Your Deployment

### 4.1 Test Backend

Visit these URLs (replace with your backend URL):

1. **Health Check:**
   ```
   https://your-backend.onrender.com/api/health
   ```
   Should return JSON with `status: "ok"`

2. **API Docs:**
   ```
   https://your-backend.onrender.com/docs
   ```
   Should show interactive API documentation

### 4.2 Test Frontend

Visit your Vercel URL:
```
https://your-project.vercel.app
```

**Check:**
- ✅ Map loads correctly
- ✅ Scene selector works
- ✅ Can run analysis (may be slow on free tier)
- ✅ No CORS errors in browser console (F12)

### 4.3 Test Full Pipeline

1. Open your Vercel frontend
2. Click **"Change scene"**
3. Select a demo scene (or upload your own)
4. Click **"Run analysis"**
5. Wait for processing (can take 2-5 minutes on free tier)
6. Verify results appear

---

## ⚙️ Step 5: Configure Custom Domains (Optional)

### For Vercel (Frontend):

1. Go to your project in Vercel dashboard
2. Click **"Settings"** → **"Domains"**
3. Add your custom domain (e.g., `navtatva.yourdomain.com`)
4. Follow Vercel's DNS instructions
5. Update backend CORS to include your domain

### For Render (Backend):

1. Go to your service in Render dashboard
2. Click **"Settings"** → **"Custom Domain"**
3. Add your domain (e.g., `api.navtatva.yourdomain.com`)
4. Update DNS records as instructed
5. Update frontend to use new backend URL

---

## 🔧 Troubleshooting

### Problem: "Application Error" on Render

**Cause:** Build failed or dependencies missing

**Solution:**
1. Check Render logs (click on your service → "Logs")
2. Verify `requirements.txt` has all dependencies
3. Ensure Python version is 3.11+
4. Check if build command completed successfully

### Problem: CORS Error in Browser

**Cause:** Backend not allowing frontend domain

**Solution:**
1. Open `app/main.py`
2. Add your Vercel domain to `allow_origins`:
   ```python
   allow_origins=[
       "https://your-project.vercel.app",
       "https://*.vercel.app",
   ]
   ```
3. Commit and push changes

### Problem: Frontend Shows "Failed to Load Scenes"

**Cause:** Frontend can't reach backend

**Solution:**
1. Verify backend URL in `index.html` is correct
2. Check if backend is running (visit `/api/health`)
3. Check browser console (F12) for network errors
4. Ensure backend has public access (not behind firewall)

### Problem: Analysis Takes Forever

**Cause:** Free tier has limited resources

**Solution:**
1. This is expected on free tier
2. Consider upgrading to paid tier for better performance
3. Or run locally for faster processing
4. Reduce analysis parameters (shorter hindcast/forecast hours)

### Problem: "Service Unavailable" Intermittently

**Cause:** Render free tier spins down after 15 min inactivity

**Solution:**
1. First request will be slow (service waking up)
2. Subsequent requests will be fast
3. Consider using a ping service to keep it alive
4. Or upgrade to paid tier for always-on service

---

## 📊 Monitoring Your Deployment

### Render Dashboard:

- **Logs:** Real-time backend logs
- **Metrics:** CPU, memory usage
- **Events:** Deployment history
- **Settings:** Environment variables, scaling

### Vercel Dashboard:

- **Deployments:** All deployment history
- **Analytics:** Visitor statistics (paid feature)
- **Logs:** Function execution logs
- **Preview:** Test deployments before production

---

## 🔄 Making Updates

### Update Backend:

```bash
# Make changes to Python code
git add .
git commit -m "Update backend feature"
git push origin main
```
Render will automatically detect the push and redeploy.

### Update Frontend:

```bash
# Make changes to HTML/CSS/JS
git add .
git commit -m "Update UI"
git push origin main
```
Vercel will automatically redeploy.

---

## 💰 Cost Considerations

### Free Tier Limitations:

**Render Free Tier:**
- ✅ 750 hours/month free compute
- ✅ Public repositories only
- ❌ Spins down after 15 min inactivity
- ❌ 512 MB RAM
- ❌ Slower CPU

**Vercel Free Tier:**
- ✅ Unlimited bandwidth
- ✅ 100 GB bandwidth
- ✅ Automatic HTTPS
- ✅ Fast global CDN
- ❌ Public repositories only

### Upgrade Recommendations:

For production/SIH demo day:
- **Render Starter:** $7/month (always-on, 512 MB RAM)
- **Render Standard:** $25/month (2 GB RAM, better for ML)
- **Vercel Pro:** $20/month (more bandwidth, analytics)

---

## 🎯 SIH Demo Day Checklist

**1 Week Before:**
- [ ] Test full pipeline end-to-end
- [ ] Upload custom demo scenes
- [ ] Verify all API endpoints work
- [ ] Check response times
- [ ] Test on mobile devices

**1 Day Before:**
- [ ] Upgrade to paid tier (recommended)
- [ ] Verify no build errors
- [ ] Check all environment variables
- [ ] Test with slow internet connection
- [ ] Prepare fallback (local backup)

**On Demo Day:**
- [ ] Have backup local deployment ready
- [ ] Keep Render/Vercel dashboards open
- [ ] Monitor logs during demo
- [ ] Have URLs readily accessible
- [ ] Test before your presentation slot

---

## 🆘 Emergency Contact

If deployment fails before SIH:

1. **Run locally:** Use local deployment as backup
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Use ngrok** for temporary public URL:
   ```bash
   ngrok http 8000
   ```

3. **Contact support:**
   - Render: [render.com/support](https://render.com/support)
   - Vercel: [vercel.com/support](https://vercel.com/support)

---

## 📚 Additional Resources

- [Render Python Deployment Guide](https://render.com/docs/deploy-fastapi)
- [Vercel Documentation](https://vercel.com/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [CORS Troubleshooting](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)

---

## ✅ Summary

You now have:
- ✅ **Backend** deployed on Render with API endpoints
- ✅ **Frontend** deployed on Vercel with interactive UI
- ✅ **Automatic deployments** on every git push
- ✅ **Free hosting** for your SIH project
- ✅ **Global CDN** for fast worldwide access
- ✅ **HTTPS** enabled by default

**Your deployed URLs:**
- Frontend: `https://your-project.vercel.app`
- Backend: `https://your-backend.onrender.com`
- API Docs: `https://your-backend.onrender.com/docs`

Good luck with Smart India Hackathon 2026! 🎉
