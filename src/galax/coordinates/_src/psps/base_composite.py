"""ABC for composite phase-space positions."""

__all__ = ["AbstractCompositePhaseSpacePosition"]

from abc import abstractmethod
from collections.abc import Hashable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

import equinox as eqx
from jaxtyping import Shaped
from plum import dispatch

import coordinax as cx
import quaxed.numpy as jnp
from dataclassish import field_items
from unxt import Quantity
from xmmutablemap import ImmutableMap
from zeroth import zeroth

import galax.typing as gt
from .base import AbstractBasePhaseSpacePosition, ComponentShapeTuple

if TYPE_CHECKING:
    from typing import Self


# Note: cannot have `strict=True` because of inheriting from ImmutableMap.
class AbstractCompositePhaseSpacePosition(
    AbstractBasePhaseSpacePosition,
    ImmutableMap[str, AbstractBasePhaseSpacePosition],  # type: ignore[misc]
    strict=False,  # type: ignore[call-arg]
):
    r"""Abstract base class of composite phase-space positions.

    The composite phase-space position is a point in the 3 spatial + 3 kinematic
    + 1 time -dimensional phase space :math:`\mathbb{R}^7` of a dynamical
    system. It is composed of multiple phase-space positions, each of which
    represents a component of the system.

    The input signature matches that of :class:`dict` (and
    :class:`~xmmutablemap.ImmutableMap`), so you can pass in the components
    as keyword arguments or as a dictionary.

    The components are stored as a dictionary and can be key accessed. However,
    the composite phase-space position itself acts as a single
    `AbstractBasePhaseSpacePosition` object, so you can access the composite
    positions, velocities, and times as if they were a single object. In this
    base class the composition of the components is abstract and must be
    implemented in the subclasses.

    Examples
    --------
    For this example we will use
    `galax.coordinates.CompositePhaseSpacePosition`.

    >>> from dataclasses import replace
    >>> import quaxed.numpy as jnp
    >>> from unxt import Quantity
    >>> import coordinax as cx
    >>> import galax.coordinates as gc

    >>> def stack(vs: list[cx.AbstractPos]) -> cx.AbstractPos:
    ...    comps = {k: jnp.stack([getattr(v, k) for v in vs], axis=-1)
    ...             for k in vs[0].components}
    ...    return replace(vs[0], **comps)

    >>> psp1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "kpc"),
    ...                              p=Quantity([4, 5, 6], "km/s"),
    ...                              t=Quantity(7, "Myr"))
    >>> psp2 = gc.PhaseSpacePosition(q=Quantity([10, 20, 30], "kpc"),
    ...                              p=Quantity([40, 50, 60], "km/s"),
    ...                              t=Quantity(7, "Myr"))

    >>> c_psp = gc.CompositePhaseSpacePosition(psp1=psp1, psp2=psp2)
    >>> c_psp["psp1"] is psp1
    True

    >>> c_psp.q
    CartesianPos3D(
      x=Quantity[...](value=f64[2], unit=Unit("kpc")),
      y=Quantity[...](value=f64[2], unit=Unit("kpc")),
      z=Quantity[...](value=f64[2], unit=Unit("kpc"))
    )

    >>> c_psp.p.d_x
    Quantity['speed'](Array([ 4., 40.], dtype=float64), unit='km / s')

    Note that the length of the individual components are 0, but the length of
    the composite is the sum of the lengths of the components.

    >>> len(psp1)
    0

    >>> len(c_psp)
    2
    """

    _data: dict[str, AbstractBasePhaseSpacePosition]

    def __init__(
        self,
        psps: (
            dict[str, AbstractBasePhaseSpacePosition]
            | tuple[tuple[str, AbstractBasePhaseSpacePosition], ...]
        ) = (),
        /,
        **kwargs: AbstractBasePhaseSpacePosition,
    ) -> None:
        ImmutableMap.__init__(self, psps, **kwargs)  # <- ImmutableMap.__init__

    @property
    @abstractmethod
    def q(self) -> cx.AbstractPos3D:
        """Positions."""

    @property
    @abstractmethod
    def p(self) -> cx.AbstractVel3D:
        """Conjugate momenta."""

    @property
    @abstractmethod
    def t(self) -> Shaped[Quantity["time"], "..."]:
        """Times."""

    def __repr__(self) -> str:  # TODO: not need this hack
        return cast(str, ImmutableMap.__repr__(self))

    # ==========================================================================
    # Array properties

    @property
    def _shape_tuple(self) -> tuple[gt.Shape, ComponentShapeTuple]:
        """Batch and component shapes.

        Examples
        --------
        >>> from unxt import Quantity
        >>> import coordinax as cx
        >>> import galax.coordinates as gc

        >>> w1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "m"),
        ...                            p=Quantity([4, 5, 6], "m/s"),
        ...                            t=Quantity(7.0, "s"))
        >>> w2 = gc.PhaseSpacePosition(q=Quantity([1.5, 2.5, 3.5], "m"),
        ...                            p=Quantity([4.5, 5.5, 6.5], "m/s"),
        ...                            t=Quantity(6.0, "s"))

        >>> cw = gc.CompositePhaseSpacePosition(w1=w1, w2=w2)
        >>> cw._shape_tuple
        ((2,), ComponentShapeTuple(q=3, p=3, t=1))
        """
        # TODO: speed up
        batch_shape = jnp.broadcast_shapes(*[psp.shape for psp in self.values()])
        if not batch_shape:
            batch_shape = (len(self),)
        else:
            batch_shape = (*batch_shape[:-1], len(self._data) * batch_shape[-1])
        shape = zeroth(self.values())._shape_tuple[1]  # noqa: SLF001
        return batch_shape, shape

    def __len__(self) -> int:
        # Length is the sum of the lengths of the components.
        # For length-0 components, we assume a length of 1.
        return sum([len(w) or 1 for w in self.values()])

    # ---------------------------------------------------------------
    # Getitem

    @AbstractBasePhaseSpacePosition.__getitem__.dispatch
    def __getitem__(
        self: "AbstractCompositePhaseSpacePosition", key: Any
    ) -> "AbstractCompositePhaseSpacePosition":
        """Get item from the key.

        Examples
        --------
        >>> from unxt import Quantity
        >>> import galax.coordinates as gc

        >>> w1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "m"),
        ...                            p=Quantity([4, 5, 6], "m/s"),
        ...                            t=Quantity(7.0, "s"))
        >>> w2 = gc.PhaseSpacePosition(q=Quantity([1.5, 2.5, 3.5], "m"),
        ...                            p=Quantity([4.5, 5.5, 6.5], "m/s"),
        ...                            t=Quantity(6.0, "s"))
        >>> cw = gc.CompositePhaseSpacePosition(w1=w1, w2=w2)

        >>> cw[...]
        CompositePhaseSpacePosition({'w1': PhaseSpacePosition(
            q=CartesianPos3D( ... ),
            p=CartesianVel3D( ... ),
            t=Quantity[PhysicalType('time')](value=f64[], unit=Unit("s"))
          ), 'w2': PhaseSpacePosition(
            q=CartesianPos3D( ... ),
            p=CartesianVel3D( ... ),
            t=Quantity[PhysicalType('time')](value=f64[], unit=Unit("s"))
        )})

        """
        # Get from each value, e.g. a slice
        return type(self)(**{k: v[key] for k, v in self.items()})

    @AbstractBasePhaseSpacePosition.__getitem__.dispatch
    def __getitem__(
        self: "AbstractCompositePhaseSpacePosition", key: str
    ) -> AbstractBasePhaseSpacePosition:
        """Get item from the key.

        Examples
        --------
        >>> from unxt import Quantity
        >>> import galax.coordinates as gc

        >>> w1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "m"),
        ...                            p=Quantity([4, 5, 6], "m/s"),
        ...                            t=Quantity(7.0, "s"))
        >>> w2 = gc.PhaseSpacePosition(q=Quantity([1.5, 2.5, 3.5], "m"),
        ...                            p=Quantity([4.5, 5.5, 6.5], "m/s"),
        ...                            t=Quantity(6.0, "s"))
        >>> cw = gc.CompositePhaseSpacePosition(w1=w1, w2=w2)

        >>> cw["w1"] is w1
        True

        """
        return self._data[key]

    # ==========================================================================
    # Convenience methods

    def to_units(self, units: Any) -> "Self":
        """Convert the components to the given units.

        Examples
        --------
        For this example we will use
        `galax.coordinates.CompositePhaseSpacePosition`.

        >>> from unxt import Quantity
        >>> from unxt.unitsystems import solarsystem
        >>> import galax.coordinates as gc

        >>> psp1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "kpc"),
        ...                              p=Quantity([4, 5, 6], "km/s"),
        ...                              t=Quantity(7, "Myr"))

        >>> c_psp = gc.CompositePhaseSpacePosition(psp1=psp1)
        >>> c_psp.to_units(solarsystem)
        CompositePhaseSpacePosition({'psp1': PhaseSpacePosition(
            q=CartesianPos3D(
                x=Quantity[...](value=f64[], unit=Unit("AU")),
                ...
        """
        return type(self)(**{k: v.to_units(units) for k, v in self.items()})

    # ===============================================================
    # Collection methods

    @property
    def shapes(self) -> Mapping[str, tuple[int, ...]]:
        """Get the shapes of the components."""
        return MappingProxyType({k: v.shape for k, v in field_items(self)})


