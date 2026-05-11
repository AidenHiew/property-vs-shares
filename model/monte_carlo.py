"""Monte Carlo runner. Vectorised over trials."""
import numpy as np
from typing import Dict


def generate_correlated_paths(
    trials: int,
    horizon: int,
    property_mu: float,
    property_sigma: float,
    share_mu: float,
    share_sigma: float,
    correlation: float,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    """Return correlated normal draws for property capital growth and share total return.

    Uses Cholesky decomposition to introduce the target correlation.

    Returns dict with 'property_growth' and 'share_return' as (trials, horizon) arrays.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((trials, horizon, 2))

    # Cholesky factor for 2x2 corr matrix [[1, rho], [rho, 1]]
    L = np.array([[1.0, 0.0], [correlation, np.sqrt(1 - correlation ** 2)]])

    correlated = z @ L.T

    property_growth = property_mu + property_sigma * correlated[..., 0]
    share_return    = share_mu    + share_sigma    * correlated[..., 1]

    return {
        "property_growth": property_growth,
        "share_return": share_return,
    }
