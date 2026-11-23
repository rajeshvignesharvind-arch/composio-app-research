# App research agent: agent-toolkit buildability for 100 apps

An agent that researches 100 apps (auth, self-serve vs gated, API surface, MCP, buildability) with a **verbatim evidence quote for every answer**, checks its own work in a second pass with a different model, and scores itself against a hand-checked gold set.

Live case study: see the deployed `site/` (link in the submission). Raw data: `site/results.json`, `site/results.csv`, `site/schema.json`, `site/llms.txt`.

## Quick start
```bash
pip install -r requirements.txt
cp .env.example .env            # GROQ_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY (all free tiers)
python -m agent.run --app "Pumble"   # one app end to end (~1 min)
python -m agent.run --all            # all 100, resumable (per-app results in data/pass1/)
python -m agent.run --all --pass2    # critic + re-research loop (data/pass2/)
python -m agent.merge && python -m agent.composio_check && python -m agent.score data/pass1.jsonl
python -m agent.build_site           # rebuild site/index.html
```

## Pipeline (agent/)
| stage | file | what it does |
|---|---|---|
| seed | `data/apps.yaml` | 100 apps, category, hint URL (pins the company identity) |
| discover | `fetch.py` | Tavily: 3 searches restricted to the vendor domain + 1 open MCP search |
| fetch | `fetch.py` | Firecrawl (JS-rendered markdown), Jina Reader fallback, all cached to `data/cache/` |
| extract | `extract.py` | Groq LLM returns strict JSON; every field needs `{value, source, quote}` |
| ground | `extract.py` | **code** checks each quote exists on the cited page (exact, else 4-gram fuzzy); otherwise the value becomes `unknown` |
| derive | `schema.py` | buildability + main blocker come from a written rule, not the model |
| critic | `critic.py` | other model than the extractor: live re-fetch of cited pages, batched judge, adversarial search |
| re-research | `run.py` | only flagged fields are re-extracted; unresolved ones are marked `needs_human` |
| score | `score.py` | per-field accuracy against `data/gold.json` |
| analyse / render | `analyze.py`, `build_site.py` | every number on the page is computed from the final records |

## Honest limits
* Both models run on Groq's free tier (extractor and critic alternate between `gpt-oss-20b` and `qwen3.8-27b`; the critic is always the *other* model). Independence is weaker than using a different vendor; the gold set measures real accuracy.
* Free-tier caps (8k tokens/min, 200k/day per model) set the run speed.
* Composio presence is checked via the public toolkit docs pages (200 vs 404), a slug heuristic.
* Gold set n=20, so accuracy has about ±10 pt margin.
* Keys live in `.env` (never committed).
