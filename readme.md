# reflexRAG 

> Developers don't struggle to write code. They struggle to understand code they didn't write.

reflexRAG is a self-healing RAG pipeline for GitHub repositories. Paste any public repo URL and ask questions about its issues, PRs, discussions, and decision history — without hallucinating.

---

## What makes this different

Every engineer from interns to staff engineers, repeatedly pays the "understanding tax" when they join a new codebase. Most "chat with repo" tools index source code. reflexRAG indexes **human communication** — issues, PR comments, discussions, rejected alternatives — and adds a critic layer that flags when an answer is sourced from a closed issue, a mismatched version, or contradictory chunks.

**The Join is the Moat** — ReflexRAG uses the repository file path as a join key between source code and GitHub discussions. After retrieving a relevant code chunk, it fetches commits and pull requests that modified the same file, allowing responses to combine implementation details with the engineering decisions behind them.

**Two features nobody else has built:**

- **Decision archaeology** — not just *what* was decided, but *why*. What alternatives were rejected, by whom, and what the reasoning was. Built by extracting structured decision nodes from every PR during ingestion.
- **Contributor map** — file ownership scores, authority maps, and *real* difficulty ratings on issues (computed from commit history and PR review patterns, not just labels).

---

## Contributor Mode (in progress)

A guided mode for early-to-mid open-source contributors, built directly into the chat interface of any ingested repo. Where the default **Explore** mode answers *"how does this work,"* **Contribute** mode answers *"how do I actually contribute here"* — grounded in the repo's full history, which generic assistants can't see.

The chat header carries a segmented **Explore / Contribute** toggle. Contribute mode replaces the empty-state prompts with six action tiles, color-grouped by intent so six options read as three clusters rather than a wall of choices:

**Finding & understanding** *(rust)*
- **Find issues for me** — open, currently-available issues matched to your skills
- **Understand an issue** — paste any issue URL for a plain-language breakdown
- **Safe first change** — the lowest-risk place to make a first PR

**How the repo works** *(blue)*
- **How contributions work here** — this repo's real review culture, PR-size norms, and response expectations, inferred from past PRs rather than just `CONTRIBUTING.md`
- **Show me a past PR like mine** — a solved PR surfaced as a working template

**People** *(sand)*
- **Who should I ask** — the right maintainer for an area, from the contributor map

**Skill matching with decomposition.** Skills are auto-inferred from your GitHub profile and editable. Instead of a binary can-you-do-this, each suggested issue is *decomposed* by skill — e.g. *"70% Python/tokenization (you have this), 30% CUDA profiling (you don't)"* — so you can judge fit honestly, including exactly where you'd need help.

**Issue orientation.** Paste an unfamiliar issue and get an *issue map*: a plain-language explanation first, then the skill-fit breakdown, then the files it likely touches, similar past PRs, and who to ask. This replaces the hours of code "archaeology" it usually takes to work out where an issue even lives. In Contribute mode the left panel swaps from conversations to your skills and the issues you're tracking.

---

## Inkling — the guide

Inkling is reflexRAG's octopus guide, and the octopus *is* the architecture: eight arms reaching into issues, PRs, commits, and code, one brain synthesizing them (rust arms for the *why*, blue for the *what*).

- **Explore mode** — a curious companion offering ambient, low-key guidance as you move around a repo.
- **Contribute mode** — a journey guide. Inkling tracks your progress through a quiet checklist (understood the issue → found the files → checked who to ask → seen a similar PR) and offers a contextual nudge when something useful is one step away.

Inkling only speaks when there's something worth saying, appears at most occasionally, and is always dismissable with a small ×. The restraint is the point — a guide you can ignore, not an assistant you have to manage.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TypeScript + Tailwind |
| Backend | FastAPI + Python 3.11 |
| RAG pipeline | LangGraph |
| LLM | Gemini 2.0 Flash (free tier) |
| Embeddings | `BAAI/bge-large-en-v1.5` (local, no API cost) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local) |
| Semantic cache | GPTCache |
| Database + Auth + Vector | Supabase (pgvector) |
| Task queue | Celery + Redis (Upstash) |
| GitHub data | PyGithub |

