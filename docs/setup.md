# Hirobot Setup Guide

## What This Is

Hirobot is a GitOps slash command bot that listens for `/hirobot` comments on GitHub issues in
`cresswellsec/agent-target-project`, calls AWS Bedrock to generate a response, and posts that
response back as a GitHub comment. It is the hello-world foundation for a larger GitOps agent
that will eventually analyze policy-as-code files and report configuration errors directly in GitHub.

The architecture is entirely serverless — no server, no container, nothing running idle.
The system only consumes resources when someone actually types a slash command.

```
Comment "/hirobot" on any issue in agent-target-project
        ↓
GitHub fires an issue_comment webhook (HTTPS POST)
        ↓
API Gateway receives the request and forwards it to Lambda
        ↓
Lambda validates the GitHub HMAC-SHA256 signature
        ↓
Lambda calls Bedrock Nova Micro with the prompt
        ↓
Lambda posts the response back as a GitHub comment
```

---

## AWS Resources

All resources live in **us-east-1** (N. Virginia). AWS account: `123456789012`.

### Lambda

| Property       | Value                                                            |
|----------------|------------------------------------------------------------------|
| Function name  | `hirobot`                                                        |
| Runtime        | Python 3.12, x86_64                                             |
| Timeout        | 30 seconds                                                       |
| Execution role | `hirobot-lambda-role`                                            |
| Handler        | `lambda_function.lambda_handler`                                 |
| ARN            | `arn:aws:lambda:us-east-1:123456789012:function:hirobot`         |

### IAM Role

Role name: `hirobot-lambda-role`, trusted by `lambda.amazonaws.com`.
Inline policy `hirobot-lambda-policy` grants exactly three things:

- `bedrock:InvokeModel` scoped to the Nova Micro model ARN
- `secretsmanager:GetSecretValue` scoped to only the two hirobot secrets
- CloudWatch Logs write access scoped to `/aws/lambda/hirobot*`

Note: `bedrock:Converse` is **not** a separate IAM action — the Converse SDK method maps to
`bedrock:InvokeModel` at the IAM layer. No additional Bedrock permission is needed.

### API Gateway

| Property      | Value                                                                        |
|---------------|------------------------------------------------------------------------------|
| Name          | `hirobot-webhook`                                                            |
| API ID        | `<api-id>`                                                                 |
| Type          | HTTP API                                                                     |
| Route         | `POST /webhook`                                                              |
| Stage         | `$default` with auto-deploy enabled                                          |
| Invoke URL    | `https://<api-id>.execute-api.us-east-1.amazonaws.com`                    |
| Webhook URL   | `https://<api-id>.execute-api.us-east-1.amazonaws.com/webhook`            |

### Secrets Manager

| Secret name                     | Purpose                          | Rotation |
|---------------------------------|----------------------------------|----------|
| `hirobot/github-webhook-secret` | HMAC signing secret (GitHub ↔ Lambda) | Manual |
| `hirobot/github-token`          | GitHub fine-grained PAT          | Manual   |

Both encrypted with `aws/secretsmanager` (AWS-managed key).

**Token expiry:** The GitHub PAT expires **June 7 2026**. To renew: generate a new token in
GitHub → Settings → Developer settings → Fine-grained tokens, then update the secret value in
Secrets Manager (Retrieve secret value → Edit).

### Bedrock

Model: `amazon.nova-micro-v1:0`. As of March 2026, AWS no longer requires manual model access
activation — Nova Micro is automatically enabled on first invocation.

---

## GitHub Configuration

Webhook on **cresswellsec/agent-target-project** → Settings → Webhooks:

| Field          | Value                                                                   |
|----------------|-------------------------------------------------------------------------|
| Payload URL    | `https://<api-id>.execute-api.us-east-1.amazonaws.com/webhook`       |
| Content type   | `application/json`                                                      |
| SSL verify     | Enabled                                                                 |
| Events         | Issue comments only                                                     |
| Secret         | Must exactly match value in `hirobot/github-webhook-secret`             |

Fine-grained PAT **hirobot-lab** scoped to `cresswellsec/agent-target-project`:

| Permission     | Level          |
|----------------|----------------|
| Issues         | Read and Write |
| Contents       | Read-only      |
| Pull Requests  | Read-only      |
| All others     | No Access      |

---

## How It Works

### Signature validation
GitHub signs each webhook payload with HMAC-SHA256 using the shared secret and sends the result
in the `X-Hub-Signature-256` header. Lambda fetches the same secret from Secrets Manager and
independently computes the HMAC. `hmac.compare_digest` is used instead of `==` because it runs
in constant time — a plain `==` comparison leaks information through response timing that could
let an attacker guess the signature byte by byte.