# =============================================================================
# helper functions


# Register AbstractCompositePhaseSpacePosition with `coordinax.represent_as`
@dispatch  # type: ignore[misc]
def represent_as(
    psp: AbstractCompositePhaseSpacePosition,
    position_cls: type[cx.AbstractPos],
    velocity_cls: type[cx.AbstractVel] | None = None,
    /,
) -> AbstractCompositePhaseSpacePosition:
    """Return with the components transformed.

    Parameters
    ----------
    psp : :class:`~galax.coordinates.AbstractCompositePhaseSpacePosition`
        The phase-space position.
    position_cls : type[:class:`~vector.AbstractPos`]
        The target position class.
    velocity_cls : type[:class:`~vector.AbstractVel`], optional
        The target differential class. If `None` (default), the differential
        class of the target position class is used.

    Examples
    --------
    >>> from unxt import Quantity
    >>> import coordinax as cx
    >>> import galax.coordinates as gc

    We define a composite phase-space position with two components.
    Every component is a phase-space position in Cartesian coordinates.

    >>> psp1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "m"),
    ...                              p=Quantity([4, 5, 6], "m/s"),
    ...                              t=Quantity(7.0, "s"))
    >>> psp2 = gc.PhaseSpacePosition(q=Quantity([1.5, 2.5, 3.5], "m"),
    ...                              p=Quantity([4.5, 5.5, 6.5], "m/s"),
    ...                              t=Quantity(6.0, "s"))
    >>> cpsp = gc.CompositePhaseSpacePosition(psp1=psp1, psp2=psp2)

    We can transform the composite phase-space position to a new position class.

    >>> cx.represent_as(cpsp, cx.CylindricalPos)
    CompositePhaseSpacePosition({'psp1': PhaseSpacePosition(
        q=CylindricalPos( ... ),
        p=CylindricalVel( ... ),
        t=Quantity...
      ),
      'psp2': PhaseSpacePosition(
        q=CylindricalPos( ... ),
        p=CylindricalVel( ... ),
        t=...
    )})

    """
    vel_cls = position_cls.differential_cls if velocity_cls is None else velocity_cls
    # TODO: can we use `replace`?
    return type(psp)(
        **{k: represent_as(v, position_cls, vel_cls) for k, v in psp.items()}
    )


