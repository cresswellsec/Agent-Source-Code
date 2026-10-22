# Agent-Source-Code

Source code for GitOps agents that run on AWS Bedrock and respond to slash commands in GitHub.

## How it works

A slash command typed in a GitHub issue or PR comment triggers a Lambda via webhook,
calls an AI model on AWS Bedrock, and posts the response back as a comment.

```
cresswellsec/agent-target-project
  └── issue comment: "/hirobot"
          ↓
  GitHub webhook (issue_comment event)
          ↓
  API Gateway → https://<api-id>.execute-api.us-east-1.amazonaws.com/webhook
          ↓
  Lambda: hirobot (arn:aws:lambda:us-east-1:123456789012:function:hirobot)
          ↓
  AWS Bedrock — Amazon Nova Micro (amazon.nova-micro-v1:0)
          ↓
  GitHub comment reply posted to agent-target-project
```

## Repos

| Repo | Purpose |
|------|---------|
| `Agent-Source-Code` (this repo) | Lambda code, IAM policies, CI/CD |
| `agent-target-project` | The subject repo — where slash commands are typed |

## Agents

### hirobot

Responds to `/hirobot` comments in `agent-target-project` with a Bedrock-generated reply.
The hello-world starting point — proves the full webhook → Lambda → Bedrock → GitHub loop works.

| Property      | Value                                                            |
|---------------|------------------------------------------------------------------|
| Lambda        | `arn:aws:lambda:us-east-1:123456789012:function:hirobot`         |
| Handler       | `lambda_function.lambda_handler`                                 |
| Model         | `amazon.nova-micro-v1:0` (Nova Micro)                            |
| Webhook URL   | `https://<api-id>.execute-api.us-east-1.amazonaws.com/webhook` |
| IAM role      | `hirobot-lambda-role`                                            |
| Status        | Decommissioned — bot retired, API Gateway deleted                |

## Repo structure

```
Agent-Source-Code/
├── lambdas/
│   └── hirobot/
│       ├── lambda_function.py    # Lambda handler (deployed)
│       ├── hirobot.py            # Original draft — superseded by lambda_function.py
│       └── requirements.txt      # boto3
├── iam/
│   ├── lambda-role-policy.json   # Permissions: Bedrock, Secrets Manager, CloudWatch
│   └── lambda-trust-policy.json  # Trust: lambda.amazonaws.com
├── docs/
│   └── setup.md                  # Full setup guide with deployed resource details
├── .github/
│   └── workflows/
│       └── deploy-hirobot.yml    # Auto-deploy via OIDC (configure OIDC first)
├── requirements.txt              # Local dev deps (boto3, pytest)
├── Dockerfile                    # Reserved for containerized agents
└── .gitignore / .dockerignore
```

## Setup

See [docs/setup.md](docs/setup.md) for the full guide including deployed resource ARNs,
GitHub webhook config, debugging tips, and the optional OIDC auto-deploy setup.
