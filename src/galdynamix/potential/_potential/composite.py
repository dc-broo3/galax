from __future__ import annotations

__all__ = ["CompositePotential"]


import uuid
from dataclasses import KW_ONLY
from typing import Any, TypeVar, final

import equinox as eqx
import jax.numpy as xp
import jax.typing as jt

from galdynamix.units import UnitSystem, dimensionless
from galdynamix.utils import ImmutableDict, partial_jit

from .base import AbstractPotentialBase

K = TypeVar("K")
V = TypeVar("V")


@final
class CompositePotential(ImmutableDict[AbstractPotentialBase], AbstractPotentialBase):
    """Composite Potential."""

    _data: dict[str, AbstractPotentialBase]
    _: KW_ONLY
    units: UnitSystem = eqx.field(
        init=False,
        static=True,
        converter=lambda x: dimensionless if x is None else UnitSystem(x),
    )
    _G: float = eqx.field(init=False, static=True)

    def __init__(
        self,
        potentials: dict[str, AbstractPotentialBase]
        | tuple[tuple[str, AbstractPotentialBase], ...] = (),
        /,
        **kwargs: AbstractPotentialBase,
    ) -> None:
        super().__init__(potentials, **kwargs)  # type: ignore[arg-type]
        self.__post_init__()

    def __post_init__(self) -> None:
        # Check that all potentials have the same unit system
        units = next(iter(self.values())).units
        if not all(p.units == units for p in self.values()):
            msg = "all potentials must have the same unit system"
            raise ValueError(msg)
        object.__setattr__(self, "units", units)

        # Apply the unit system to any parameters.
        self._init_units()

    # === Potential ===

    @partial_jit()
    def potential_energy(
        self,
        q: jt.Array,
        t: jt.Array,
    ) -> jt.Array:
        return xp.sum(xp.array([p.potential_energy(q, t) for p in self.values()]))

    ###########################################################################
    # Composite potentials

    def __or__(self, other: Any) -> CompositePotential:
        if not isinstance(other, AbstractPotentialBase):
            return NotImplemented

        return CompositePotential(  # combine the two dictionaries
            self._data
            | (  # make `other` into a compatible dictionary.
                other._data
                if isinstance(other, CompositePotential)
                else {str(uuid.uuid4()): other}
            )
        )

    def __ror__(self, other: Any) -> CompositePotential:
        if not isinstance(other, AbstractPotentialBase):
            return NotImplemented

        return CompositePotential(  # combine the two dictionaries
            (  # make `other` into a compatible dictionary.
                other._data
                if isinstance(other, CompositePotential)
                else {str(uuid.uuid4()): other}
            )
            | self._data
        )

    def __add__(self, other: AbstractPotentialBase) -> CompositePotential:
        return self | other