# =================


@dispatch(precedence=1)
def replace(
    obj: AbstractCompositePhaseSpacePosition, /, **kwargs: Any
) -> AbstractCompositePhaseSpacePosition:
    """Replace the components of the composite phase-space position.

    Examples
    --------
    >>> import galax.coordinates as gc
    >>> from dataclassish import replace

    We define a composite phase-space position with two components.
    Every component is a phase-space position in Cartesian coordinates.

    >>> psp1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "m"),
    ...                              p=Quantity([4, 5, 6], "m/s"),
    ...                              t=Quantity(7.0, "s"))
    >>> psp2 = gc.PhaseSpacePosition(q=Quantity([1.5, 2.5, 3.5], "m"),
    ...                              p=Quantity([4.5, 5.5, 6.5], "m/s"),
    ...                              t=Quantity(6.0, "s"))
    >>> cpsp = gc.CompositePhaseSpacePosition(psp1=psp1, psp2=psp2)

    We can replace the components of the composite phase-space position.

    >>> cpsp2 = replace(cpsp, psp1=psp2, psp2=psp1)

    >>> cpsp2["psp1"] != psp1
    True

    >>> cpsp2["psp1"] == psp2
    Array(True, dtype=bool)

    >>> cpsp2["psp2"] == psp1
    Array(True, dtype=bool)

    """
    # TODO: directly call the Mapping implementation
    extra_keys = set(kwargs) - set(obj)
    kwargs = eqx.error_if(kwargs, any(extra_keys), "invalid keys {extra_keys}.")

    return type(obj)(**{**obj, **kwargs})


@dispatch(precedence=1)
def replace(
    obj: AbstractCompositePhaseSpacePosition,
    replacements: Mapping[str, Any],
    /,
) -> AbstractCompositePhaseSpacePosition:
    """Replace the components of the composite phase-space position.

    Examples
    --------
    >>> import galax.coordinates as gc
    >>> from dataclassish import replace

    We define a composite phase-space position with two components. Every
    component is a phase-space position in Cartesian coordinates.

    >>> psp1 = gc.PhaseSpacePosition(q=Quantity([1, 2, 3], "m"),
    ...                              p=Quantity([4, 5, 6], "m/s"),
    ...                              t=Quantity(7.0, "s"))
    >>> psp2 = gc.PhaseSpacePosition(q=Quantity([1.5, 2.5, 3.5], "m"),
    ...                              p=Quantity([4.5, 5.5, 6.5], "m/s"),
    ...                              t=Quantity(6.0, "s"))
    >>> cpsp = gc.CompositePhaseSpacePosition(psp1=psp1, psp2=psp2)

    We can selectively replace the ``t`` component of each constituent
    phase-space position.

    >>> cpsp2 = replace(cpsp, {"psp1": {"t": Quantity(10.0, "s")},
    ...                        "psp2": {"t": Quantity(11.0, "s")}})

    """
    # AbstractCompositePhaseSpacePosition is both a Mapping and a dataclass
    # so we need to disambiguate the method to call
    method = replace.invoke(Mapping[Hashable, Any], Mapping[str, Any])
    return method(obj, replacements)
