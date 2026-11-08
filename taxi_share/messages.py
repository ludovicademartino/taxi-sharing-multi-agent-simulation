"""
Direct communication between the agents.

Mesa has no messages, so we wrote our own:
- Message: a performative and a content
- MessageReceiver: an agent with a list of received messages

To send a message, an agent gives it to the model (the environment), and the
model calls notify() on each receiver. The receiver reads its messages
later, in its perception.
"""

from mesa.discrete_space import CellAgent


class Message:
    """Message structure. We use the performatives of the Contract Net (FIPA).
    inform and inform-done are assertive: the taxi only tells a fact, and the
    passenger decides itself what to do with it."""
    CFP = "cfp"                  # passenger -> taxis: "who can take me from A to B?"
    PROPOSE = "propose"          # taxi -> passengers: "I can, you arrive in k steps"
    ACCEPT = "accept-proposal"   # passenger -> one taxi: "I take your offer"
    REJECT = "reject-proposal"   # passenger -> the other taxis: "no thanks"
    FAILURE = "failure"          # taxi -> passenger: "sorry, I have no more room for you"
    INFORM = "inform"            # taxi -> passenger: "I am in your district"
    INFORM_DONE = "inform-done"  # taxi -> passenger: "you have arrived at your destination"

    def __init__(self, performative, content=None):
        self.performative = performative
        self.content = content or {}   # only data (coordinates, numbers, addresses)


class MessageReceiver(CellAgent):
    """Agent that can receive messages"""

    def __init__(self, model):
        super().__init__(model)
        self.messages = []

    def notify(self, message, sender):
        """Called by the model when a message arrives"""
        self.messages.append((message, sender))

    def read_messages(self):
        """Perception: I take all my messages and my list is empty again"""
        messages = self.messages
        self.messages = []
        return messages

    def send(self, performative, receivers, content=None):
        """Action: one message, to one or several receivers"""
        self.model.send(Message(performative, content), self, receivers)
