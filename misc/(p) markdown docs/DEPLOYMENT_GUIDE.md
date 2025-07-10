# 🚀 MCB Deployment Guide

## 🔐 Security Checklist (MUST DO BEFORE DEPLOYMENT)

### ✅ Critical Security Steps:

1. **Switch to Production App**

   - Use `app_production.py` instead of `app.py`
   - Has rate limiting, input validation, timeouts

2. **Set Environment Variables**

   ```bash
   FLASK_ENV=production
   SECRET_KEY=your-super-secret-key-change-this
   ALLOWED_ORIGIN=https://yourdomain.com
   STOCKFISH_PATH=/usr/bin/stockfish
   ```

3. **Update requirements.txt**
   ```bash
   Flask==2.3.3
   Flask-CORS==4.0.0
   Flask-Limiter==3.12
   Flask-Talisman==1.1.0
   python-dotenv==1.1.1
   chess==1.999
   requests==2.31.0
   ```

## 🌐 Deployment Options

### Option 1: Railway (Recommended)

1. **Sign up**: [railway.app](https://railway.app)
2. **Connect GitHub repo**
3. **Set environment variables** in dashboard
4. **Deploy automatically** ✅

### Option 2: Render

1. **Sign up**: [render.com](https://render.com)
2. **Connect GitHub repo**
3. **Set environment variables**
4. **Deploy**

### Option 3: Heroku

1. **Sign up**: [heroku.com](https://heroku.com)
2. **Install Heroku CLI**
3. **Create app**: `heroku create your-app-name`
4. **Set environment variables**: `heroku config:set FLASK_ENV=production`
5. **Deploy**: `git push heroku main`

## 🛡️ Security Configuration

### Environment Variables to Set:

```bash
# Required
FLASK_ENV=production
SECRET_KEY=your-32-character-secret-key-here
ALLOWED_ORIGIN=https://yourdomain.com

# Optional but recommended
STOCKFISH_PATH=/usr/bin/stockfish
```

### Additional Security Measures:

1. **Domain Restrictions**: Set `ALLOWED_ORIGIN` to your actual domain
2. **Rate Limiting**: Already configured (5 requests/minute)
3. **Input Validation**: Usernames are validated
4. **Timeouts**: 5-minute analysis timeout
5. **Error Handling**: Graceful error responses

## 📦 Deployment Files

### Required Files:

- `app_production.py` - Secure Flask app
- `requirements.txt` - Python dependencies
- `Procfile` - Deployment configuration
- `runtime.txt` - Python version specification

### File Structure:

```
MCB/
├── app_production.py      # Main Flask app (use this!)
├── requirements.txt       # Dependencies
├── Procfile              # Deployment config
├── runtime.txt           # Python version
├── index.html            # Frontend
├── styles.css           # Styling
├── main.js              # JavaScript
├── get_games.py         # Game fetching
├── analyze_games.py     # Analysis logic
└── stockfish/           # Chess engine
```

## 🚨 Production Limitations

### Security Limitations:

- **1 game analysis only** (prevents resource abuse)
- **5 requests per minute** (prevents DDoS)
- **5 minute timeout** (prevents hanging processes)
- **10 concurrent users max** (prevents overload)

### To Upgrade for Production:

1. **Add database** for user accounts
2. **Add payment processing** for premium features
3. **Add monitoring** (error tracking, analytics)
4. **Add caching** for better performance
5. **Add email notifications** for completion
6. **Add user authentication** for personalized experience

## 💰 Monetization Setup

### Free Tier:

- 1 game analysis
- Basic blunder detection
- No account required

### Premium Tier ($5/month):

- 10 game analysis
- Advanced pattern recognition
- Progress tracking
- Priority support

### Implementation:

1. **Add Stripe integration** for payments
2. **Add user authentication** system
3. **Add usage tracking** and limits
4. **Add premium features** behind paywall

## 🔧 Testing Your Deployment

### Pre-deployment Checklist:

- [ ] `app_production.py` works locally
- [ ] Environment variables set
- [ ] Requirements.txt updated
- [ ] Stockfish path configured
- [ ] CORS origins restricted
- [ ] Rate limiting tested

### Post-deployment Testing:

1. **Load the website** - Check if it loads
2. **Test analysis** - Try analyzing a game
3. **Test rate limiting** - Make multiple requests
4. **Test error handling** - Try invalid usernames
5. **Test mobile** - Check responsive design

## 🚀 Go Live Steps

1. **Deploy to Railway/Render/Heroku**
2. **Set all environment variables**
3. **Test thoroughly**
4. **Monitor for errors**
5. **Add domain name** (optional)
6. **Set up SSL certificate** (automatic on most platforms)
7. **Add analytics** (Google Analytics)

## 📊 Monitoring & Maintenance

### Essential Monitoring:

- **Error rates** - Track application errors
- **Response times** - Monitor performance
- **Usage patterns** - Track user behavior
- **Resource usage** - Monitor server resources

### Regular Maintenance:

- **Update dependencies** monthly
- **Check security alerts** weekly
- **Review error logs** daily
- **Monitor costs** monthly

## 🔒 Security Best Practices

### Current Security Features:

✅ Rate limiting (5 requests/minute)
✅ Input validation (usernames)
✅ HTTPS enforcement
✅ CORS restrictions
✅ Request timeouts
✅ Error handling
✅ Resource limits

### Additional Security (Advanced):

- [ ] User authentication
- [ ] API key management
- [ ] Database security
- [ ] Logging and monitoring
- [ ] Security headers
- [ ] SQL injection prevention
- [ ] XSS protection

## 💡 Cost Estimation

### Free Tier (Most Platforms):

- **Railway**: 500 hours/month free
- **Render**: 750 hours/month free
- **Heroku**: 1000 hours/month free

### Expected Monthly Costs:

- **Free tier**: $0 (with usage limits)
- **Basic plan**: $5-10/month
- **Production plan**: $25-50/month

### Cost Optimization:

1. **Use free tiers** initially
2. **Monitor usage** closely
3. **Optimize code** for efficiency
4. **Cache results** where possible
5. **Implement usage limits**
