#!/usr/bin/env python3
"""
AWS Deployment Script for PropTrader
Deploys to AWS Elastic Beanstalk
"""

import os
import subprocess
import sys
import json
from datetime import datetime

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return None

def check_aws_cli():
    """Check if AWS CLI is installed"""
    result = run_command("aws --version", "Checking AWS CLI")
    if result:
        print(f"📋 AWS CLI version: {result.strip()}")
        return True
    else:
        print("❌ AWS CLI not found. Please install it first:")
        print("   brew install awscli")
        print("   aws configure")
        return False

def create_eb_config():
    """Create Elastic Beanstalk configuration"""
    config = {
        "AWSEBDockerrunVersion": "1",
        "Image": {
            "Name": "amazon/aws-eb-python:3.9",
            "Update": "true"
        },
        "Ports": [
            {
                "ContainerPort": 8001,
                "HostPort": 80
            }
        ],
        "Volumes": [],
        "Logging": "/var/log/nginx"
    }
    
    with open('.ebextensions/01_flask.config', 'w') as f:
        f.write("""option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: wsgi:app
  aws:elasticbeanstalk:environment:proxy:staticfiles:
    /static: static/
  aws:autoscaling:launchconfiguration:
    InstanceType: t2.micro
  aws:elasticbeanstalk:application:environment:
    FLASK_ENV: production
    PYTHONPATH: /var/app/current
""")
    
    with open('.ebextensions/02_environment.config', 'w') as f:
        f.write("""option_settings:
  aws:elasticbeanstalk:application:environment:
    SECRET_KEY: "your-secret-key-here"
    JWT_SECRET_KEY: "your-jwt-secret-key-here"
    FLASK_ENV: production
""")
    
    print("✅ Created Elastic Beanstalk configuration")

def create_dockerfile():
    """Create Dockerfile for container deployment"""
    dockerfile_content = """FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs

# Expose port
EXPOSE 8001

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Run the application
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:8001", "wsgi:app"]
"""
    
    with open('Dockerfile', 'w') as f:
        f.write(dockerfile_content)
    
    print("✅ Created Dockerfile")

def create_docker_compose():
    """Create docker-compose.yml for local testing"""
    compose_content = """version: '3.8'

services:
  web:
    build: .
    ports:
      - "8001:8001"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=sqlite:///proptrader.db
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    restart: unless-stopped
"""
    
    with open('docker-compose.yml', 'w') as f:
        f.write(compose_content)
    
    print("✅ Created docker-compose.yml")

def create_eb_ignore():
    """Create .ebignore file"""
    ignore_content = """# Development files
*.pyc
__pycache__/
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Database
*.db
*.sqlite

# Git
.git/
.gitignore

# AWS
.elasticbeanstalk/
.ebextensions/

# Docker
Dockerfile
docker-compose.yml
.dockerignore

# Documentation
README.md
docs/

# Tests
tests/
test_*
*_test.py

# Temporary files
*.tmp
*.temp
"""
    
    with open('.ebignore', 'w') as f:
        f.write(ignore_content)
    
    print("✅ Created .ebignore")

def deploy_to_eb():
    """Deploy to Elastic Beanstalk"""
    app_name = "proptrader-exchange"
    environment_name = "proptrader-prod"
    
    # Initialize EB application
    print("🚀 Deploying to AWS Elastic Beanstalk...")
    
    # Check if EB CLI is installed
    eb_version = run_command("eb --version", "Checking EB CLI")
    if not eb_version:
        print("❌ EB CLI not found. Installing...")
        run_command("pip install awsebcli", "Installing EB CLI")
    
    # Initialize EB application
    if not os.path.exists('.elasticbeanstalk'):
        run_command("eb init -p python-3.9 proptrader-exchange --region us-east-1", "Initializing EB application")
    
    # Create environment
    run_command(f"eb create {environment_name} --instance-type t2.micro --single-instance", "Creating EB environment")
    
    # Deploy
    run_command("eb deploy", "Deploying application")
    
    # Get the URL
    url = run_command("eb status", "Getting application URL")
    if url:
        print(f"🌐 Your PropTrader Exchange is now live at: {url}")
    
    return True

def create_cloudformation_template():
    """Create CloudFormation template for infrastructure"""
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "PropTrader Exchange Infrastructure",
        "Parameters": {
            "EnvironmentName": {
                "Type": "String",
                "Default": "proptrader",
                "Description": "Environment name"
            }
        },
        "Resources": {
            "ElasticBeanstalkApplication": {
                "Type": "AWS::ElasticBeanstalk::Application",
                "Properties": {
                    "ApplicationName": {"Ref": "EnvironmentName"},
                    "Description": "PropTrader Exchange Application"
                }
            },
            "ElasticBeanstalkEnvironment": {
                "Type": "AWS::ElasticBeanstalk::Environment",
                "Properties": {
                    "ApplicationName": {"Ref": "ElasticBeanstalkApplication"},
                    "EnvironmentName": {"Fn::Sub": "${EnvironmentName}-prod"},
                    "SolutionStackName": "64bit Amazon Linux 2 v3.4.0 running Python 3.9",
                    "OptionSettings": [
                        {
                            "Namespace": "aws:autoscaling:launchconfiguration",
                            "OptionName": "InstanceType",
                            "Value": "t2.micro"
                        },
                        {
                            "Namespace": "aws:elasticbeanstalk:environment",
                            "OptionName": "EnvironmentType",
                            "Value": "SingleInstance"
                        }
                    ]
                }
            }
        },
        "Outputs": {
            "ApplicationURL": {
                "Description": "URL of the PropTrader Exchange",
                "Value": {"Fn::Sub": "http://${ElasticBeanstalkEnvironment.EndpointURL}"},
                "Export": {"Name": {"Fn::Sub": "${EnvironmentName}-URL"}}
            }
        }
    }
    
    with open('cloudformation-template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print("✅ Created CloudFormation template")

def main():
    """Main deployment function"""
    print("🚀 PropTrader AWS Deployment Script")
    print("=" * 50)
    
    # Check prerequisites
    if not check_aws_cli():
        return False
    
    # Create deployment files
    os.makedirs('.ebextensions', exist_ok=True)
    create_eb_config()
    create_dockerfile()
    create_docker_compose()
    create_eb_ignore()
    create_cloudformation_template()
    
    print("\n📋 Deployment files created successfully!")
    print("\n🎯 Next steps:")
    print("1. Configure AWS credentials: aws configure")
    print("2. Deploy to EB: python deploy_aws.py --deploy")
    print("3. Or deploy manually: eb deploy")
    print("4. Or use CloudFormation: aws cloudformation create-stack --stack-name proptrader --template-body file://cloudformation-template.json")
    
    # Check if --deploy flag is provided
    if '--deploy' in sys.argv:
        return deploy_to_eb()
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 