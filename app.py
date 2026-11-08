"""
Live view:   solara run app.py
Taxis = squares (grey: empty, green: 1 passenger, red: 2 or more)
Passengers = dots (blue: calling, cyan: booked). A passenger in a taxi is not drawn.
"""

from mesa.visualization import SolaraViz, SpaceRenderer, make_plot_component
from mesa.visualization.components import AgentPortrayalStyle

from taxi_share.agents import Taxi
from taxi_share.model import TaxiModel


def agent_portrayal(agent):
    # the view only observes the agents, it takes no decision
    if isinstance(agent, Taxi):
        colour = ["tab:gray", "tab:green", "tab:red"][min(len(agent.on_board), 2)]
        return AgentPortrayalStyle(color=colour, marker="s", size=90, zorder=2)
    colour = "tab:cyan" if agent.state == "booked" else "tab:blue"
    return AgentPortrayalStyle(color=colour, marker="o", size=25, zorder=1)


model_params = {
    "level": {"type": "SliderInt", "value": 4, "label": "Design level (1-4)", "min": 1, "max": 4, "step": 1},
    "n_taxis": {"type": "SliderInt", "value": 12, "label": "Taxis", "min": 2, "max": 30, "step": 1},
    "demand": {"type": "SliderFloat", "value": 0.8, "label": "New passengers per step",
               "min": 0.1, "max": 2.0, "step": 0.1},
    "capacity": {"type": "SliderInt", "value": 4, "label": "Seats (level 4)", "min": 3, "max": 6, "step": 1},
    "max_detour": {"type": "SliderInt", "value": 3, "label": "Detour accepted (km)", "min": 0, "max": 8, "step": 1},
    "max_wait": {"type": "SliderInt", "value": 10, "label": "Max wait (steps)", "min": 3, "max": 30, "step": 1},
    "margin": {"type": "SliderInt", "value": 0, "label": "Margin of the taxis (steps per stop)", "min": 0, "max": 2, "step": 1},
    "demand_steps": 2000,   # in the live view new passengers keep coming
    "seed": 0,
}

model = TaxiModel(demand_steps=2000, seed=0)
renderer = SpaceRenderer(model=model, backend="matplotlib").setup_agents(agent_portrayal).render()

page = SolaraViz(
    model,
    renderer,
    model_params=model_params,
    name="Taxi sharing",
    components=[
        make_plot_component({"Calling or booked": "tab:blue", "In taxi": "tab:green"}),
        make_plot_component("Total km"),
        make_plot_component({"% gave up": "tab:red", "% shared": "tab:orange", "% late": "tab:purple"}),
    ],
)
page  # noqa
