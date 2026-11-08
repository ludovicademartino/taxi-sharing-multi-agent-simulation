"""
Checks that the code follows the model (Section 6 of the report):
    python checks.py   (about 10 seconds)

At every step we check that:
- every agent does at most one action: one message, or one move (taxis)
- a taxi never has more passengers than seats
- a passenger never rides more km than it accepts
At the end of every run we check that every passenger has left the city.
The latest arrival is not checked: it is a plan of the taxi, which can be
missed (see Section 5.5 of the report).
"""

from taxi_share.agents import Taxi
from taxi_share.model import TaxiModel


class CheckedModel(TaxiModel):
    """The same model, which also remembers who sent a message in this step"""

    def send(self, message, sender, receivers):
        self.senders.append(sender)
        super().send(message, sender, receivers)

    def step(self):
        self.senders = []
        km_before = {taxi: taxi.km for taxi in self.taxis}
        super().step()
        # at most one action per agent
        assert len(self.senders) == len(set(self.senders)), "an agent sent two messages"
        for taxi in self.taxis:
            moved = taxi.km - km_before[taxi]
            assert moved <= 1, "a taxi drove two districts"
            assert not (moved and taxi in self.senders), "a taxi drove and sent a message"
            # seats and longest ride
            assert len(taxi.on_board) <= taxi.seats, "too many passengers"
            for passenger, km in taxi.on_board.items():
                assert km <= taxi.limits[passenger][0], "a ride is too long"


def main():
    for level in [1, 2, 3, 4]:
        for max_detour in [0, 3, 8]:
            for seed in [0, 1]:
                model = CheckedModel(level=level, max_detour=max_detour, seed=seed)
                model.run_for(300)
                for _ in range(1000):        # no new passengers: wait until everybody has left
                    if len(model.passengers()) == 0:
                        break
                    model.step()
                assert len(model.passengers()) == 0, "a passenger never left"
            print(f"level {level}, detour {max_detour}: OK")
    print("All checks passed.")


if __name__ == "__main__":
    main()
