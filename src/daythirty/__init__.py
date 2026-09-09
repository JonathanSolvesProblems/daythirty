"""Day Thirty: an agent that works a California health insurance denial end to end.

The name is the mechanism. Under Cal. Health & Safety Code § 1374.30(j)(3) an enrollee
"shall not be required to participate in the plan's grievance process for more than 30
days", so on the thirtieth day after a grievance is filed the qualifying event occurs and
a six month clock starts, whether or not the plan has answered. Almost nobody knows it
started.
"""

__all__ = ["deadlines", "precedent"]
