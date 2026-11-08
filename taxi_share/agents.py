"""
The two agents: Passenger and Taxi.

Both follow the procedural loop:  step() = perceive -> decide -> act
- perceive(): read my messages and update my beliefs (no choice here)
- decide():   choose one action; the taxi may also update its plan here
              (its intentions), but decide() never changes the city
- act():      do this action

One action per step. Mesa runs the agents one after the other in each step,
and sending a message means calling the model, which writes in the mailbox
of the receivers: so sending a message is an action, like driving.
At each step an agent sends one message (it can have several receivers)
or does one physical action, never both.

An agent only knows the others by their address: the "sender" of a
message, or the address that a passenger writes in its cfp (like an AID
in JADE). It never reads or changes the variables of another agent.
"""

from taxi_share.messages import Message, MessageReceiver


def distance(a, b):
    """Number of districts between two coordinates.
    Our grid has 8 neighbours per cell, so a diagonal move costs one district
    like a straight move: the distance is the largest of the two differences."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def move_towards(cell, target):
    """The neighbour cell that is the closest to the target.
    With 8 neighbours, repeating this gives a shortest path, so we do not
    need a routing algorithm."""
    return min(cell.neighborhood, key=lambda c: distance(c.coordinate, target))


# =============================================================================
class Passenger(MessageReceiver):
    """
    Cognitive agent: it has beliefs (offers, booking) and if-then rules.
    calling -> booked -> in_taxi -> leaves the city
    calling -> gives up after max_wait steps without a booking
    """

    def __init__(self, model, cell, destination, max_detour, max_wait):
        super().__init__(model)
        self.cell = cell
        self.destination = destination.coordinate
        self.direct = distance(cell.coordinate, self.destination)  # km of the direct trip
        self.max_ride = self.direct + max_detour   # the longest ride I accept (km)
        self.max_wait = max_wait                   # my patience (steps)
        self.state = "calling"
        self.t_request = model.steps
        # the latest step at which I want to arrive: max_wait steps to be picked up,
        # max_ride steps in the car, and 2 steps to get in and out
        self.latest = self.t_request + max_wait + self.max_ride + 2
        self.t_pickup = None
        # (arrival, taxi) received while I am calling. An answer to one of my
        # older calls is kept too: it is still a real offer for the same trip.
        self.offers = []
        self.to_reject = []    # taxis whose offer I did not take
        self.km = None         # km of my ride (told by the taxi at the end)
        self.shared = False    # did I share the taxi? (told by the taxi at the end)
        self.n_accepts = 0     # how many offers I accepted...
        self.n_failures = 0    # ...and how many of them ended with a failure
        # beliefs updated at each perception
        self.now = model.steps          # current step (clock of the city)
        self.taxis = []                 # addresses of the taxis (public list of the city)
        self.failure = False            # my taxi told me it has no more room
        self.taxi_here = False          # my taxi told me it is in my district
        self.arrived = False            # my taxi told me I have arrived

    def step(self):
        self.perceive()
        self.act(self.decide())

    def perceive(self):
        self.now = self.model.steps
        self.taxis = self.model.taxis      # the list of taxis is public in the city
        self.failure = self.taxi_here = self.arrived = False
        for message, sender in self.read_messages():
            if message.performative == Message.PROPOSE and self.state == "calling":
                # one propose message has one offer for each caller: I read mine
                self.offers.append((message.content["arrival"][self.unique_id], sender))
            elif message.performative == Message.FAILURE:
                self.failure = True
                self.n_failures += 1
            elif message.performative == Message.INFORM:
                self.taxi_here = True   # my taxi is in my district (I decide to get in)
            elif message.performative == Message.INFORM_DONE:
                self.arrived = True
                self.km = message.content["km"]
                self.shared = message.content["shared"]

    def decide(self):
        """one action, the rules are in order of priority"""
        if self.arrived:
            return "leave"
        if self.taxi_here:
            return "board"
        if self.state == "booked" and self.failure:
            return "call"               # my taxi has no more room: I call again
        if self.to_reject:
            return "reject"
        if self.state != "calling":
            return "wait"               # booked (my taxi is coming) or in the taxi
        if self.offers:
            return "accept"
        if self.now - self.t_request >= self.max_wait:
            return "give_up"
        return "call"                   # first call, or nobody answered: call again

    def request(self):
        """What I tell the taxis about my trip (and my address, to answer me)"""
        return {"address": self.unique_id, "origin": self.cell.coordinate,
                "destination": self.destination, "max_ride": self.max_ride, "latest": self.latest}

    def act(self, action):
        if action == "call":            # one message to all the taxis
            self.send(Message.CFP, self.taxis, self.request())
            self.state, self.offers = "calling", []
        elif action == "accept":        # one message to the taxi that brings me first
            arrival, best = min(self.offers, key=lambda offer: offer[0])
            self.send(Message.ACCEPT, [best], self.request())
            self.to_reject = [taxi for _, taxi in self.offers if taxi is not best]
            self.state, self.offers = "booked", []
            self.n_accepts += 1
        elif action == "reject":        # one message to all the other taxis
            self.send(Message.REJECT, self.to_reject)
            self.to_reject = []
        elif action == "board":         # I get in the taxi: I am not in a district any more
            self.state, self.t_pickup = "in_taxi", self.now
            self.cell = None
        elif action in ("leave", "give_up"):   # I leave the city, the model records my trip
            served = action == "leave"
            self.model.leave(self, {
                "gave_up": not served,
                "wait": self.t_pickup - self.t_request if served else None,
                "direct": self.direct,
                "late": served and self.now > self.latest,
                "detour": self.km / self.direct if served else None,
                "shared": self.shared,
                "accepts": self.n_accepts,
                "failures": self.n_failures})
        # "wait": I do nothing


# =============================================================================
class Taxi(MessageReceiver):
    """
    Rational agent: its goal is explicit (bring each booked passenger to its
    destination, within its limits) and it plans how to reach it: its route,
    the list of stops to serve, is its plan. It plans where a new passenger
    can enter this route.
    one action per step, by priority:
      1. a stop is here: tell the passenger I am here / it has arrived (inform / inform-done)
      2. tell the passengers I cannot take any more (failure)
      3. answer all the callers I can take, in one propose message
      4. drive one district towards the next stop
    A proposal does not book the seat: two passengers can accept the same
    seat, and the second one gets a failure and calls again.
    A taxi that cannot take a caller does not answer (no "refuse" message):
    a message costs a step, and the passenger treats silence as a "no".
    """

    def __init__(self, model, cell, level, seats, margin):
        super().__init__(model)
        self.cell = cell
        self.level = level      # design level of the experiment (1 to 4)
        self.seats = seats
        # Extra steps I count for each stop when I plan. Sending a message
        # takes a step in which I do not drive, and I cannot know in advance
        # how many calls I will answer. With margin=0 my times are a bit
        # optimistic, with margin=1 I keep one more step per stop.
        self.margin = margin
        self.route = []         # stops: (coordinate, passenger, "pickup" or "dropoff")
        self.on_board = {}      # passenger -> km driven since its pickup
        self.limits = {}        # passenger -> (longest ride in km, latest arrival step)
        self.shared = set()     # passengers who shared the taxi at some moment
        self.failures = []      # passengers who accepted but do not fit any more
        self.km = 0             # km driven
        self.passenger_km = 0   # km x passengers on board (for the occupancy)
        # beliefs updated at each perception
        self.here = cell.coordinate     # my district
        self.calls = []                 # (passenger, request) of the callers
        self.accepts = []               # (passenger, request) of the passengers who accepted

    def step(self):
        self.perceive()
        self.act(self.decide())

    def perceive(self):
        """Read the messages and update my beliefs (no choice here)"""
        self.here = self.cell.coordinate
        self.calls = []     # (passenger, request) of the callers
        self.accepts = []   # (passenger, request) of the passengers who accepted my offer
        for message, sender in self.read_messages():
            if message.performative == Message.CFP:
                self.calls.append((sender, message.content))
            elif message.performative == Message.ACCEPT:
                self.accepts.append((sender, message.content))
            # REJECT: nothing to do

    def decide(self):
        """First I update my plan with the accepted offers, then I choose
        one action (and its data). Changing my plan (my intentions) does not
        change anything in the city, so it is not an action."""
        for passenger, request in self.accepts:
            # my proposal did not book the seat: I check that it still fits
            route = self.plan(passenger, request)
            if route is None:
                self.failures.append(passenger)
            else:
                self.route = route
                self.limits[passenger] = (request["max_ride"], request["latest"])

        if self.route and self.route[0][0] == self.here:
            return (self.route[0][2],)                  # "pickup" or "dropoff"
        if self.failures:
            return ("failure",)
        offers = []
        for passenger, request in self.calls:          # every caller is checked alone
            route = self.plan(passenger, request)
            if route is not None:
                offers.append((passenger, request["address"], self.arrival(route, passenger)))
        if offers:
            return ("propose", offers)
        if self.route:
            return ("drive",)
        return ("idle",)

    def act(self, decision):
        action = decision[0]
        if action == "pickup":           # one message: "I am in your district"
            # Simplification: from this message the passenger counts as on board,
            # even if it gets in at its own next turn (see Limits in the report).
            passenger = self.route.pop(0)[1]
            self.on_board[passenger] = 0
            if len(self.on_board) > 1:
                self.shared.update(self.on_board)
            self.send(Message.INFORM, [passenger])
        elif action == "dropoff":        # one message: "you have arrived"
            passenger = self.route.pop(0)[1]
            km = self.on_board.pop(passenger)
            del self.limits[passenger]
            self.send(Message.INFORM_DONE, [passenger], {"km": km, "shared": passenger in self.shared})
            self.shared.discard(passenger)
        elif action == "failure":        # one message to all of them
            self.send(Message.FAILURE, self.failures)
            self.failures = []
        elif action == "propose":        # one message to all the callers I can take
            offers = decision[1]         # one arrival time for each caller, by its address
            self.send(Message.PROPOSE, [p for p, _, _ in offers],
                      {"arrival": {address: arrival for _, address, arrival in offers}})
        elif action == "drive":          # one physical action, no message
            self.cell = move_towards(self.cell, self.route[0][0])
            self.km += 1
            self.passenger_km += len(self.on_board)
            for passenger in self.on_board:
                self.on_board[passenger] += 1
        # "idle": no passenger, no call, I stay where I am

    # ----- planning: used by decide, it changes nothing -----
    def plan(self, passenger, request):
        """
        Where can I put a new passenger in my route?
        We try every place for its pickup and every later place for its
        drop-off (the other stops keep their order), and we keep the shortest
        new route that respects the rules. Returns None if nothing fits.
        """
        if self.level == 1 and self.route:
            return None                  # level 1: one passenger at a time (today's taxi)
        # The order of the stops is our plan. A route with n stops has about
        # n*n/2 ways to add a pickup and a drop-off, and our routes are short
        # (a few stops), so trying all of them is fast enough.
        pickup = (request["origin"], passenger, "pickup")
        dropoff = (request["destination"], passenger, "dropoff")
        limits = dict(self.limits)
        limits[passenger] = (request["max_ride"], request["latest"])
        # a stop that is here is served at this step, so it stays first
        first = 1 if self.route and self.route[0][0] == self.here else 0
        best = None
        for i in range(first, len(self.route) + 1):
            for j in range(i, len(self.route) + 1):
                route = self.route[:i] + [pickup] + self.route[i:j] + [dropoff] + self.route[j:]
                if not self.respects(route, limits):
                    continue
                if self.level == 2 and self.route and self.length(route) > self.length(self.route):
                    continue             # level 2: the route must not change
                if best is None or self.length(route) < self.length(best):
                    best = route
        return best

    def respects(self, route, limits):
        """We follow the route stop by stop and check the rules:
        - never more passengers than seats
        - nobody rides more km than it accepts
        - nobody arrives later than it wants (1 step per km, 1 step per stop,
          plus my margin for each stop)"""
        riding = dict(self.on_board)     # passenger -> km in the car
        here, t = self.here, self.model.steps
        for coordinate, passenger, kind in route:
            km = distance(here, coordinate)
            here, t = coordinate, t + km + 1 + self.margin
            for p in riding:
                riding[p] += km
            if kind == "pickup":
                riding[passenger] = 0
                if len(riding) > self.seats:
                    return False
            else:
                max_ride, latest = limits[passenger]
                if riding.pop(passenger) > max_ride or t > latest:
                    return False
        return True

    def length(self, route):
        """km from my position to the end of the route"""
        km, here = 0, self.here
        for coordinate, _, _ in route:
            km += distance(here, coordinate)
            here = coordinate
        return km

    def arrival(self, route, passenger):
        """Steps until the passenger arrives: 1 step per km, 1 step per stop
        and my margin for each stop (the same count as in respects)"""
        for k, (_, p, kind) in enumerate(route):
            if p is passenger and kind == "dropoff":
                return self.length(route[:k + 1]) + (k + 1) * (1 + self.margin)
        return None   # never reached: plan() always puts the drop-off in the route
