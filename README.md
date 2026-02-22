# 🌍 AI Trip Planner

[![Python](https://skillicons.dev/icons?i=python)](https://www.python.org/)
[![FastAPI](https://skillicons.dev/icons?i=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://skillicons.dev/icons?i=docker)](https://www.docker.com/)
[![AWS](https://skillicons.dev/icons?i=aws)](https://aws.amazon.com/)
[![GitHub Actions](https://skillicons.dev/icons?i=githubactions)](https://github.com/features/actions)

Agentic travel planner with a FastAPI backend, Streamlit frontend, LangGraph orchestration, and optional LangSmith tracing and alerting.

## 🚀 Tech Stack

![Tech Stack](https://skillicons.dev/icons?i=python,fastapi,docker,aws,githubactions&perline=5)

## ✨ What it does

- 💬 Accepts a user prompt for a trip plan.
- 🤖 Uses a LangGraph agent with tools to collect weather, places, and cost info.
- 📋 Returns a structured plan in the UI.
- 🐳 Supports Docker, ECR/ECS/App Runner deployment, and GitHub Actions CI/CD.

## 📁 Project structure

```
AI_Trip_Planner/
	main.py                      # FastAPI backend
	streamlit_app.py             # Streamlit UI
	agent/
		agentic_workflow.py        # LangGraph agent and tool wiring
	tools/                       # Tool definitions (weather, places, cost, FX)
	utils/
		model_loader.py            # LLM loader (Groq/OpenAI)
		langsmith_monitor.py       # LangSmith alerts (log/webhook/smtp)
	config/
		config.yaml                # Model selection
	Dockerfile
	docker-compose.yml
	deploy-aws.sh                # ECR + ECS deploy script
	ecs-task-definition.json     # ECS task template
	apprunner-config.json        # App Runner config
	.github/workflows/deploy.yml # GitHub Actions -> ECR
```

## 🤖 How the agent is built

The agent is defined in [agent/agentic_workflow.py](agent/agentic_workflow.py):

- `GraphBuilder` loads the LLM via [utils/model_loader.py](utils/model_loader.py)
- Tools are registered from:
	- [tools/weather_info_tool.py](tools/weather_info_tool.py)
	- [tools/place_search_tool.py](tools/place_search_tool.py)
	- [tools/expense_calculator_tool.py](tools/expense_calculator_tool.py)
	- [tools/currency_conversion_tool.py](tools/currency_conversion_tool.py)
- The graph flow is:

```mermaid
flowchart TD
	START --> Agent
  Agent -->|tool call| Weather[Weather Tools]
  Agent -->|tool call| Places[Place Search Tools]
  Agent -->|tool call| Calc[Expense Calculator Tools]
  Agent -->|tool call| FX[Currency Converter Tool]
  Weather --> Agent
  Places --> Agent
  Calc --> Agent
  FX --> Agent
  Agent --> END
```

Available tools:
- **Weather**: `get_current_weather`, `get_weather_forecast`
- **Place Search**: `search_attractions`, `search_restaurants`, `search_activities`, `search_transportation`
- **Expense Calculator**: `estimate_total_hotel_cost`, `calculate_total_expense`, `calculate_daily_expense_budget`
- **Currency Converter**: `convert_currency`

`Agent` uses the system prompt from [prompt_library/prompt.py](prompt_library/prompt.py) and binds tools for function calls.

## 💻 Local run (no Docker)

1) Create and activate a virtual environment.
2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Create `.env` (do not commit secrets):

```
GROQ_API_KEY=...
TAVILAY_API_KEY=...
OPENWEATHERMAP_API_KEY=...
EXCHANGE_RATE_API_KEY=...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=AGENTIC-AI-LLMOPS
```

4) Run backend:

```bash
uvicorn main:app --reload --port 8000
```

5) Run frontend:

```bash
streamlit run streamlit_app.py
```

Backend: http://localhost:8000
Frontend: http://localhost:8501

## 🐳 Docker

### Docker Containers

The application runs two containers:

| Container | Service | Port | Purpose |
|-----------|---------|------|---------|
| `backend` | FastAPI | 8000 | REST API that handles agent execution |
| `frontend` | Streamlit | 8501 | User interface for trip planning |

Both containers are built from the same Dockerfile but run different commands via `supervisord`.

### Build and run with Docker Compose

```bash
docker-compose up --build
```

This builds one image and runs two services:
- `backend` on port 8000
- `frontend` on port 8501

### Standalone Docker build

```bash
docker build -t trip-planner:latest .
docker run -p 8000:8000 -p 8501:8501 trip-planner:latest
```

The image uses `supervisord` to run both FastAPI and Streamlit.

### Adding the Agent Graph Image

The agent automatically generates a graph visualization (`my_graph.png`) on each request. To include it in your README or documentation:

1. The graph is saved to the working directory when you run a query
2. Find `my_graph.png` in the project root
3. Add it to your README:

```markdown
![Agent Graph](my_graph.png)
```

Or upload it to your repository and reference it:

```markdown
![Agent Graph](https://raw.githubusercontent.com/username/repo/main/my_graph.png)
```

## ☁️ AWS ECR + ECS (manual)

The script [deploy-aws.sh](deploy-aws.sh) builds and pushes to ECR, then registers an ECS task and creates a service.

1) Update `subnet-xxxxx` and `sg-xxxxx` in [deploy-aws.sh](deploy-aws.sh)
2) Update env vars in [ecs-task-definition.json](ecs-task-definition.json)
3) Run:

```bash
chmod +x deploy-aws.sh
./deploy-aws.sh
```

This creates:
- ECR repository `trip-planner`
- ECS cluster `trip-planner-cluster`
- ECS service `trip-planner-service`

## 🏃 AWS App Runner (optional)

[apprunner-config.json](apprunner-config.json) defines a service that pulls the ECR image and exposes port 8501 (Streamlit). Update the runtime env vars before use.

## 🔄 GitHub Actions (ECR push)

The workflow in [.github/workflows/deploy.yml](.github/workflows/deploy.yml) builds and pushes to ECR on every `main` push.

Required GitHub secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

The workflow tags the image as both `latest` and the commit SHA.

## 🌐 Public availability

When ECS/App Runner is configured with public networking, the service becomes publicly accessible via the AWS-generated URL or load balancer. You must open the correct ports (8000 for backend, 8501 for frontend) and use a public subnet with `assignPublicIp=ENABLED`.

## 📊 Observability (LangSmith)

Tracing is enabled via `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in `.env`. Alerts are handled in [utils/langsmith_monitor.py](utils/langsmith_monitor.py) with three modes:

- `log` (default, easiest)
- `webhook`
- `smtp`

Configure:

```
ALERT_NOTIFY_MODE=log
ALERT_LATENCY_SECONDS=5
ALERT_TOKEN_THRESHOLD=50
```
## Images
<img width="1600" height="699" alt="image" src="https://github.com/user-attachments/assets/67638a20-e842-4031-95df-f3adfb000260" />
<img width="1600" height="809" alt="image" src="https://github.com/user-attachments/assets/a209dc1b-f51f-4c98-acc7-3ae3c1f5bd02" />
<img width="1600" height="882" alt="image" src="https://github.com/user-attachments/assets/2d8311a2-d117-40ad-b0e6-91cbd547da61" />
<img width="1600" height="788" alt="image" src="https://github.com/user-attachments/assets/c90fb2f8-87bf-476a-984b-9bdccedc60c7" />
<img width="1600" height="985" alt="image" src="https://github.com/user-attachments/assets/df1d8963-4b84-4071-93c1-1aa29a159451" />
<img width="1600" height="938" alt="image" src="https://github.com/user-attachments/assets/7e5183ac-151f-48f5-9573-b532a50d864c" />



## 🔒 Security notes

- Never commit `.env` or any API keys.
- Use GitHub secrets or AWS Secrets Manager for production.

## 🛠️ Troubleshooting

- If tools fail, check tool schemas and the LLM function-call output.
- If tracing is missing, verify `LANGCHAIN_API_KEY` and project name.
