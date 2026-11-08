"""
The environment (mesa.Model): the grid of districts, the list of taxis,
the delivery of the messages, the new passengers and the measures.
It never decides which taxi takes which passenger: the agents do.
"""

import mesa
from mesa.discrete_space import OrthogonalMooreGrid

from taxi_share.agents import Passenger, Taxi, distance

# number of seats for each design level (None = the "capacity" parameter)
SEATS = {1: 1, 2: 2, 3: 2, 4: None}


class TaxiModel(mesa.Model):

    def __init__(self, level=4, n_taxis=12, demand=0.8, capacity=4, max_detour=3,
                 max_wait=10, margin=0, size=20, demand_steps=300, seed=None):
        super().__init__(rng=seed)
        self.max_detour = max_detour      # extra km a passenger accepts
        self.max_wait = max_wait          # steps a passenger waits for a booking
        self.margin = margin              # extra steps per stop in the plan of a taxi
        self.trips = []                   # one record for each passenger who left

        # 1 cell = 1 district; capacity=None: many agents in the same cell
        self.grid = OrthogonalMooreGrid((size, size), torus=False, capacity=None, random=self.random)
        cells = self.grid.all_cells.cells

        # All the passengers of the run are drawn now, before the taxis.
        # So with the same seed, every setting (level, fleet...) gets exactly
        # the same passengers, and we can compare the settings fairly.
        # demand = passengers per step on average (0.8 = one with probability 0.8)
        self.requests = []
        for _ in range(demand_steps):
            n = int(demand) + (self.random.random() < demand % 1)
            trips = []
            for _ in range(n):
                origin, destination = self.random.choice(cells), self.random.choice(cells)
                while distance(origin.coordinate, destination.coordinate) < 2:
                    destination = self.random.choice(cells)
                trips.append((origin, destination))
            self.requests.append(trips)

        seats = SEATS[level] or capacity
        self.taxis = list(Taxi.create_agents(self, n_taxis, self.random.choices(cells, k=n_taxis),
                                             level=level, seats=seats, margin=margin))

        self.datacollector = mesa.DataCollector(model_reporters={
            "Calling or booked": lambda m: len(m.passengers().select(lambda p: p.state != "in_taxi")),
            "In taxi": lambda m: len(m.passengers().select(lambda p: p.state == "in_taxi")),
            "Total km": lambda m: sum(t.km for t in m.taxis),
            "% gave up": lambda m: percent(m.trips, "gave_up"),
            "% shared": lambda m: percent([t for t in m.trips if not t["gave_up"]], "shared"),
            "% late": lambda m: percent([t for t in m.trips if not t["gave_up"]], "late"),
        })

    # ----- services of the environment -----
    def send(self, message, sender, receivers):
        """Delivers a message to each receiver"""
        for receiver in receivers:
            receiver.notify(message, sender)

    def leave(self, passenger, record):
        """A passenger leaves the city: we record its trip and remove it"""
        self.trips.append(record)
        passenger.remove()

    def passengers(self):
        return self.agents.select(lambda a: isinstance(a, Passenger))

    # ----- runtime -----
    def step(self):
        if self.steps <= len(self.requests):          # new passengers of this step
            trips = self.requests[self.steps - 1]
            if trips:
                Passenger.create_agents(self, len(trips), [o for o, _ in trips], [d for _, d in trips],
                                        max_detour=self.max_detour, max_wait=self.max_wait)
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)

    # ----- measures at the end of a run (used by experiments.py) -----
    def results(self):
        km = sum(t.km for t in self.taxis)
        served = [t for t in self.trips if not t["gave_up"]]
        return {
            "Total km": km,
            "Served": len(served),
            "km per passenger": km / len(served),
            "Occupancy": sum(t.passenger_km for t in self.taxis) / km,
            "% shared": percent(served, "shared"),
            "% gave up": percent(self.trips, "gave_up"),
            "Direct km": mean(t["direct"] for t in self.trips),
            "Wait": mean(t["wait"] for t in served),
            "Detour": mean(t["detour"] for t in served),
            "% late": percent(served, "late"),
            # accepted offers that ended with a failure (the seat was taken in between)
            "% accepts failed": 100 * sum(t["failures"] for t in self.trips)
                                / max(1, sum(t["accepts"] for t in self.trips)),
        }


def percent(trips, key):
    return 100 * sum(t[key] for t in trips) / len(trips) if trips else 0.0


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0
