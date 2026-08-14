"""Wheel-probability polynomial coefficients, one cubic per pack (fed to
np.polyval with ALSA).

Source: the MTGAZone wheel guide — https://mtgazone.com/how-to-wheel-in-drafts/
Example for pack #1, ALSA 7.2:
-0.46*(7.2^3) + 7.97*(7.2^2) - 27.43*7.2 + 26.61 = 70.6% (69.4% in the article)
Pack #6: 0.25*(7.2^3) +-2.65*(7.2^2) + 9.76*7.2 - 11.21 = 15.0% (13.0% in the article)
Percentages are close to but not identical to the article, so the coefficients are
likely fitted/generalized from set draft data rather than copied verbatim.
"""

WHEEL_COEFFICIENTS = [
    [-0.46, 7.97, -27.43, 26.61],
    [-0.33, 6.31, -23.12, 23.86],
    [-0.19, 4.39, -17.06, 17.71],
    [-0.06, 2.27, -9.22, 9.43],
    [0.08, 0.15, -1.88, 2.36],
    [0.25, -2.65, 9.76, -11.21],
]

__all__ = ["WHEEL_COEFFICIENTS"]