### The base64 gotcha
API Gateway sometimes base64-encodes the request body before passing it to Lambda
(`isBase64Encoded: true`). GitHub signs the **original raw bytes**, not the base64 string. If
Lambda runs HMAC on the base64-encoded version it computes a completely different hash and every
delivery fails with 401. The handler checks `isBase64Encoded` and decodes back to raw bytes
before computing the signature. Do not remove this logic.

### Secrets at runtime
Lambda fetches secrets from Secrets Manager at runtime via `boto3`. The execution role is
automatically injected with temporary credentials by AWS — no access keys appear in the code,
environment variables, or logs. Those credentials are scoped to only what `hirobot-lambda-role`
permits and are rotated automatically by AWS every few hours.

### Ignoring non-command events with 200
Lambda returns `200` for webhook events it intentionally ignores (not a comment, not `/hirobot`).
Returning any non-200 status would cause GitHub to mark those deliveries as failed and eventually
disable the webhook.

---

## Adding New Slash Commands

The entire pipeline (webhook validation, GitHub API integration) already exists. Adding a command
is just adding an `elif` branch in `lambda_handler`:

```python
elif comment_text.lower().startswith("/check"):
    filename = comment_text.split()[1]          # e.g. "/check blahconfig" → "blahconfig"
    file_content = fetch_file_from_github(repo, filename, github_token)
    result = call_bedrock(f"Check this config for errors:\n\n{file_content}")
    post_github_comment(repo, issue_number, result, github_token)
```

No IAM changes needed — the role already has Contents read access via the GitHub PAT.

---

## Deploying Code Changes

**Currently: manual.** Paste updated code into the Lambda console editor and click **Deploy**.
The Lambda handler must remain set to `lambda_function.lambda_handler`.

**Future: automatic via GitHub Actions.** The workflow at
`.github/workflows/deploy-hirobot.yml` will auto-deploy on push to `main` once OIDC is
configured. See Step 8 below.

### Step 8: OIDC Auto-Deploy (optional, do after /hirobot is confirmed working)

#### 1. Create OIDC identity provider in AWS

AWS Console → IAM → Identity providers → Add provider
- Provider type: **OpenID Connect**
- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

#### 2. Create the deploy role

```bash
aws iam create-role \
  --role-name hirobot-github-deploy-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"},
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
        "StringLike": {"token.actions.githubusercontent.com:sub": "repo:cresswellsec/Agent-Source-Code:*"}
      }
    }]
  }'

aws iam put-role-policy \
  --role-name hirobot-github-deploy-role \
  --policy-name deploy-lambda \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["lambda:UpdateFunctionCode", "lambda:GetFunction"],
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:hirobot"
    }]
  }'
```

#### 3. Add the role ARN as a GitHub Actions secret

`Agent-Source-Code` → Settings → Secrets and variables → Actions → New repository secret:

| Name                  | Value                                                                        |
|-----------------------|------------------------------------------------------------------------------|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::123456789012:role/hirobot-github-deploy-role`                  |

---

## Debugging

**CloudWatch Logs** is always the first stop: Lambda → hirobot → Monitor → View CloudWatch logs
→ click the most recent log stream. Full Python tracebacks appear there.

Common failure modes encountered during initial setup:

| Symptom | Cause |
|---------|-------|
| Lambda runs old code silently | Forgot to click **Deploy** after pasting code |
| 401 on every delivery | Webhook secret in GitHub ≠ value in Secrets Manager |
| Runtime error on every invocation | Handler setting doesn't match function name in code |
| Timeout on every invocation | Lambda timeout left at default 3s — must be 30s |
| Signature mismatch despite correct secret | API Gateway base64-encoded the body — check `isBase64Encoded` handling |

---

## Cost

~**$0.80/month** at lab scale (two Secrets Manager secrets at $0.40 each). Lambda, API Gateway,
and Bedrock Nova Micro are effectively free at personal lab invocation volumes. Secrets Manager
has no free tier for stored secrets. SSM Parameter Store Standard is free but Secrets Manager
is the correct pattern for credentials.

---

## Resource Summary

| Resource              | Name / Value                                                        |
|-----------------------|---------------------------------------------------------------------|
| Lambda function       | `hirobot`                                                           |
| Lambda ARN            | `arn:aws:lambda:us-east-1:123456789012:function:hirobot`            |
| IAM role              | `hirobot-lambda-role`                                               |
| API Gateway ID        | `<api-id>`                                                        |
| Webhook URL           | `https://<api-id>.execute-api.us-east-1.amazonaws.com/webhook`   |
| Secret (webhook)      | `hirobot/github-webhook-secret`                                     |
| Secret (token)        | `hirobot/github-token`                                              |
| PAT name              | `hirobot-lab` (expires June 7 2026)                                |
| Bedrock model         | `amazon.nova-micro-v1:0`                                            |
| Target repo           | `cresswellsec/agent-target-project`                                 |
| Source repo           | `cresswellsec/Agent-Source-Code`                                    |
