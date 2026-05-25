"""Named force-field selector.

FastMDXplora lets users pick a force field by a short, documented **name**
(e.g. ``charmm36``, ``amber14``) rather than by listing raw OpenMM XML
filenames. Each name resolves to the underlying protein/water XML set, a
default water model, and whether the force field supports small-molecule
ligand parameterization.

This module is the single source of truth for that mapping. The setup phase
calls :func:`resolve_forcefield` to turn a name into a concrete
:class:`ForceFieldChoice`; everything else (the OpenMM ``ForceField`` build,
the manifest record, validation messages) is derived from it.

A raw-XML escape hatch remains available: a user who passes an explicit
``force_field`` list of XML filenames bypasses the named selector entirely
(see the setup pipeline). That is for power users who need a combination the
named registry does not (yet) cover.

The XML filenames below were verified against the force-field files bundled
with OpenMM (``openmm/app/data``). Adding a new named force field is a single
entry in :data:`_REGISTRY`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ForceFieldChoice:
    """A resolved force-field selection.

    Attributes
    ----------
    name : str
        The canonical name (lowercased), as recorded in the manifest.
    xmls : tuple[str, ...]
        OpenMM force-field XML files, passed positionally to
        ``openmm.app.ForceField(*xmls)``.
    water_model : str | None
        Default water model name for ``Modeller.addSolvent(model=...)``.
        ``None`` means "let Modeller infer it from the force field".
    supports_ligand : bool
        Whether this force field can parameterize small-molecule ligands
        (via the OpenFF small-molecule generator). Used by the ligand
        feature to reject incoherent combinations with a clear error.
    small_molecule_forcefield : str | None
        Default small-molecule force field name handed to the OpenFF
        ``SystemGenerator`` (e.g. ``openff-2.2.1``) when ``supports_ligand``
        is true. ``None`` for protein-only force fields.
    description : str
        One-line human-readable summary for help text and templates.
    """

    name: str
    xmls: tuple[str, ...]
    water_model: str | None
    supports_ligand: bool
    small_molecule_forcefield: str | None
    description: str


# ---------------------------------------------------------------------------
# Registry — the single source of truth for named force fields.
#
# XML filenames verified against OpenMM's bundled openmm/app/data. Each entry
# is independent; adding a force field is one line. The ligand-capable
# AMBER+OpenFF entry is added by the ligand feature, where the OpenFF
# small-molecule generator wiring lives.
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, ForceFieldChoice] = {
    "charmm36": ForceFieldChoice(
        name="charmm36",
        xmls=("charmm36.xml", "charmm36/water.xml"),
        water_model=None,  # CHARMM36 water XML supplies the model
        supports_ligand=False,
        small_molecule_forcefield=None,
        description="CHARMM36 protein force field with CHARMM-style water.",
    ),
    "amber14": ForceFieldChoice(
        name="amber14",
        xmls=("amber14-all.xml", "amber14/tip3p.xml"),
        water_model="tip3p",
        supports_ligand=False,
        small_molecule_forcefield=None,
        description="AMBER14 (all biopolymers) with TIP3P water.",
    ),
    "amber-fb15": ForceFieldChoice(
        name="amber-fb15",
        xmls=("amberfb15.xml", "tip3p.xml"),
        water_model="tip3p",
        supports_ligand=False,
        small_molecule_forcefield=None,
        description="AMBER-FB15 protein force field with TIP3P water.",
    ),
    "amber-openff": ForceFieldChoice(
        name="amber-openff",
        xmls=("amber14/protein.ff14SB.xml", "amber14/tip3p.xml"),
        water_model="tip3p",
        supports_ligand=True,
        small_molecule_forcefield="openff-2.2.1",
        description=(
            "AMBER ff14SB protein + TIP3P water + OpenFF Sage 2.2.1 for "
            "small-molecule ligands (protein-ligand systems)."
        ),
    ),
}

#: The default force field when the user specifies none. CHARMM36 is the
#: verified default that protein-only workflows have used since v0.1.0.
DEFAULT_FORCEFIELD = "charmm36"


def available_forcefields() -> tuple[str, ...]:
    """Return the registered force-field names, sorted for stable display."""
    return tuple(sorted(_REGISTRY))


def resolve_forcefield(name: str | None) -> ForceFieldChoice:
    """Resolve a force-field name to a :class:`ForceFieldChoice`.

    Parameters
    ----------
    name : str | None
        A registered force-field name (case-insensitive). ``None`` selects
        :data:`DEFAULT_FORCEFIELD`.

    Returns
    -------
    ForceFieldChoice

    Raises
    ------
    ValueError
        If ``name`` is not a registered force field. The message lists the
        valid choices.
    """
    key = (name or DEFAULT_FORCEFIELD).strip().lower()
    choice = _REGISTRY.get(key)
    if choice is None:
        valid = ", ".join(available_forcefields())
        raise ValueError(
            f"Unknown force field {name!r}. Valid choices: {valid}. "
            f"(For an unlisted combination, pass an explicit `force_field` "
            f"list of OpenMM XML filenames instead.)"
        )
    return choice
