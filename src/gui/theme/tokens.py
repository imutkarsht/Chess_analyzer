from dataclasses import dataclass


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    XXXL = 48


class Radius:
    SM = 4
    MD = 6
    LG = 8
    XL = 12
    XXL = 16


@dataclass
class TypeScale:
    display: int = 28
    heading: int = 18
    body: int = 14
    small: int = 12
    tiny: int = 11
    stat_value: int = 42
