# Taxi sharing — multi-agent based simulation in Mesa

Ludovica De Martino, Claudio Bendinelli — Université Paris-Saclay

## Install and run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
solara run app.py        # live view: grid, sliders, charts
python experiments.py    # experiments of the report (about 1 minute), saved in results/
python checks.py         # checks that the code follows the model (about 10 seconds)
```

## Files

```
taxi_share/messages.py   Message + MessageReceiver (our direct communication)
taxi_share/agents.py     Passenger and Taxi: perceive -> decide -> act
taxi_share/model.py      TaxiModel = environment: grid, list of taxis, delivery of messages, passengers, measures
app.py                   live view
experiments.py           experiments of the report
checks.py                checks: one action per step, seats, longest ride
results/                 tables (tables.txt) and charts of the report
report.pdf               the report
```

## Design levels

| Level | Seats | A taxi that already has passengers takes a new one if... |
|---|---|---|
| 1 | 1 | never (today's taxi) |
| 2 | 2 | its route does not get longer |
| 3 | 2 | every passenger keeps its limits (detour accepted, latest arrival) |
| 4 | `capacity` (4) | same as level 3, with more seats |

The parameter `margin` (0 by default) is the number of extra steps a taxi keeps
for each stop when it plans: a taxi that sends a message does not drive in that
step, so without a margin its arrival times are a bit optimistic (see the report, Section 5.5).
