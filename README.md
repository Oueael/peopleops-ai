# PeopleOps AI Assistant

A Slack-based AI assistant that answers employee policy questions using a synthetic company handbook.

This portfolio project demonstrates retrieval-augmented generation (RAG), role-based document access, citation validation, sensitive-topic escalation, audit logging, and user feedback.

## Project Overview

Employees often need quick answers about company policies. This project explores how an AI assistant can answer those questions while limiting responses to approved handbook content.

The assistant retrieves relevant handbook sections, sends them to an LLM, and returns an answer with citations. If the available information doesn't support an answer, the assistant can abstain rather than inventing a policy.

All handbook content is synthetic. This is a portfolio prototype, not a production HR system.

## Architecture

```text
                         Slack
                           |
                           v
                       Slack Bot
                           |
                           v
                     Receive Mention
                           |
                           v
                    Background Worker
                           |
                           v
                  Sensitive Topic Check
                           |
                 +---------+---------+
                 |                   |
              Escalate            Continue
                 |                   |
                 v                   v
           Safe DM Reply       Identify User Role
                 |                   |
                 v                   v
          Notify Private HR   Authorized Retrieval
              Channel                |
                                     v
                                 PostgreSQL
                                  pgvector
                                     |
                                     v
                                   Gemini
                                     |
                                     v
                             Citation Validation
                                     |
                                     v
                             Add Readable Sources
                                     |
                                     v
                              Private Slack DM
                                     |
                                     v
                               Feedback Buttons
                                     |
                                     v
                                Audit Logging
```

## Technology Stack

- Python
- Slack Bolt and Socket Mode
- PostgreSQL and pgvector
- Sentence Transformers (`all-MiniLM-L6-v2`)
- Google Gemini (`gemini-3.5-flash-lite`)
- Psycopg
- SQL and Python-based evaluation scripts
- Docker Compose

FastAPI is included as a separate health-check application, not as the main Slack request handler.

## Key Features

### Retrieval-Augmented Generation

Handbook documents are processed into smaller text chunks, converted into embeddings, and stored in PostgreSQL.

When an employee asks a question:

1. The question is converted into an embedding.
2. Relevant handbook chunks are retrieved using vector similarity.
3. Retrieval is filtered by the user's role and region.
4. Retrieved content is included in the LLM prompt.
5. Gemini generates an answer using the supplied sources.
6. Citation validation checks that referenced source numbers exist.
7. Readable document names and section headings are appended to the answer.

### Role-Based Access Control

Retrieval is filtered according to the user's assigned role.

Current roles:

- Employee
- Manager
- HR

Employees can retrieve general employee content. Managers can also retrieve manager-only guidance. HR has the broadest configured access.

Roles are assigned using trusted Slack member IDs configured in environment variables.

Access restrictions are enforced during retrieval rather than relying on the LLM to follow instructions.

### Private Slack Responses

Employees mention the assistant in a Slack channel. The bot acknowledges the request privately in that channel and sends the actual answer through a direct message.

This prevents manager-only answers from being exposed in public channels.

### Sensitive-Topic Escalation

A keyword-based rule system checks for sensitive workplace topics, including harassment, discrimination, retaliation, and workplace safety concerns.

When a matching topic is detected:

- The assistant returns a human-handoff response to the employee.
- A notification is sent to a private People Operations Slack channel.
- The notification identifies the reporting employee and detected category without copying the original report.

This is an initial rule-based implementation, not a complete workplace incident classifier or emergency response system.

### Citation Validation and Abstention

The assistant checks whether citations refer to documents returned by retrieval.

Valid citations are accompanied by readable document names and section headings.

The assistant also recognizes explicit abstentions when the available handbook information doesn't answer a question.

The citation validator checks reference existence, not whether a cited passage semantically supports every claim.

### Audit Logging and Feedback

The project records audit metadata such as:

- Slack user and channel identifiers
- Assigned role and region
- Interaction outcome
- Retrieved source metadata
- Citation-validation status
- Response latency

Question content is represented by a SHA-256 fingerprint and length rather than being stored directly in the audit record.

The fingerprint does not make the associated user or channel identifiers anonymous.

Slack users can rate ordinary answers using Helpful and Not helpful buttons. Feedback is stored for later review.

## Evaluation

The project includes a small evaluation set covering answerable questions, unsupported questions, role permissions, escalation, policy conflicts, and adversarial access-control checks.

### Latest Results

