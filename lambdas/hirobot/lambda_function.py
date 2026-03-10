import json
import hmac
import hashlib
import boto3
import urllib.request
import os
import base64


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
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )
    response = client.converse(
        modelId="amazon.nova-micro-v1:0",
        messages=[{
            "role": "user",
            "content": [{"text": prompt}]
        }]
    )
    return response["output"]["message"]["content"][0]["text"]


def lambda_handler(event, _context):
    # 1. Get the webhook signing secret from Secrets Manager
    webhook_secret = get_secret("hirobot/github-webhook-secret")
    signature = event.get("headers", {}).get("x-hub-signature-256", "")

    # 2. Handle API Gateway base64 encoding
    # API Gateway sometimes base64-encodes the request body before passing
    # it to Lambda. If that happens we need to decode it back to the original
    # raw bytes — because GitHub signed the original bytes, not the encoded version.
    # If we run HMAC on the wrong bytes, the signature will never match.
    body_raw = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)

    if is_base64:
        payload = base64.b64decode(body_raw)
        body_raw = payload.decode("utf-8")
    else:
        payload = body_raw.encode("utf-8") if isinstance(body_raw, str) else body_raw

    # 3. Validate the signature — reject anything not from GitHub
    if not validate_signature(payload, signature, webhook_secret):
        print(f"Signature validation failed. Received sig: {signature}")
        return {"statusCode": 401, "body": "Invalid signature"}

    # 4. Parse the JSON body
    try:
        body = json.loads(body_raw)
    except (json.JSONDecodeError, TypeError):
        return {"statusCode": 400, "body": "Bad request"}

    # 5. Only handle issue/PR comments, ignore everything else silently
    if "comment" not in body:
        return {"statusCode": 200, "body": "ignored"}

    comment_text = body["comment"]["body"].strip()
    repo = body["repository"]["full_name"]
    issue_number = body["issue"]["number"]

    # 6. Only respond to /hirobot — ignore all other comments
    if comment_text.lower() != "/hirobot":
        return {"statusCode": 200, "body": "not my command"}

    # 7. Call Bedrock to generate the response
    response_text = call_bedrock(
        "The user typed /hirobot as a slash command in a GitHub comment. "
        "Reply with just the word 'hi' and nothing else."
    )

    # 8. Post the response back to GitHub as a comment
    github_token = get_secret("hirobot/github-token")
    post_github_comment(repo, issue_number, response_text, github_token)

    return {"statusCode": 200, "body": "ok"}