**Zero paid AI APIs** — embeddings and reranking run locally. Only the Gemini API key is required.

---

## Project structure

```
reflexRAG/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic settings from .env
│   │   │   ├── supabase.py            # Supabase client singleton
│   │   │   ├── security.py            # JWT validation, GitHub OAuth
│   │   │   └── dependencies.py        # FastAPI dependency injection
│   │   ├── models/
│   │   │   ├── chunk.py               # Chunk dataclass + ChunkResult
│   │   │   ├── repo.py                # Repo, IngestionJob pydantic models
│   │   │   ├── message.py             # Message, Citation, StalenessFlag
│   │   │   ├── decision.py            # DecisionNode dataclass
│   │   │   ├── contributor.py         # Contributor, FileArea, RankedIssue
│   │   │   └── graph_state.py         # LangGraph TypedDict state
│   │   ├── api/routes/
│   │   │   ├── auth.py                # GET /auth/github, /auth/callback, /auth/me
│   │   │   ├── repos.py               # POST /repos, GET /repos, DELETE /repos/{id}
│   │   │   ├── chat.py                # POST /sessions, POST /sessions/{id}/chat (SSE)
│   │   │   ├── decisions.py           # GET /repos/{id}/decisions
│   │   │   ├── contributors.py        # GET /repos/{id}/contributors, /start-here
│   │   │   ├── webhooks.py            # POST /webhooks/github
│   │   │   └── billing.py             # GET /billing/plan (Stripe-ready stub)
│   │   ├── services/
│   │   │   ├── ingestion/
│   │   │   │   ├── github_fetcher.py  # PyGithub wrapper, rate limit handling
│   │   │   │   ├── chunker.py         # Text splitting + metadata attachment
│   │   │   │   ├── embedding_service.py # bge-large-en-v1.5 local inference
│   │   │   │   ├── vector_store.py    # pgvector upsert + similarity search
│   │   │   │   └── orchestrator.py    # Full ingestion pipeline coordinator
│   │   │   ├── rag/
│   │   │   │   ├── graph.py           # LangGraph graph definition + compilation
│   │   │   │   ├── nodes.py           # retrieve, generate, finalize node functions
│   │   │   │   ├── critic.py          # Staleness, version, contradiction checks
│   │   │   │   ├── reranker.py        # cross-encoder reranking (50 → 8 chunks)
│   │   │   │   ├── cache.py           # GPTCache semantic cache wrapper
│   │   │   │   └── prompts.py         # RAG prompt templates
│   │   │   └── features/
│   │   │       ├── decision_extractor.py  # Gemini Flash structured JSON extraction
│   │   │       ├── contributor_builder.py # Ownership + authority scoring
│   │   │       └── file_area_builder.py   # Co-change graph from commit history
│   │   └── utils/
│   │       ├── hashing.py             # sha256 content hash for dedup
│   │       ├── github_parser.py       # URL parsing, version tag extraction
│   │       ├── version_extractor.py   # Regex version extraction from text
│   │       └── sse.py                 # SSE response helpers
│   ├── celery_worker/
│   │   ├── celery_app.py              # Celery app + Redis broker config
│   │   └── tasks.py                   # ingest_repo task, differential_ingest task
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_chunker.py        # Chunk splitting correctness
│   │   │   ├── test_critic.py         # Staleness flag logic
│   │   │   └── test_embedding.py      # Embedding shape + similarity sanity
│   │   └── integration/
│   │       ├── test_ingestion.py      # Full ingestion pipeline (mocked GitHub API)
│   │       └── test_rag_graph.py      # LangGraph end-to-end with fixture chunks
│   ├── .env.example                   # All required env vars documented
│   ├── requirements.txt               # Pinned dependencies
│   ├── Dockerfile                     # Builds backend + pre-downloads models
│   ├── pytest.ini                     # Test config
│   └── litellm_config.yaml            # Model routing rules
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LandingPage.tsx        # Hero + repo URL input
│   │   │   ├── DashboardPage.tsx      # User's ingested repos
│   │   │   ├── ChatPage.tsx           # Main chat interface
│   │   │   ├── ContributorMapPage.tsx # File ownership + issue rankings
│   │   │   └── DecisionsPage.tsx      # Decision archaeology browser
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx     # Message list + input
│   │   │   │   ├── MessageBubble.tsx  # Single message with citations
│   │   │   │   ├── CitationCard.tsx   # Source card (type, status, url, excerpt)
│   │   │   │   ├── StalenessWarning.tsx # Inline staleness flag badge
│   │   │   │   └── StreamingMessage.tsx # Token-by-token streaming render
│   │   │   ├── repo/
│   │   │   │   ├── RepoInput.tsx      # GitHub URL input + validation
│   │   │   │   ├── RepoCard.tsx       # Repo summary card in dashboard
│   │   │   │   └── IngestionProgress.tsx # Live progress bar via polling
│   │   │   ├── contributor/
│   │   │   │   ├── ContributorMap.tsx # Contributor list + scores
│   │   │   │   ├── FileAreaTree.tsx   # File area ownership tree
│   │   │   │   └── IssueRanking.tsx   # Ranked good-first-issues
│   │   │   └── shared/
│   │   │       ├── Navbar.tsx
│   │   │       ├── Sidebar.tsx
│   │   │       ├── Badge.tsx          # Status badges (open/closed/merged)
│   │   │       └── LoadingSpinner.tsx
│   │   ├── hooks/
│   │   │   ├── useChat.ts             # Chat session management
│   │   │   ├── useRepo.ts             # Repo CRUD + ingestion polling
│   │   │   ├── useSSE.ts              # SSE stream connection hook
│   │   │   └── useAuth.ts             # GitHub OAuth flow
│   │   ├── store/
│   │   │   ├── chatStore.ts           # Zustand: messages, sessions
│   │   │   ├── repoStore.ts           # Zustand: repos, ingestion status
│   │   │   └── authStore.ts           # Zustand: user, token
│   │   ├── types/index.ts             # All TypeScript interfaces
│   │   └── utils/
│   │       ├── api.ts                 # Typed fetch wrapper
│   │       └── sse.ts                 # SSE stream reader + event parser
│   ├── .env.example
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── package.json
│
├── docker-compose.yml                 # Backend + Celery + Redis for local dev
├── .gitignore
└── README.md
```

