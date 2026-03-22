# Remote Deployment

`forest` is a single Docker container (FastAPI + Uvicorn) backed by PostgreSQL with pgvector. Any hosting that can run a container image and connect to a Postgres instance with the `vector` extension works. This guide covers **AWS** and **GCP** as the two most common choices.

Both paths follow the same pattern:

1. Provision a managed PostgreSQL instance **with pgvector**.
2. Push the `forest` Docker image to a container registry.
3. Deploy the container with the right environment variables.
4. Point your Slack app's Request URL at the public endpoint.

---

## Prerequisites (both providers)

- Docker installed locally (to build and push the image).
- The provider's CLI authenticated (`aws` or `gcloud`).
- A filled-in `.env` with your Slack and OpenRouter credentials (see [Installation](installation.md)).

---

## AWS

### 1. Database — RDS PostgreSQL with pgvector

RDS PostgreSQL 15+ bundles pgvector as a trusted extension.

```bash
aws rds create-db-instance \
  --db-instance-identifier forest-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16.4 \
  --master-username forest \
  --master-user-password '<DB_PASSWORD>' \
  --allocated-storage 20 \
  --publicly-accessible \
  --vpc-security-group-ids '<SG_ID>'
```

After the instance is available, connect and enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Note the endpoint hostname — you will use it in `DATABASE_URL`.

> **Tip:** for production, set `--publicly-accessible` to `false` and place both RDS and ECS in the same VPC / private subnets. The example above uses public access for simplicity.

### 2. Container registry — ECR

```bash
aws ecr create-repository --repository-name forest

aws ecr get-login-password --region <REGION> \
  | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

docker build -t forest .
docker tag forest:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/forest:latest
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/forest:latest
```

### 3. Compute — ECS Fargate

Create a task definition (`forest-task.json`):

```json
{
  "family": "forest",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "forest",
      "image": "<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/forest:latest",
      "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
      "environment": [
        { "name": "DATABASE_URL", "value": "postgresql+asyncpg://forest:<DB_PASSWORD>@<RDS_HOST>:5432/forest" },
        { "name": "SLACK_BOT_TOKEN", "value": "xoxb-..." },
        { "name": "SLACK_SIGNING_SECRET", "value": "..." },
        { "name": "OPENROUTER_API_KEY", "value": "..." },
        { "name": "CHAT_MODEL_ID", "value": "..." },
        { "name": "EMBEDDING_MODEL_ID", "value": "..." }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/forest",
          "awslogs-region": "<REGION>",
          "awslogs-stream-prefix": "forest"
        }
      }
    }
  ]
}
```

> **Production note:** use AWS Secrets Manager or SSM Parameter Store instead of plaintext `environment` entries. Reference them via `secrets` in the task definition.

Register and run:

```bash
aws ecs register-task-definition --cli-input-json file://forest-task.json

aws ecs create-cluster --cluster-name forest

aws ecs create-service \
  --cluster forest \
  --service-name forest \
  --task-definition forest \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_ID>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}"
```

### 4. Public HTTPS — ALB

Attach an Application Load Balancer to the ECS service so Slack can reach the container over HTTPS:

1. Create an ALB in the same VPC/subnets.
2. Create a target group (port 8000, health check path `/healthz`).
3. Add an HTTPS listener (port 443) with an ACM certificate for your domain.
4. Register the ECS service's target group.

After DNS propagates, verify:

```bash
curl https://forest.example.com/healthz
```

### 5. Slack wiring

Set your Slack app's **Event Subscriptions → Request URL** to:

```
https://forest.example.com/slack/events
```

### AWS — App Runner alternative

If you want to skip ECS/ALB setup, **AWS App Runner** deploys from ECR with built-in HTTPS and auto-scaling:

```bash
aws apprunner create-service \
  --service-name forest \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/forest:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "DATABASE_URL": "postgresql+asyncpg://forest:<DB_PASSWORD>@<RDS_HOST>:5432/forest",
          "SLACK_BOT_TOKEN": "xoxb-...",
          "SLACK_SIGNING_SECRET": "...",
          "OPENROUTER_API_KEY": "...",
          "CHAT_MODEL_ID": "...",
          "EMBEDDING_MODEL_ID": "..."
        }
      }
    },
    "AuthenticationConfiguration": {
      "AccessRoleArn": "<ECR_ACCESS_ROLE_ARN>"
    }
  }' \
  --health-check-configuration 'Protocol=HTTP,Path=/healthz,Interval=10,Timeout=5'
```

App Runner gives you an `https://<id>.<region>.awsapprunner.com` URL immediately. Use that as your Slack Request URL. For a custom domain, add one via the App Runner console or CLI.

> **Note:** App Runner can reach RDS only if both are in the same VPC. Associate a VPC connector with the App Runner service and ensure security groups allow traffic on port 5432.

---

## GCP

