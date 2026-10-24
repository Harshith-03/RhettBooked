backend/app/main.py                 FastAPI routes

backend/app/llm.py                  LLM adapter + fallback

backend/app/brief/                  intake.py (text -> EventBrief), questions.py (ask only missing fields)

backend/app/data/                   placeholder_gen.py, loaders.py, osm.py, mbta.py, openalex.py, build_db.py

backend/app/privacy/                scrubber.py, tokenizer.py, vault.py, risk_report.py

backend/app/plan/                   attendance.py, venue_optimizer.py, tech.py, food_water.py,

                                    transport.py, people.py, sponsors.py, budget.py, options.py, plan.py

backend/app/drill/                  twin.py, power.py, network.py, air.py, queues.py, mobility.py,

                                    montecarlo.py, sensitivity.py, verdict.py

backend/app/agent/                  rag.py, explainer.py, tools.py

backend/tests/

config/assumptions.yaml             every ASSUMED parameter with value, range, and source note

data/placeholder/                   generated BU buildings/rooms, parking, sponsors, rate cards

tools/sensor_logger.py

frontend/src/pages/                 Intake.tsx, Plan.tsx, Compare.tsx, Drill.tsx, Trust.tsx, Export.tsx

docs/                               METHODS.md, ETHICS.md, DEVPOST.md, KIRO_USAGE.md