"""Corotating reference frame."""

__all__ = ["ConstantRotationZOperator"]


from dataclasses import replace
from typing import Literal, final

from jaxtyping import Float, Shaped
from plum import convert

import coordinax as cx
import coordinax.operators as cxop
import quaxed.numpy as jnp
from unxt import Quantity

from galax.coordinates._src.psps.base_psp import AbstractPhaseSpacePosition

vec_matmul = jnp.vectorize(jnp.matmul, signature="(3,3),(3)->(3)")


def rot_z(
    theta: Shaped[Quantity["angle"], ""],
) -> Float[Quantity["dimensionless"], "3 3"]:
    """Rotation matrix for rotation around the z-axis.

    Parameters
    ----------
    theta : Quantity[float, "angle"]
        The angle of rotation.

    Returns
    -------
    tuple[Quantity[float, "angle"], Quantity[float, "angle"]]
        The sine and cosine of the angle.
    """
    return jnp.asarray(
        [
            [jnp.cos(theta), -jnp.sin(theta), 0],
            [jnp.sin(theta), jnp.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )


@final
class ConstantRotationZOperator(cxop.AbstractOperator):  # type: ignore[misc]
    r"""Operator for constant rotation in the x-y plane.

    The coordinate transform is given by:

    .. math::

        (t,\mathbf{x}) \mapsto (t, \mathbf{x} (1 + Omega_z ))

    where :math:`\mathbf {Omega}` is the angular velocity vector in the z
    direction.

    Parameters
    ----------
    Omega_z : Quantity[float, "angular speed"]
        The angular speed about the z axis.

    Examples
    --------
    First some imports:

    >>> from dataclasses import replace
    >>> from plum import convert
    >>> from unxt import Quantity
    >>> import coordinax as cx
    >>> import galax.coordinates as gc
    >>> from galax.coordinates.operators import ConstantRotationZOperator

    We define a rotation of 90 degrees every gigayear about the z axis.

    >>> op = ConstantRotationZOperator(Omega_z=Quantity(90, "deg / Gyr"))

    We can apply the rotation to a position.

    >>> psp = gc.PhaseSpacePosition(q=Quantity([1, 0, 0], "kpc"),
    ...                             p=Quantity([0, 0, 0], "kpc/Gyr"),
    ...                             t=Quantity(1, "Gyr"))

    >>> newpsp = op(psp)

    For display purposes, we convert the resulting position to an Array.

    >>> convert(newpsp.q, Quantity).value.round(2)
    Array([0., 1., 0.], dtype=float64)

    This rotation is time dependent.

    >>> psp2 = replace(psp, t=Quantity(2, "Gyr"))
    >>> convert(op(psp2).q, Quantity).value.round(2)
    Array([-1.,  0.,  0.], dtype=float64)

    We can also apply the rotation to a
    :class:`~galax.corodinates.PhaseSpacePosition`.

    >>> psp = gc.PhaseSpacePosition(q=Quantity([1, 0, 0], "kpc"),
    ...                             p=Quantity([0, 0, 0], "kpc/Gyr"),
    ...                             t=Quantity(1, "Gyr"))


    >>> newpsp = op(psp)
    >>> convert(newpsp.q, Quantity).value.round(2)
    Array([0., 1., 0.], dtype=float64)

    We can also apply the rotation to a :class:`~galax.coordinax.FourVector`.

    >>> t = Quantity(1, "Gyr")
    >>> v4 = cx.FourVector(t=t, q =Quantity([1, 0, 0], "kpc"))

    >>> newv4 = op(v4)
    >>> convert(newv4.q, Quantity).value.round(2)
    Array([0., 1., 0.], dtype=float64)

    We can also apply the rotation to a :class:`~coordinax.AbstractPos3D`.

    >>> q = cx.CartesianPos3D.from_(Quantity([1, 0, 0], "kpc"))
    >>> newq, newt = op(q, t)
    >>> convert(newq, Quantity).value.round(2)
    Array([0., 1., 0.], dtype=float64)

    We can also apply the rotation to a :class:`~unxt.Quantity`, which
    is interpreted as a :class:`~coordinax.CartesianPos3D` if it has shape
    ``(*batch, 3)`` and a :class:`~coordinax.FourVector` if it has shape
    ``(*batch, 4)``.

    >>> q = Quantity([1, 0, 0], "kpc")
    >>> newq, newt = op(q, t)
    >>> newq.value.round(2)
    Array([0., 1., 0.], dtype=float64)
    """

    # TODO: add a converter for 1/s -> rad / s.
    Omega_z: Quantity["angular frequency"] = Quantity(0, "mas / yr")
    """The angular speed about the z axis."""

    # -------------------------------------------

    @property
    def is_inertial(self) -> Literal[False]:
        """Galilean translation is an inertial frame-preserving transformation.

        Examples
        --------
        >>> from unxt import Quantity
        >>> from galax.coordinates.operators import ConstantRotationZOperator

        >>> op = ConstantRotationZOperator(Quantity(360, "deg / Gyr"))
        >>> op.is_inertial
        False
        """
        return False

    @property
    def inverse(self) -> "ConstantRotationZOperator":
        """The inverse of the operator.

        Examples
        --------
        >>> from unxt import Quantity
        >>> from galax.coordinates.operators import ConstantRotationZOperator

        >>> op = ConstantRotationZOperator(Omega_z=Quantity(360, "deg / Gyr"))
        >>> op.inverse
        ConstantRotationZOperator(
            Omega_z=Quantity[...]( value=...i64[], unit=Unit("deg / Gyr") )
        )

        """
        return ConstantRotationZOperator(Omega_z=-self.Omega_z)

    # -------------------------------------------

    @cxop.AbstractOperator.__call__.dispatch(precedence=1)
    def __call__(
        self: "ConstantRotationZOperator",
        q: Quantity["length"],
        t: Quantity["time"],
        /,
    ) -> tuple[Quantity["length"], Quantity["time"]]:
        """Apply the translation to the Cartesian coordinates.

        Examples
        --------
        >>> from unxt import Quantity
        >>> from galax.coordinates.operators import ConstantRotationZOperator

        >>> op = ConstantRotationZOperator(Omega_z=Quantity(90, "deg / Gyr"))

        >>> q = Quantity([1, 0, 0], "kpc")
        >>> t = Quantity(1, "Gyr")
        >>> newq, newt = op(q, t)
        >>> newq.value.round(2)
        Array([0., 1., 0.], dtype=float64)

        >>> newt
        Quantity['time'](Array(1, dtype=int64, ...), unit='Gyr')

        This rotation is time dependent. If we rotate by 2 Gyr, we go another
        90 degrees.

        >>> op(q, Quantity(2, "Gyr"))[0].value.round(2)
        Array([-1.,  0.,  0.], dtype=float64)

        """
        Rz = rot_z(self.Omega_z * t)
        return (vec_matmul(Rz, q), t)

    @cxop.AbstractOperator.__call__.dispatch(precedence=1)
    def __call__(
        self: "ConstantRotationZOperator",
        vec: cx.AbstractPos3D,
        t: Quantity["time"],
        /,
    ) -> tuple[cx.AbstractPos3D, Quantity["time"]]:
        """Apply the translation to the coordinates.

        Examples
        --------
        >>> from plum import convert
        >>> from unxt import Quantity
        >>> import coordinax as cx
        >>> from galax.coordinates.operators import ConstantRotationZOperator

        >>> op = ConstantRotationZOperator(Omega_z=Quantity(90, "deg / Gyr"))

        >>> q = cx.CartesianPos3D.from_(Quantity([1, 0, 0], "kpc"))
        >>> t = Quantity(1, "Gyr")
        >>> newq, newt = op(q, t)
        >>> convert(newq, Quantity).value.round(2)
        Array([0., 1., 0.], dtype=float64)

        >>> newt
        Quantity['time'](Array(1, dtype=int64, ...), unit='Gyr')

        This rotation is time dependent.

        >>> convert(op(q, Quantity(2, "Gyr"))[0], Quantity).value.round(2)
        Array([-1., 0., 0.], dtype=float64)

        """
        q = convert(vec.represent_as(cx.CartesianPos3D), Quantity)
        qp, tp = self(q, t)
        vecp = cx.CartesianPos3D.from_(qp).represent_as(type(vec))
        return (vecp, tp)

    @cxop.AbstractOperator.__call__.dispatch
    def __call__(
        self: "ConstantRotationZOperator", psp: AbstractPhaseSpacePosition, /
    ) -> AbstractPhaseSpacePosition:
        """Apply the translation to the coordinates.

        Examples
        --------
        >>> from dataclasses import replace
        >>> from plum import convert
        >>> from unxt import Quantity
        >>> from galax.coordinates import PhaseSpacePosition
        >>> from galax.coordinates.operators import ConstantRotationZOperator

        >>> op = ConstantRotationZOperator(Omega_z=Quantity(90, "deg / Gyr"))

        >>> psp = PhaseSpacePosition(q=Quantity([1, 0, 0], "kpc"),
        ...                          p=Quantity([0, 0, 0], "kpc/Gyr"),
        ...                          t=Quantity(1, "Gyr"))

        >>> newpsp = op(psp)
        >>> convert(newpsp.q, Quantity).value.round(2)
        Array([0., 1., 0.], dtype=float64)

        >>> newpsp.t
        Quantity['time'](Array(1., dtype=float64), unit='Gyr')

        This rotation is time dependent.

        >>> psp2 = replace(psp, t=Quantity(2, "Gyr"))
        >>> convert(op(psp2).q, Quantity).value.round(2)
        Array([-1.,  0.,  0.], dtype=float64)

        """
        # Shifting the position and time
        q, t = self(psp.q, psp.t)
        # Transforming the momentum. The actual value of momentum is not
        # affected by the translation, however for non-Cartesian coordinates the
        # representation of the momentum in will be different.  First transform
        # the momentum to Cartesian coordinates at the original position. Then
        # transform the momentum back to the original representation, but at the
        # translated position.
        p = psp.p.represent_as(cx.CartesianVel3D, psp.q).represent_as(type(psp.p), q)
        # Reasseble and return
        return replace(psp, q=q, p=p, t=t)


@cxop.simplify_op.register  # type: ignore[misc]
def _simplify_op_rotz(frame: ConstantRotationZOperator, /) -> cxop.AbstractOperator:
    """Simplify the operators in an PotentialFrame.

    Examples
    --------
    >>> from unxt import Quantity
    >>> import coordinax as cx
    >>> import galax.coordinates.operators as gco

    >>> op = gco.ConstantRotationZOperator(Omega_z=Quantity(90, "deg / Gyr"))
    >>> cx.operators.simplify_op(op) == op
    Array(True, dtype=bool)

    >>> op = gco.ConstantRotationZOperator(Omega_z=Quantity(0, "deg / Gyr"))
    >>> cx.operators.simplify_op(op)
    IdentityOperator()

    """
    if frame.Omega_z == 0:
        return cxop.IdentityOperator()
    return frame
