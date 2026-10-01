"""Pure district listing counts to bounded skill demand weights."""

import math


def weights(listings: list[set[str]], known_skills: set[str]) -> dict[str, float]:
    if not listings:
        return {}
    counts = {skill: 0 for skill in known_skills}
    for listing in listings:
        for skill in listing & known_skills:
            counts[skill] += 1
    size = len(listings)
    return {skill: min(2.0, 1.0 + math.log1p(count * 10 / size)) for skill, count in counts.items() if count}
