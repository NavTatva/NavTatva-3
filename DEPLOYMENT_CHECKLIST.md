# 🚀 Quick Deployment Checklist for NavTatva

Use this checklist to deploy your project step-by-step.

---

## 📝 What You Need to Provide

### Required:
- [ ] **GitHub Account** - [github.com](https://github.com) (free)
- [ ] **Vercel Account** - [vercel.com](https://vercel.com) (free, sign up with GitHub)
- [ ] **Render Account** - [render.com](https://render.com) (free, sign up with GitHub)

### Optional (for enhanced features):
- [ ] **Hugging Face Token** - [huggingface.co](https://huggingface.co) (free, for model downloads)
- [ ] **AISStream API Key** - [aisstream.io](https://aisstream.io) (free tier, for live AIS)

---

## 🔄 Deployment Steps

### Step 1: Push Code to GitHub ✅

```bash
cd c:\Users\LENOVO\Downloads\SIH-Nav\NavTatva-3

# Initialize git (if not done)
git init
git add .
git commit -m "Initial commit - NavTatva SIH"

# Create repository on github.com (name: navtatva-sih, PUBLIC)

# Push code
git remote add origin https://github.com/YOUR_USERNAME/navtatva-sih.git
git branch -M main
git push -u origin main
```

**✅ Verify:** Code visible on GitHub

---

### Step 2: Deploy Backend on Render 🔧

1. **Login to Render** → Sign up with GitHub
2. **New Web Service** → Connect GitHub repository
3. **Configure:**
   ```
   Name: navtatva-backend
   Runtime: Python 3
   Build: pip install -r requirements.txt && python scripts/bootstrap_demo.py --minimal
   Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   Plan: Free
   ```
4. **Add Environment Variables:**
   ```
   TIDETRACE_OFFLINE = 1
   PYTHON_VERSION = 3.11.0
   ```
5. **Deploy** → Wait 5-10 minutes

**✅ Copy Backend URL:** `https://navtatva-backend-xxxx.onrender.com`

**✅ Test:** Visit `/api/health` endpoint

---

### Step 3: Update Frontend Configuration 📝

Before deploying frontend, update the backend URL:

1. Open `app/static/index.html`
2. Find line ~450:
   ```javascript
   : 'https://your-backend-url.onrender.com';
   ```
3. Replace with your Render URL:
   ```javascript
   : 'https://navtatva-backend-xxxx.onrender.com';
   ```
4. Save and commit:
   ```bash
   git add app/static/index.html
   git commit -m "Update backend URL"
   git push origin main
   ```

---

### Step 4: Deploy Frontend on Vercel 🌐

1. **Login to Vercel** → Sign up with GitHub
2. **Import Project** → Select your repository
3. **Configure:**
   ```
   Framework: Other
   Root: ./
   Build Command: (empty)
   Output: app/static
   ```
4. **Environment Variable:**
   ```
   API_BASE_URL = https://your-render-backend-url.onrender.com
   ```
5. **Deploy** → Wait 1-2 minutes

**✅ Copy Frontend URL:** `https://your-project.vercel.app`

**✅ Test:** Open URL and try loading the map

---

### Step 5: Final Configuration 🔧

Update `vercel.json` with actual backend URL:

1. Open `vercel.json`
2. Replace:
   ```json
   "destination": "https://navtatva-backend-xxxx.onrender.com/api/:path*"
   ```
3. Commit and push:
   ```bash
   git add vercel.json
   git commit -m "Update API proxy"
   git push origin main
   ```

Vercel will auto-redeploy.

---

## 🧪 Testing Checklist

### Backend Tests:
- [ ] `/api/health` returns 200 OK
- [ ] `/docs` shows API documentation
- [ ] `/api/scenes` returns scenes list
- [ ] No errors in Render logs

### Frontend Tests:
- [ ] Homepage loads
- [ ] Map displays correctly
- [ ] Scene selector works
- [ ] "Run analysis" button works
- [ ] No CORS errors in browser console (F12)

### Full Pipeline Test:
- [ ] Select a scene
- [ ] Click "Run analysis"
- [ ] Wait for completion (2-5 min on free tier)
- [ ] Results display correctly
- [ ] Can view vessel tracks
- [ ] Can export report

---

## 📊 Your Deployment URLs

Fill in after deployment:

```
Frontend: https://_________________________.vercel.app
Backend:  https://_________________________.onrender.com
API Docs: https://_________________________.onrender.com/docs
```

---

## 🚨 Common Issues & Quick Fixes

### Issue: CORS Error
**Fix:** Update `app/main.py` CORS settings with your Vercel domain

### Issue: Backend "Application Error"
**Fix:** Check Render logs → Verify Python version → Check requirements.txt

### Issue: Frontend can't connect to backend
**Fix:** Verify backend URL in `index.html` → Test `/api/health` directly

### Issue: Analysis times out
**Fix:** Expected on free tier → Upgrade or run locally for demo

### Issue: Service unavailable intermittently
**Fix:** Free tier sleeps after 15 min → First request wakes it up (slow)

---

## 🎯 Pre-Demo Day Checklist

**1 Week Before:**
- [ ] Full end-to-end test
- [ ] Upload custom scenes
- [ ] Test on multiple browsers
- [ ] Test on mobile
- [ ] Prepare backup plan

**1 Day Before:**
- [ ] Consider upgrading to paid tier
- [ ] Verify all features work
- [ ] Check response times
- [ ] Have local backup ready
- [ ] Test with slow connection

**Demo Day Morning:**
- [ ] Test deployment
- [ ] Open dashboards (Render + Vercel)
- [ ] Have URLs ready
- [ ] Local backup running
- [ ] Browser tabs prepared

---

## 🆘 Emergency Backup Plan

If deployment fails:

**Option 1: Local + ngrok**
```bash
# Terminal 1: Run locally
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Expose with ngrok
ngrok http 8000
```

**Option 2: Full Local**
```bash
python -m uvicorn app.main:app --reload
# Open http://localhost:8000
```

---

## 📞 Support Resources

- **Render Docs:** [render.com/docs](https://render.com/docs)
- **Vercel Docs:** [vercel.com/docs](https://vercel.com/docs)
- **CORS Guide:** [enable-cors.org](https://enable-cors.org)
- **FastAPI Deploy:** [fastapi.tiangolo.com/deployment](https://fastapi.tiangolo.com/deployment/)

---

## ✅ Deployment Complete!

When all checkboxes are ✅, your project is live and ready for SIH demo! 🎉

**Remember:**
- Keep both dashboard tabs open during demo
- Have local backup running
- Monitor logs for any issues
- Test before your presentation time

Good luck! 🚀
