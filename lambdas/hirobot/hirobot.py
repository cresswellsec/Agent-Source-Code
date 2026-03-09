import json
import hmac
import hashlib
import boto3
import urllib.request
import os


def get_secret(secret_name):
    client = boto3.client("secretsmanager")
    return client.get_secret_value(SecretId=secret_name)["SecretString"]


def validate_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def post_github_comment(repo: str, issue_number: int, message: str, token: str):
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    data = json.dumps({"body": message}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "hirobot/1.0")
    urllib.request.urlopen(req)


def call_bedrock(prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    response = client.converse(
        modelId="amazon.nova-micro-v1:0",
        messages=[{
            "role": "user",
            "content": [{"text": prompt}]
        }]
    )
    return response["output"]["message"]["content"][0]["text"]


def handler(event, _context):
    # 1. Validate GitHub webhook signature
    webhook_secret = get_secret("hirobot/github-webhook-secret")
    signature = event.get("headers", {}).get("x-hub-signature-256", "")
    body_raw = event.get("body", "")
    payload = body_raw.encode() if isinstance(body_raw, str) else body_raw

    if not validate_signature(payload, signature, webhook_secret):
        return {"statusCode": 401, "body": "Invalid signature"}

    # 2. Parse event body
    try:
        body = json.loads(body_raw)
    except (json.JSONDecodeError, TypeError):
        return {"statusCode": 400, "body": "Bad request"}

    # 3. Only handle issue/PR comments, ignore everything else
    if "comment" not in body:
        return {"statusCode": 200, "body": "ignored"}

    comment_text = body["comment"]["body"].strip()
    repo = body["repository"]["full_name"]
    issue_number = body["issue"]["number"]

    # 4. Only respond to /hirobot
    if comment_text.lower() != "/hirobot":
        return {"statusCode": 200, "body": "not my command"}

    # 5. Call Bedrock
    response_text = call_bedrock(
        "The user typed /hirobot as a slash command in a GitHub comment. "
        "Reply with just the word 'hi' and nothing else."
    )

    # 6. Post the response back to GitHub
    github_token = get_secret("hirobot/github-token")
    post_github_comment(repo, issue_number, response_text, github_token)

    return {"statusCode": 200, "body": "ok"}
