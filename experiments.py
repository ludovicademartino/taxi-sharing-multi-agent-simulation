"""
Experiments of the report:   python experiments.py   (about 1 minute)

Every setting is run 10 times (seeds 0 to 9). New passengers appear during
300 steps, then the run goes on until every passenger has left the city.
With the same seed every setting gets the same passengers (see model.py),
so we can compare two settings seed by seed.
The tables (mean and standard deviation of the 10 runs) are printed and
saved in results/tables.txt, the charts in results/*.png.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from taxi_share.agents import Taxi
from taxi_share.model import TaxiModel

SEEDS = range(10)
MEASURES = ["Direct km", "Served", "% gave up", "Total km", "km per passenger", "Occupancy", "% shared", "Wait", "Detour", "% late",
            "% accepts failed"]


def run(**params):
    """10 runs of one setting -> one row of results per run"""
    rows = []
    for seed in SEEDS:
        model = TaxiModel(seed=seed, **params)
        model.run_for(300)
        while len(model.passengers()) > 0:   # no new passengers: we wait until everybody has left
            model.step()
        rows.append(dict(model.results(), seed=seed, **params))
    return pd.DataFrame(rows)


def table(data, by, measures, title):
    """mean (standard deviation) of the 10 runs, printed and saved"""
    groups = data.groupby(by)[measures]
    text = groups.mean().round(2).astype(str) + " (" + groups.std().round(2).astype(str) + ")"
    text = f"\n== {title} ==\n" + text.T.to_string() + "\n"
    print(text)
    with open("results/tables.txt", "a") as f:
        f.write(text)


def wins(data, setting, column, better, worse, measure):
    """In how many of the 10 runs is the 'better' setting really better? (same passengers)"""
    a = data[data[column] == better].sort_values("seed")[measure].values
    b = data[data[column] == worse].sort_values("seed")[measure].values
    text = f"{setting}: {column}={better} better than {column}={worse} on '{measure}' in {sum(a < b)}/10 runs\n"
    print(text, end="")
    with open("results/tables.txt", "a") as f:
        f.write(text)


def plot(data, x, measures, name, hue=None):
    """One chart per measure: mean of the 10 runs, the bar is the standard deviation"""
    fig, axes = plt.subplots(1, len(measures), figsize=(3.4 * len(measures), 3))
    for ax, measure in zip(axes, measures):
        sns.lineplot(data=data, x=x, y=measure, hue=hue, marker="o", errorbar="sd",
                     err_style="bars", ax=ax, palette="Set1" if hue else None)
        ax.set_title(measure)
        ax.set_xticks(sorted(data[x].unique()))   # only the values we really tested
    fig.tight_layout()
    fig.savefig(f"results/{name}.png", dpi=120)
    plt.close(fig)


def main():
    os.makedirs("results", exist_ok=True)
    open("results/tables.txt", "w").close()

    # 1. the four design levels, low and high demand (12 taxis)
    levels = pd.concat([run(level=lv, demand=d) for d in [0.3, 0.8] for lv in [1, 2, 3, 4]])
    table(levels, ["demand", "level"], MEASURES, "1. Levels (12 taxis)")
    high = levels[levels.demand == 0.8]
    for measure in ["% gave up", "km per passenger"]:
        wins(high, "high demand", "level", 2, 1, measure)
        wins(high, "high demand", "level", 3, 2, measure)
        wins(high, "high demand", "level", 4, 3, measure)
        wins(high, "high demand", "level", 3, 4, measure)   # the other way: is level 4 worse?
    plot(levels, "level", ["% gave up", "km per passenger", "Wait", "Detour"], "levels", hue="demand")

    # 2. size of the fleet, levels 1 and 4 (high demand)
    fleet = pd.concat([run(level=lv, n_taxis=n) for lv in [1, 4] for n in [8, 10, 12, 14, 16, 18]])
    table(fleet, ["level", "n_taxis"], ["Served", "% gave up", "Total km", "km per passenger"], "2. Fleet (high demand)")
    plot(fleet, "n_taxis", ["% gave up", "Total km", "km per passenger"], "fleet", hue="level")

    # 3. detour accepted by the passengers, level 4 (high demand)
    detour = pd.concat([run(level=4, max_detour=d) for d in [0, 1, 2, 3, 4, 6, 8]])
    table(detour, "max_detour", ["% gave up", "km per passenger", "Occupancy", "% shared", "Wait", "Detour"],
          "3. Detour accepted (level 4, high demand)")
    plot(detour, "max_detour", ["% gave up", "km per passenger", "Wait", "Detour"], "detour")

    # 4. number of seats, for a small and a large detour (level 4, high demand)
    seats = pd.concat([run(level=4, capacity=c, max_detour=d) for d in [3, 8] for c in [2, 3, 4, 6]])
    table(seats, ["max_detour", "capacity"], ["% gave up", "km per passenger", "Occupancy", "Detour"],
          "4. Seats x detour (level 4, high demand)")
    plot(seats, "capacity", ["% gave up", "km per passenger", "Occupancy"], "seats", hue="max_detour")

    # 5. patience of the passengers (max_wait), levels 1 and 4 (high demand)
    wait = pd.concat([run(level=lv, max_wait=w) for lv in [1, 4] for w in [5, 10, 20, 30]])
    table(wait, ["level", "max_wait"], ["% gave up", "Wait", "km per passenger"], "5. Patience (high demand)")
    for w in [5, 10, 20, 30]:
        wins(wait[wait.max_wait == w], f"max_wait={w}", "level", 4, 1, "% gave up")
        wins(wait[wait.max_wait == w], f"max_wait={w}", "level", 4, 1, "km per passenger")
    plot(wait, "max_wait", ["% gave up", "Wait", "km per passenger"], "max_wait", hue="level")

    # 6. a picture of the city after 60 steps (level 4, high demand), same colours as the live view
    model = TaxiModel(seed=0)
    model.run_for(60)
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    for agent in model.agents:
        if agent.cell is None:
            continue                         # a passenger in a taxi is not drawn
        x, y = agent.cell.coordinate
        if isinstance(agent, Taxi):
            ax.scatter(x, y, marker="s", s=90, zorder=2,
                       color=["tab:gray", "tab:green", "tab:red"][min(len(agent.on_board), 2)])
        else:
            ax.scatter(x, y, marker="o", s=25, zorder=1,
                       color="tab:cyan" if agent.state == "booked" else "tab:blue")
    ax.set_xlim(-1, 20)
    ax.set_ylim(-1, 20)
    ax.set_title("The city after 60 steps")
    fig.tight_layout()
    fig.savefig("results/grid.png", dpi=120)
    plt.close(fig)

    # 7. a margin in the plan of the taxis (high demand)
    # A taxi plans 1 step per km and 1 step per stop, but every message it sends
    # takes a step in which it does not drive. Here the taxi keeps 0, 1 or 2 more
    # steps for each stop of its route, to see if it can keep its promises.
    margin = pd.concat([run(level=lv, margin=m) for lv in [1, 3, 4] for m in [0, 1, 2]])
    table(margin, ["level", "margin"], ["% late", "% gave up", "Served", "km per passenger", "Occupancy", "% shared", "Wait", "Detour"],
          "7. Margin of the taxis (high demand)")
    for lv in [1, 3, 4]:
        wins(margin[margin.level == lv], f"level {lv}", "margin", 1, 0, "% late")
    m1 = margin[margin.margin == 1]
    wins(m1, "margin=1", "level", 3, 1, "% gave up")
    wins(m1, "margin=1", "level", 3, 1, "km per passenger")
    plot(margin, "margin", ["% late", "% gave up", "km per passenger"], "margin", hue="level")


if __name__ == "__main__":
    main()