### 1. Database — Cloud SQL for PostgreSQL with pgvector

Cloud SQL for PostgreSQL 15+ supports pgvector via the `google_ml_integration` or by enabling the extension directly.

```bash
gcloud sql instances create forest-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=<REGION> \
  --root-password='<DB_PASSWORD>' \
  --database-flags=cloudsql.enable_pgvector=on

gcloud sql databases create forest --instance=forest-db

gcloud sql users create forest \
  --instance=forest-db \
  --password='<DB_PASSWORD>'
```

Connect and enable the extension:

```bash
gcloud sql connect forest-db --user=forest
```

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Note the instance connection name (`<PROJECT>:<REGION>:forest-db`) — Cloud Run uses it for a secure connection via the Cloud SQL Auth Proxy sidecar.

### 2. Container registry — Artifact Registry

```bash
gcloud artifacts repositories create forest \
  --repository-format=docker \
  --location=<REGION>

gcloud auth configure-docker <REGION>-docker.pkg.dev

docker build -t forest .
docker tag forest:latest <REGION>-docker.pkg.dev/<PROJECT>/forest/forest:latest
docker push <REGION>-docker.pkg.dev/<PROJECT>/forest/forest:latest
```

### 3. Compute — Cloud Run

Cloud Run gives you a managed, auto-scaling HTTPS endpoint.

```bash
gcloud run deploy forest \
  --image <REGION>-docker.pkg.dev/<PROJECT>/forest/forest:latest \
  --region <REGION> \
  --platform managed \
  --port 8000 \
  --allow-unauthenticated \
  --add-cloudsql-instances <PROJECT>:<REGION>:forest-db \
  --set-env-vars "\
DATABASE_URL=postgresql+asyncpg://forest:<DB_PASSWORD>@/forest?host=/cloudsql/<PROJECT>:<REGION>:forest-db,\
SLACK_BOT_TOKEN=xoxb-...,\
SLACK_SIGNING_SECRET=...,\
OPENROUTER_API_KEY=...,\
CHAT_MODEL_ID=...,\
EMBEDDING_MODEL_ID=..."
```

> **Production note:** store secrets in **Secret Manager** and reference them with `--set-secrets` instead of `--set-env-vars`.

Cloud Run outputs a URL like `https://forest-<hash>-<region>.a.run.app`. Verify:

```bash
curl https://forest-<hash>-<region>.a.run.app/healthz
```

### 4. Slack wiring

Set your Slack app's **Event Subscriptions → Request URL** to:

```
https://forest-<hash>-<region>.a.run.app/slack/events
```

For a custom domain, map one via `gcloud run domain-mappings create`.

### Cloud Run configuration notes

| Setting | Recommended value | Why |
|---------|-------------------|-----|
| Min instances | `1` | Avoids cold-start delays for Slack's 3-second response window. |
| Max instances | `1-2` | `forest` is a single-process app; more than one instance is fine but offers diminishing returns. |
| Memory | `512 Mi` | Sufficient for typical workloads; increase if onboarding large channel histories. |
| CPU | `1` | Adequate for webhook-driven traffic. |
| Request timeout | `300s` | Onboarding scans can take a while. |

Set these via flags:

```bash
gcloud run services update forest \
  --min-instances=1 \
  --max-instances=2 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300
```

---

## Migrations

The Docker entrypoint runs `alembic upgrade head` on every container start, so schema migrations apply automatically when you deploy a new image. No separate migration step is needed.

If you need to run migrations manually against a remote database:

```bash
export DATABASE_URL="postgresql+asyncpg://forest:<DB_PASSWORD>@<HOST>:5432/forest"
poetry run alembic upgrade head
```

For Cloud SQL, you can proxy locally first:

```bash
cloud-sql-proxy <PROJECT>:<REGION>:forest-db &
export DATABASE_URL="postgresql+asyncpg://forest:<DB_PASSWORD>@127.0.0.1:5432/forest"
poetry run alembic upgrade head
```

---

## Security checklist

- [ ] Database is **not** publicly accessible in production (use VPC peering / private networking).
- [ ] Secrets (`SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `OPENROUTER_API_KEY`, `DATABASE_URL`) are stored in a secrets manager, not in plaintext env vars.
- [ ] HTTPS is terminated at the load balancer (ALB) or provided by the platform (Cloud Run, App Runner).
- [ ] Database credentials use a strong, unique password.
- [ ] Security groups / firewall rules restrict Postgres access to the application only.
- [ ] Container images are rebuilt and redeployed for security patches.

---

## Verifying the deployment

After deploying to either provider:

```bash
# Liveness
curl https://<your-host>/healthz
# => {"status":"ok"}

# Readiness (DB reachable)
curl https://<your-host>/ready
# => {"status":"ready"}
```

Then in Slack, invite the bot to a channel and run `@forest help` to confirm end-to-end connectivity.
