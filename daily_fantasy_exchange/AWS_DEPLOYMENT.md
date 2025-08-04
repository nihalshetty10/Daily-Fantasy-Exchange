# PropTrader AWS Deployment Guide

## 🚀 Quick Deploy to AWS

Your PropTrader Exchange can be deployed to AWS in minutes! Here are the steps:

### Prerequisites

1. **Install AWS CLI:**
   ```bash
   brew install awscli
   aws configure
   ```

2. **Install EB CLI:**
   ```bash
   pip install awsebcli
   ```

### Option 1: Automatic Deployment (Recommended)

Run the deployment script:
```bash
python deploy_aws.py --deploy
```

This will:
- ✅ Create all necessary AWS configuration files
- ✅ Deploy to Elastic Beanstalk
- ✅ Set up the production environment
- ✅ Give you a live URL

### Option 2: Manual Deployment

1. **Initialize Elastic Beanstalk:**
   ```bash
   eb init -p python-3.9 proptrader-exchange --region us-east-1
   ```

2. **Create environment:**
   ```bash
   eb create proptrader-prod --instance-type t2.micro --single-instance
   ```

3. **Deploy:**
   ```bash
   eb deploy
   ```

4. **Get your URL:**
   ```bash
   eb status
   ```

### Option 3: Docker Deployment

1. **Build and test locally:**
   ```bash
   docker-compose up --build
   ```

2. **Deploy to ECS:**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
   docker build -t proptrader .
   docker tag proptrader:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/proptrader:latest
   docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/proptrader:latest
   ```

### Option 4: CloudFormation Deployment

1. **Deploy infrastructure:**
   ```bash
   aws cloudformation create-stack \
     --stack-name proptrader \
     --template-body file://cloudformation-template.json \
     --capabilities CAPABILITY_IAM
   ```

2. **Check deployment:**
   ```bash
   aws cloudformation describe-stacks --stack-name proptrader
   ```

## 🌐 Environment Variables

Set these in your AWS environment:

```bash
SECRET_KEY=your-super-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
FLASK_ENV=production
DATABASE_URL=postgresql://username:password@host:port/database
REDIS_URL=redis://host:port
```

## 📊 Database Setup

### For Production (PostgreSQL):

1. **Create RDS instance:**
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier proptrader-db \
     --db-instance-class db.t3.micro \
     --engine postgres \
     --master-username admin \
     --master-user-password your-password \
     --allocated-storage 20
   ```

2. **Update DATABASE_URL:**
   ```
   DATABASE_URL=postgresql://admin:your-password@proptrader-db.region.rds.amazonaws.com:5432/proptrader
   ```

### For Development (SQLite):
The app will use SQLite by default if no DATABASE_URL is set.

## 🔧 Configuration Files Created

- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Local development
- `wsgi.py` - WSGI entry point
- `.ebextensions/` - Elastic Beanstalk config
- `cloudformation-template.json` - Infrastructure as code

## 🎯 Features Deployed

- ✅ Real-time trading interface
- ✅ Live prop generation from actual games
- ✅ User authentication and portfolios
- ✅ Real-time WebSocket updates
- ✅ Mobile-responsive design
- ✅ Auto-scaling infrastructure

## 📈 Monitoring

1. **CloudWatch Logs:**
   ```bash
   aws logs describe-log-groups --log-group-name-prefix /aws/elasticbeanstalk
   ```

2. **Application Metrics:**
   - CPU utilization
   - Memory usage
   - Request count
   - Error rates

## 🔒 Security

1. **HTTPS Setup:**
   ```bash
   eb config
   # Add SSL certificate
   ```

2. **Environment Variables:**
   - Never commit secrets to code
   - Use AWS Systems Manager Parameter Store
   - Rotate keys regularly

## 💰 Cost Optimization

- **Free Tier:** t2.micro instances are free for 12 months
- **Auto Scaling:** Scale down during off-hours
- **Reserved Instances:** For predictable workloads
- **Spot Instances:** For non-critical workloads

## 🚨 Troubleshooting

### Common Issues:

1. **Port 8001 not accessible:**
   - Check security groups
   - Verify load balancer configuration

2. **Database connection errors:**
   - Verify DATABASE_URL
   - Check RDS security groups

3. **WebSocket connection issues:**
   - Ensure Redis is running
   - Check SocketIO configuration

### Debug Commands:

```bash
# Check application logs
eb logs

# SSH into instance
eb ssh

# Check environment health
eb health

# View configuration
eb config
```

## 🌍 Global Deployment

For multi-region deployment:

1. **Create multiple environments:**
   ```bash
   eb create proptrader-us-east-1 --region us-east-1
   eb create proptrader-eu-west-1 --region eu-west-1
   eb create proptrader-ap-southeast-1 --region ap-southeast-1
   ```

2. **Set up Route 53:**
   - Create hosted zone
   - Configure health checks
   - Set up failover routing

## 📞 Support

If you encounter issues:

1. Check the logs: `eb logs`
2. Review the configuration: `eb config`
3. Test locally: `docker-compose up`
4. Check AWS Console for detailed metrics

## 🎉 Success!

Once deployed, your PropTrader Exchange will be available at:
`https://your-app-name.region.elasticbeanstalk.com`

Users can:
- ✅ Register and login
- ✅ View real-time props
- ✅ Trade contracts
- ✅ Manage portfolios
- ✅ Track performance

**Your PropTrader Exchange is now live and global! 🚀** 