---

## Local development setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project (free tier)
- A Gemini API key (free from [Google AI Studio](https://aistudio.google.com))
- A GitHub OAuth App

### 1. Clone

```bash
git clone https://github.com/your-username/reflexRAG.git
cd reflexRAG
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your keys

# Run the API
uvicorn app.main:app --reload --port 8000
```

### 3. Celery worker (separate terminal)

```bash
cd backend
source venv/bin/activate
celery -A celery_worker.celery_app worker --loglevel=info
```

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local
npm run dev
```

App runs at `http://localhost:5173`

### 5. Docker (alternative — runs everything together)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env
docker-compose up --build
```

---

## Supabase setup

Run these SQL statements in your Supabase SQL editor to create the schema:

```sql
-- Enable pgvector
create extension if not exists vector;

-- Users
create table users (
  id uuid primary key default gen_random_uuid(),
  github_id text unique not null,
  username text not null,
  email text,
  avatar_url text,
  plan text default 'free' check (plan in ('free','pro')),
  repos_used int default 0,
  created_at timestamptz default now()
);

-- Repos (shared across users)
create table repos (
  id uuid primary key default gen_random_uuid(),
  github_url text unique not null,
  owner text not null,
  name text not null,
  status text default 'queued',
  chunk_count int default 0,
  decision_count int default 0,
  last_ingested_at timestamptz,
  latest_commit_sha text
);

-- User <-> Repo join table
create table user_repos (
  user_id uuid references users(id) on delete cascade,
  repo_id uuid references repos(id) on delete cascade,
  linked_at timestamptz default now(),
  primary key (user_id, repo_id)
);

-- Chunks with pgvector
create table chunks (
  id uuid primary key default gen_random_uuid(),
  repo_id uuid references repos(id) on delete cascade,
  content text not null,
  embedding vector(1024),          -- bge-large-en-v1.5 outputs 1024 dims
  source_type text not null,
  source_id text not null,
  status text default 'none',
  version_tag text,
  content_hash text unique not null,
  source_created_at timestamptz
);

-- Vector similarity index
create index on chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Chat
create table chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  repo_id uuid references repos(id) on delete cascade,
  title text,
  created_at timestamptz default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references chat_sessions(id) on delete cascade,
  role text not null check (role in ('user','assistant')),
  content text not null,
  citations jsonb default '[]',
  staleness_flags jsonb default '[]',
  model_used text,
  tokens_used int,
  created_at timestamptz default now()
);

-- Decision nodes
create table decision_nodes (
  id uuid primary key default gen_random_uuid(),
  repo_id uuid references repos(id) on delete cascade,
  decision text not null,
  alternatives_rejected jsonb default '[]',
  reasoning text,
  source_chunk_ids jsonb default '[]',
  embedding vector(1024),
  created_at timestamptz default now()
);

-- Contributor map
create table contributors (
  id uuid primary key default gen_random_uuid(),
  repo_id uuid references repos(id) on delete cascade,
  github_username text not null,
  ownership_score float default 0,
  authority_score float default 0,
  top_areas jsonb default '[]',
  updated_at timestamptz default now()
);

create table file_areas (
  id uuid primary key default gen_random_uuid(),
  repo_id uuid references repos(id) on delete cascade,
  area_path text not null,
  complexity_score float default 0,
  co_changes_with jsonb default '[]',
  updated_at timestamptz default now()
);

-- Row Level Security
alter table chat_sessions enable row level security;
alter table messages enable row level security;
alter table user_repos enable row level security;

create policy "users see own sessions"
  on chat_sessions for all
  using (auth.uid()::text = user_id::text);

create policy "users see own messages"
  on messages for all
  using (
    session_id in (
      select id from chat_sessions where user_id::text = auth.uid()::text
    )
  );
```

---

## Environment variables

See `backend/.env.example` for the full list. The minimum required to run:

```
GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
GEMINI_API_KEY
REDIS_URL
SECRET_KEY
```

---

## Running tests

```bash
cd backend
source venv/bin/activate
pytest
```

---

## How it works

1. **Ingest** — paste a GitHub URL. The Celery worker calls the GitHub API, chunks every issue/PR/comment, embeds them locally with `bge-large-en-v1.5`, and upserts to pgvector. If another user already ingested the same repo, their chunks are reused (content hash dedup).

2. **Query** — your question is embedded, top-50 chunks are retrieved via cosine similarity, reranked to top-8 by the cross-encoder, and passed to Gemini Flash with a strict citation prompt.

3. **Critic** — before the answer reaches you, the critic checks: is this chunk from a closed issue? Does the version tag mismatch your question? Do any chunks contradict each other? If yes, it re-retrieves with a refined query or surfaces a staleness warning inline.

4. **Stream** — the answer streams token by token over SSE. Citations and staleness flags arrive as structured events after the text, so the UI can render source cards and warning badges.

---

## Roadmap

- [ ] **Contributor Mode** — skill-decomposition issue matching + issue orientation maps (see above; in active development)
- [ ] **Inkling journey guide** — progress checklist + contextual nudges in Contribute mode
- [ ] Private repo support (requires `repo` OAuth scope)
- [ ] GitHub App installation tokens (3× higher rate limit)
- [ ] Stripe billing integration
- [ ] Cross-repo impact analysis
- [ ] VS Code extension

---

## License

MIT