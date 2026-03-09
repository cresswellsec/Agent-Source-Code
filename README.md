# Agent-Source-Code

Source code for GitOps agents that run on AWS Bedrock and respond to slash commands in GitHub.

## How it works

A slash command typed in a GitHub issue or PR comment triggers a Lambda via webhook,
calls an AI model on AWS Bedrock, and posts the response back as a comment.

```
cresswellsec/lab-target-project
  └── issue comment: "/hirobot"
          ↓
  GitHub webhook
          ↓
  API Gateway → Lambda (hirobot)
          ↓
  AWS Bedrock (Nova Micro)
          ↓
  GitHub comment reply
```

## Repos

| Repo | Purpose |
|------|---------|
| `Agent-Source-Code` (this repo) | Lambda code, IAM policies, CI/CD |
| `lab-target-project` | The subject repo — where slash commands are typed |

## Agents

### hirobot

Responds to `/hirobot` comments in `lab-target-project` with a Bedrock-generated reply.
The hello-world starting point — proves the full webhook → Lambda → Bedrock → GitHub loop works.

- **Lambda:** `lambdas/hirobot/hirobot.py`
- **Model:** Amazon Nova Micro (`amazon.nova-micro-v1:0`)
- **Auth:** IAM roles + GitHub webhook signature validation
- **Secrets:** GitHub token and webhook secret stored in AWS Secrets Manager

## Repo structure

```
Agent-Source-Code/
├── lambdas/
│   └── hirobot/
│       ├── hirobot.py        # Lambda handler
│       └── requirements.txt  # boto3 (Lambda runtime dep)
├── iam/
│   ├── lambda-role-policy.json   # Permissions: Bedrock, Secrets Manager, CloudWatch
│   └── lambda-trust-policy.json  # Trust: lambda.amazonaws.com
├── docs/
│   └── setup.md              # Step-by-step deploy guide
├── .github/
│   └── workflows/
│       └── deploy-hirobot.yml  # Auto-deploy on push to main
├── requirements.txt          # Local dev deps (boto3, pytest)
├── Dockerfile                # Reserved for containerized agents
└── .gitignore / .dockerignore
```

## Setup

See [docs/setup.md](docs/setup.md) for the full step-by-step guide covering:
- Enabling Bedrock model access
- Creating Secrets Manager secrets
- IAM role creation
- Lambda deployment
- API Gateway + GitHub webhook configuration
- Optional GitHub Actions auto-deploy via OIDC
