"""galax: Galactic Dynamix in Jax."""

__all__ = ["MockStreamGenerator"]

from dataclasses import KW_ONLY
from functools import partial
from typing import TypeAlias, final

import equinox as eqx
import jax
import jax.experimental.array_api as xp
import jax.numpy as jnp
from jax.lib.xla_bridge import get_backend

from galax.coordinates import PhaseSpacePosition, PhaseSpaceTimePosition
from galax.dynamics._dynamics.integrate._api import Integrator
from galax.dynamics._dynamics.integrate._builtin import DiffraxIntegrator
from galax.dynamics._dynamics.orbit import Orbit, evaluate_orbit, integrate_orbit
from galax.potential._potential.base import AbstractPotentialBase
from galax.typing import BatchVec6, FloatScalar, IntScalar, Vec6, VecN, VecTime

from .core import MockStream
from .df import AbstractStreamDF
from .utils import cond_reverse, interleave_concat

Carry: TypeAlias = tuple[IntScalar, VecN, VecN]


@final
class MockStreamGenerator(eqx.Module):  # type: ignore[misc]
    """Generate a mock stellar stream in the specified external potential."""

    df: AbstractStreamDF
    """Distribution function for generating mock streams.

    E.g. ``galax.dynamics.mockstream.FardalStreamDF``.
    """

    potential: AbstractPotentialBase
    """Potential in which the progenitor orbits and creates a stream."""

    _: KW_ONLY
    progenitor_integrator: Integrator = eqx.field(
        default=DiffraxIntegrator(), static=True
    )
    """Integrator for the progenitor orbit."""

    stream_integrator: Integrator = eqx.field(default=DiffraxIntegrator(), static=True)
    """Integrator for the stream."""

    # ==========================================================================

    @partial(jax.jit)
    def _run_scan(  # TODO: output shape depends on the input shape
        self, ts: VecTime, mock0_lead: MockStream, mock0_trail: MockStream
    ) -> tuple[BatchVec6, BatchVec6]:
        """Generate stellar stream by scanning over the release model/integration.

        Better for CPU usage.
        """
        w0_lead = mock0_lead.w()
        w0_trail = mock0_trail.w()
        t_f = ts[-1] + 1e-3  # TODO: not have the bump in the final time.

        def one_pt_intg(carry: Carry, _: IntScalar) -> tuple[Carry, tuple[VecN, VecN]]:
            """Integrate one point along the stream.

            Parameters
            ----------
            carry : tuple[int, VecN, VecN]
                Initial state of the particle at index `idx`.
            idx : int
                Index of the current point.
            """
            i, w0_l_i, w0_t_i = carry
            tstep = xp.asarray([ts[i], t_f])

            def integ_ics(ics: Vec6) -> VecN:
                # TODO: only return the final state
                return integrate_orbit(
                    self.potential, ics, tstep, integrator=self.stream_integrator
                ).w()[-1]

            # vmap integration over leading and trailing arm
            w0_lt_i = jnp.vstack([w0_l_i, w0_t_i])  # TODO: xp.stack
            w_l, w_t = jax.vmap(integ_ics, in_axes=(0,))(w0_lt_i)
            # Prepare for next iteration
            carry_out = (i + 1, w0_lead[i + 1, :], w0_trail[i + 1, :])
            return carry_out, (w_l, w_t)

        carry_init = (0, w0_lead[0, :], w0_trail[0, :])
        pt_ids = xp.arange(len(w0_lead))
        lead_arm_w, trail_arm_w = jax.lax.scan(one_pt_intg, carry_init, pt_ids)[1]

        return lead_arm_w, trail_arm_w

    @partial(jax.jit)
    def _run_vmap(  # TODO: output shape depends on the input shape
        self, ts: VecTime, mock0_lead: MockStream, mock0_trail: MockStream
    ) -> tuple[BatchVec6, BatchVec6]:
        """Generate stellar stream by vmapping over the release model/integration.

        Better for GPU usage.
        """
        t_f = ts[-1] + 1e-3  # TODO: not have the bump in the final time.

        # TODO: make this a separated method
        @jax.jit  # type: ignore[misc]
        def one_pt_intg(i: IntScalar, w0_l_i: Vec6, w0_t_i: Vec6) -> tuple[Vec6, Vec6]:
            tstep = xp.asarray([ts[i], t_f])
            # TODO: only return the final state
            w_lead = integrate_orbit(
                self.potential, w0_l_i, tstep, integrator=self.stream_integrator
            ).w()[-1]
            w_trail = integrate_orbit(
                self.potential, w0_t_i, tstep, integrator=self.stream_integrator
            ).w()[-1]
            return w_lead, w_trail

        w0_lead = mock0_lead.w()
        w0_trail = mock0_trail.w()
        pt_ids = xp.arange(len(w0_lead))
        lead_arm_w, trail_arm_w = jax.vmap(one_pt_intg)(pt_ids, w0_lead, w0_trail)
        return lead_arm_w, trail_arm_w

    @partial(jax.jit, static_argnames=("seed_num", "vmapped"))
    def run(
        self,
        ts: VecTime,
        prog_w0: PhaseSpaceTimePosition | PhaseSpacePosition | Vec6,
        prog_mass: FloatScalar,
        *,
        seed_num: int,
        vmapped: bool | None = None,
    ) -> tuple[MockStream, Orbit]:
        """Generate mock stellar stream.

        Parameters
        ----------
        ts : Array[float, (time,)]
            Stripping times.
        prog_w0 : Array[float, (6,)]
            Initial conditions of the progenitor.
        prog_mass : float
            Mass of the progenitor.

        seed_num : int, keyword-only
            Seed number for the random number generator.

            :todo: a better way to handle PRNG

        vmapped : bool | None, optional keyword-only
            Whether to use `jax.vmap` (`True`) or `jax.lax.scan` (`False`) to
            parallelize the integration. ``vmapped=True`` is recommended for GPU
            usage, while ``vmapped=False`` is recommended for CPU usage.  If
            `None` (default), then `jax.vmap` is used on GPU and `jax.lax.scan`
            otherwise.

        Returns
        -------
        mockstream : MockStream
            Leading and/or trailing arms of the mock stream.
        prog_o : Orbit
            Orbit of the progenitor.
        """
        # TODO: ꜛ a discussion about the stripping times
        # Parse vmapped
        use_vmap = get_backend().platform == "gpu" if vmapped is None else vmapped

        # Ensure w0 is a PhaseSpacePosition
        if isinstance(prog_w0, PhaseSpaceTimePosition):
            w0 = eqx.error_if(prog_w0, prog_w0.ndim > 0, "prog_w0 must be scalar")
        elif isinstance(prog_w0, PhaseSpacePosition):
            w0 = eqx.error_if(prog_w0, prog_w0.ndim > 0, "prog_w0 must be scalar")
            w0 = PhaseSpaceTimePosition(q=prog_w0.q, p=prog_w0.p, t=ts[0])
        else:
            w0 = PhaseSpaceTimePosition(prog_w0[0:3], prog_w0[3:6], t=ts[0])

        # If the time stepping passed in is negative, assume this means that all
        # of the initial conditions are at *end time*, and we need to reverse
        # them before treating them as initial conditions
        ts = cond_reverse(ts[1] < ts[0], ts)

        # Integrate the progenitor orbit, evaluating at the stripping times
        prog_o = evaluate_orbit(
            self.potential, w0, ts, integrator=self.progenitor_integrator
        )

        # Generate stream initial conditions along the integrated progenitor
        # orbit. The release times are stripping times.
        mock0_lead, mock0_trail = self.df.sample(
            self.potential, prog_o, prog_mass, seed_num=seed_num
        )

        if use_vmap:
            lead_arm_w, trail_arm_w = self._run_vmap(ts, mock0_lead, mock0_trail)
        else:
            lead_arm_w, trail_arm_w = self._run_scan(ts, mock0_lead, mock0_trail)

        t = xp.ones_like(ts) * ts[-1]  # TODO: ensure this time is correct

        # TODO: move the leading vs trailing logic to the DF
        if self.df.lead and self.df.trail:
            axis = len(trail_arm_w.shape) - 2
            q = interleave_concat(trail_arm_w[:, 0:3], lead_arm_w[:, 0:3], axis=axis)
            p = interleave_concat(trail_arm_w[:, 3:6], lead_arm_w[:, 3:6], axis=axis)
            t = interleave_concat(t, t, axis=0)
            release_time = interleave_concat(
                mock0_lead.release_time, mock0_trail.release_time, axis=0
            )
        elif self.df.lead:
            q = lead_arm_w[:, 0:3]
            p = lead_arm_w[:, 3:6]
            release_time = mock0_lead.release_time
        elif self.df.trail:
            q = trail_arm_w[:, 0:3]
            p = trail_arm_w[:, 3:6]
            release_time = mock0_trail.release_time
        else:
            msg = "You must generate either leading or trailing tails (or both!)"
            raise ValueError(msg)

        mockstream = MockStream(q=q, p=p, t=t, release_time=release_time)

        return mockstream, prog_o