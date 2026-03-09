# Hirobot Setup Guide

## Overview

`/hirobot` is a GitHub comment slash command that calls AWS Bedrock (Nova Micro) and posts a reply back to the same issue or PR.

```
lab-target-project: comment "/hirobot"
        ↓
GitHub webhook → API Gateway → Lambda (hirobot)
        ↓
Bedrock (Nova Micro)
        ↓
GitHub comment reply
```

---

## Prerequisites

- AWS account with Bedrock Nova Micro access enabled
- GitHub fine-grained personal access token (PAT)
- AWS CLI configured locally (`aws configure`)

---

## Step 1: Enable Bedrock Nova Micro

AWS Console → Bedrock → Model access → Request access to **Amazon Nova Micro**.
Takes ~30 seconds to activate.

---

## Step 2: Create Secrets in Secrets Manager

AWS Console → Secrets Manager → Store a new secret → **Other type of secret**

| Secret name                     | Value                                      |
|---------------------------------|--------------------------------------------|
| `hirobot/github-webhook-secret` | A random string you choose (e.g. `myS3cr3tW3bh00k`) |
| `hirobot/github-token`          | Your GitHub fine-grained PAT               |

### GitHub PAT permissions

Go to GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token.
Scope it to **cresswellsec/lab-target-project** only with:
- **Issues**: Read and Write

---

## Step 3: Create the IAM Role

```bash
# Create the role
aws iam create-role \
  --role-name hirobot-lambda-role \
  --assume-role-policy-document file://iam/lambda-trust-policy.json

# Attach the permissions policy
# Replace YOUR_ACCOUNT_ID in iam/lambda-role-policy.json first
aws iam put-role-policy \
  --role-name hirobot-lambda-role \
  --policy-name hirobot-lambda-policy \
  --policy-document file://iam/lambda-role-policy.json
```

---

## Step 4: Deploy the Lambda

```bash
cd lambdas/hirobot
zip hirobot.zip hirobot.py

aws lambda create-function \
  --function-name hirobot \
  --runtime python3.12 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/hirobot-lambda-role \
  --handler hirobot.handler \
  --zip-file fileb://hirobot.zip \
  --timeout 30 \
  --region us-east-1
```

To update the function after code changes:
```bash
aws lambda update-function-code \
  --function-name hirobot \
  --zip-file fileb://hirobot.zip \
  --region us-east-1
```

---

## Step 5: Create API Gateway

AWS Console → API Gateway → Create API → **HTTP API**

1. Add integration → Lambda → select `hirobot`
2. Route: `POST /webhook`
3. Deploy → stage name: `prod`
4. Copy the invoke URL: `https://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com/webhook`

---

## Step 6: Add GitHub Webhook

Go to **cresswellsec/lab-target-project** → Settings → Webhooks → Add webhook

| Field            | Value                                        |
|------------------|----------------------------------------------|
| Payload URL      | Your API Gateway URL from Step 5             |
| Content type     | `application/json`                           |
| Secret           | Same value as `hirobot/github-webhook-secret` |
| Which events?    | Select **Issue comments** only               |

---

## Step 7: Test It

Open any issue in `cresswellsec/lab-target-project` and comment `/hirobot`.
You should see a reply within a few seconds.

---

## Resource names

| Resource              | Name / ARN                                      |
|-----------------------|-------------------------------------------------|
| Lambda function       | `hirobot`                                       |
| IAM role              | `hirobot-lambda-role`                           |
| Secret (webhook)      | `hirobot/github-webhook-secret`                 |
| Secret (token)        | `hirobot/github-token`                          |
| Bedrock model         | `amazon.nova-micro-v1:0`                        |
| Target repo           | `cresswellsec/lab-target-project`               |