| Evaluation | Passed | Failed | Deferred |
|---|---:|---:|---:|
| Retrieval and policy | 10 | 0 | 2 |
| Answer generation | 8 | 0 | 0 |

The two deferred retrieval cases are tested by the generation evaluation, where both passed.

Run the evaluations from the project root:

```powershell
python -m evals.run_evals
python -m evals.run_generation_evals
```

Results are saved under `evals/`.

The evaluation suite includes local checks and generation-based checks. Some cases overlap, and the current tests do not establish comprehensive answer correctness or security.

These results represent a small prototype test set, not a comprehensive security or quality assessment.

## Running Locally

### Requirements

- Python
- Docker Desktop
- PostgreSQL with pgvector
- Google Gemini API key
- Slack app configured for Socket Mode

### Environment Configuration

Create a `.env` file in the project root.

Configure the following variables:

```env
DATABASE_URL=postgresql://peopleops:YOUR_PASSWORD@localhost:5432/peopleops

GEMINI_API_KEY=your_gemini_api_key

SLACK_BOT_TOKEN=your_slack_bot_token
SLACK_APP_TOKEN=your_slack_app_token

SLACK_MANAGER_IDS=
SLACK_HR_IDS=

SLACK_HR_CHANNEL_ID=your_private_hr_channel_id
```

Use your actual local database credentials and Slack configuration. Never commit `.env` or API credentials to GitHub.

### Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install project dependencies:

```powershell
pip install -r requirements.txt
```

Start the PostgreSQL container:

```powershell
docker compose up -d
```

Initialize the database:

```powershell
python -m rag.database
```

Process handbook documents into chunks:

```powershell
python -m rag.ingest
```

Generate embeddings:

```powershell
python -m rag.embed
```

Store chunks and embeddings in PostgreSQL:

```powershell
python -m rag.store
```

Start the Slack bot:

```powershell
python -m app.slack_bot
```

## Security Considerations

- Synthetic handbook data is used for development.
- Role and region restrictions are applied during retrieval.
- Sensitive-topic checks run before LLM generation.
- Sensitive reports generate private HR notifications.
- Answers are delivered through direct messages.
- API credentials are kept in environment variables.
- Audit records avoid storing raw question text.
- The LLM is instructed to answer using retrieved handbook sources.

This prototype has not undergone a formal security review. Keyword-based escalation can miss sensitive messages or produce false positives. Citation validation does not guarantee factual correctness.

## Limitations

- The evaluation set is small.
- Citation validation checks reference existence, not semantic support.
- Escalation uses keyword rules rather than a comprehensive classifier.
- HR notifications are basic Slack notifications, not a case-management workflow.
- Retrieval thresholds can occasionally cause relevant questions to be rejected.
- Audit logging does not provide a complete answer-quality or cost analysis.

## Project Structure

```text
peopleops-ai/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── slack_bot.py
│   └── user_roles.py
├── data/
│   ├── handbook/
│   └── chunks.json
├── docs/
│   └── decision-log.md
├── evals/
│   ├── __init__.py
│   ├── cases.json
│   ├── latest_generation_results.json
│   ├── latest_results.json
│   ├── run_evals.py
│   └── run_generation_evals.py
├── policy/
│   ├── __init__.py
│   └── escalation.py
├── rag/
│   ├── __init__.py
│   ├── audit.py
│   ├── citations.py
│   ├── database.py
│   ├── database_search.py
│   ├── embed.py
│   ├── feedback.py
│   ├── generate.py
│   ├── ingest.py
│   ├── prompt.py
│   ├── search.py
│   └── store.py
├── tests/
│   └── __init__.py
├── tools/
│   └── __init__.py
├── docker-compose.yml
├── requirements.txt
├── README.md
└── .gitignore
```

## Demo

The demo uses a test Slack workspace and synthetic handbook content.

1. Ask an employee policy question and show the private answer with readable citations.
2. Demonstrate that an employee cannot retrieve manager-only guidance.
3. Ask a manager-specific question and show that the manager can retrieve the restricted information.
4. Submit a synthetic harassment-related message and show the private employee response and HR notification.
5. Ask an unsupported question and demonstrate abstention.
6. Show the evaluation results and discuss the known limitations.

## Purpose

This project demonstrates how to build an AI-assisted internal knowledge system with attention to retrieval quality, access control, safety, and evaluation.

It is intended as a learning and portfolio project, with clear distinctions between implemented functionality and known limitations.
