from collections.abc import Mapping

import astropy.units as u
import jax.experimental.array_api as xp
import jax.numpy as jnp
import pytest
from typing_extensions import override

import galax.potential as gp
from galax.units import UnitSystem, dimensionless, galactic, solarsystem
from galax.utils._misc import first

from .test_composite import AbstractCompositePotential_Test


class TestMilkyWayPotential(AbstractCompositePotential_Test):
    """Test the `galax.potential.CompositePotential` class."""

    @pytest.fixture(scope="class")
    def pot_cls(self) -> type[gp.MilkyWayPotential]:
        """Composite potential class."""
        return gp.MilkyWayPotential

    @pytest.fixture(scope="class")
    def pot_map(self) -> Mapping[str, gp.AbstractPotentialBase]:
        """Composite potential."""
        return {
            "disk": {"m": 6.8e10 * u.Msun, "a": 3.0 * u.kpc, "b": 0.28 * u.kpc},
            "halo": {"m": 5.4e11 * u.Msun, "r_s": 15.62 * u.kpc},
            "bulge": {"m": 5e9 * u.Msun, "c": 1.0 * u.kpc},
            "nucleus": {"m": 1.71e9 * u.Msun, "c": 0.07 * u.kpc},
        }

    @pytest.fixture(scope="class")
    def pot(
        self,
        pot_cls: type[gp.CompositePotential],
        pot_map: Mapping[str, gp.AbstractPotentialBase],
    ) -> gp.CompositePotential:
        """Composite potential."""
        return pot_cls(**pot_map)

    @pytest.fixture(scope="class")
    def pot_map_unitless(self, pot_map) -> Mapping[str, gp.AbstractPotentialBase]:
        """Composite potential."""
        return {k: {kk: vv.value for kk, vv in v.items()} for k, v in pot_map.items()}

    # ==========================================================================
    # TODO: use a universal `replace` function then don't need to override
    #       these tests.

    @override
    def test_init_units_invalid(
        self,
        pot_cls: type[gp.CompositePotential],
        pot_map: Mapping[str, gp.AbstractPotentialBase],
    ) -> None:
        """Test invalid unit system."""
        # TODO: raise a specific error. The type depends on whether beartype is
        # turned on.
        with pytest.raises(Exception):  # noqa: B017, PT011
            pot_cls(**pot_map, units=1234567890)

    @override
    def test_init_units_from_usys(
        self,
        pot_cls: type[gp.CompositePotential],
        pot_map: gp.MilkyWayPotential,
    ) -> None:
        """Test unit system from UnitSystem."""
        usys = UnitSystem(u.km, u.s, u.Msun, u.radian)
        assert pot_cls(**pot_map, units=usys).units == usys

    @override
    def test_init_units_from_args(
        self,
        pot_cls: type[gp.CompositePotential],
        pot_map_unitless: Mapping[str, gp.AbstractPotentialBase],
    ) -> None:
        """Test unit system from None."""
        pot = pot_cls(**pot_map_unitless, units=None)
        assert pot.units == galactic

    @override
    def test_init_units_from_tuple(
        self,
        pot_cls: type[gp.CompositePotential],
        pot_map: Mapping[str, gp.AbstractPotentialBase],
    ) -> None:
        """Test unit system from tuple."""
        units = (u.km, u.s, u.Msun, u.radian)
        assert pot_cls(**pot_map, units=units).units == UnitSystem(*units)

    @override
    def test_init_units_from_name(
        self,
        pot_cls: type[gp.CompositePotential],
        pot_map: Mapping[str, gp.AbstractPotentialBase],
        pot_map_unitless: Mapping[str, gp.AbstractPotentialBase],
    ) -> None:
        """Test unit system from named string."""
        units = "dimensionless"
        pot = pot_cls(**pot_map_unitless, units=units)
        assert pot.units == dimensionless

        units = "solarsystem"
        pot = pot_cls(**pot_map, units=units)
        assert pot.units == solarsystem

        units = "galactic"
        pot = pot_cls(**pot_map, units=units)
        assert pot.units == galactic

        msg = "cannot convert invalid_value to a UnitSystem"
        with pytest.raises(NotImplementedError, match=msg):
            pot_cls(**pot_map, units="invalid_value")

    # ==========================================================================

    # --------------------------
    # `__or__`

    def test_or_incorrect(self, pot):
        """Test the `__or__` method with incorrect inputs."""
        with pytest.raises(TypeError, match="unsupported operand type"):
            _ = pot | 1

    def test_or_pot(self, pot: gp.CompositePotential) -> None:
        """Test the `__or__` method with a single potential."""
        single_pot = gp.KeplerPotential(m=1e12 * u.solMass, units=galactic)
        newpot = pot | single_pot

        assert isinstance(newpot, gp.CompositePotential)

        newkey, newvalue = tuple(newpot.items())[-1]
        assert isinstance(newkey, str)
        assert newvalue is single_pot

    def test_or_compot(self, pot: gp.CompositePotential) -> None:
        """Test the `__or__` method with a composite potential."""
        comp_pot = gp.CompositePotential(
            kep1=gp.KeplerPotential(m=1e12 * u.solMass, units=galactic),
            kep2=gp.KeplerPotential(m=1e12 * u.solMass, units=galactic),
        )
        newpot = pot | comp_pot

        assert isinstance(newpot, gp.CompositePotential)

        newkey, newvalue = tuple(newpot.items())[-2]
        assert newkey == "kep1"
        assert newvalue is newpot["kep1"]

        newkey, newvalue = tuple(newpot.items())[-1]
        assert newkey == "kep2"
        assert newvalue is newpot["kep2"]

    # --------------------------
    # `__ror__`

    def test_ror_incorrect(self, pot):
        """Test the `__or__` method with incorrect inputs."""
        with pytest.raises(TypeError, match="unsupported operand type"):
            _ = 1 | pot

    def test_ror_pot(self, pot: gp.CompositePotential) -> None:
        """Test the `__ror__` method with a single potential."""
        single_pot = gp.KeplerPotential(m=1e12 * u.solMass, units=galactic)
        newpot = single_pot | pot

        assert isinstance(newpot, gp.CompositePotential)

        newkey, newvalue = first(newpot.items())
        assert isinstance(newkey, str)
        assert newvalue is single_pot

    def test_ror_compot(self, pot: gp.CompositePotential) -> None:
        """Test the `__ror__` method with a composite potential."""
        comp_pot = gp.CompositePotential(
            kep1=gp.KeplerPotential(m=1e12 * u.solMass, units=galactic),
            kep2=gp.KeplerPotential(m=1e12 * u.solMass, units=galactic),
        )
        newpot = comp_pot | pot

        assert isinstance(newpot, gp.CompositePotential)

        newkey, newvalue = first(newpot.items())
        assert newkey == "kep1"
        assert newvalue is newpot["kep1"]

        newkey, newvalue = tuple(newpot.items())[1]
        assert newkey == "kep2"
        assert newvalue is newpot["kep2"]

    # --------------------------
    # `__add__`

    def test_add_incorrect(self, pot):
        """Test the `__add__` method with incorrect inputs."""
        # TODO: specific error
        with pytest.raises(Exception):  # noqa: B017, PT011
            _ = pot + 1

    def test_add_pot(self, pot: gp.CompositePotential) -> None:
        """Test the `__add__` method with a single potential."""
        single_pot = gp.KeplerPotential(m=1e12 * u.solMass, units=galactic)
        newpot = pot + single_pot

        assert isinstance(newpot, gp.CompositePotential)

        newkey, newvalue = tuple(newpot.items())[-1]
        assert isinstance(newkey, str)
        assert newvalue is single_pot

    def test_add_compot(self, pot: gp.CompositePotential) -> None:
        """Test the `__add__` method with a composite potential."""
        comp_pot = gp.CompositePotential(
            kep1=gp.KeplerPotential(m=1e12 * u.solMass, units=galactic),
            kep2=gp.KeplerPotential(m=1e12 * u.solMass, units=galactic),
        )
        newpot = pot + comp_pot

        assert isinstance(newpot, gp.CompositePotential)

        newkey, newvalue = tuple(newpot.items())[-2]
        assert newkey == "kep1"
        assert newvalue is newpot["kep1"]

        newkey, newvalue = tuple(newpot.items())[-1]
        assert newkey == "kep2"
        assert newvalue is newpot["kep2"]

    # ==========================================================================

    def test_potential_energy(self, pot, x) -> None:
        assert jnp.isclose(pot.potential_energy(x, t=0), xp.asarray(-0.19386052))

    def test_gradient(self, pot, x):
        assert jnp.allclose(
            pot.gradient(x, t=0), xp.asarray([0.00256403, 0.00512806, 0.01115272])
        )

    def test_density(self, pot, x):
        assert jnp.isclose(pot.density(x, t=0), 33365858.46361218)

    def test_hessian(self, pot, x):
        assert jnp.allclose(
            pot.hessian(x, t=0),
            xp.asarray(
                [
                    [0.00231054, -0.00050698, -0.00101273],
                    [-0.00050698, 0.00155006, -0.00202546],
                    [-0.00101273, -0.00202546, -0.00197444],
                ]
            ),
        )