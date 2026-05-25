# fastmdx

PyPI alias for [**FastMDXplora**](https://github.com/aai-research-lab/FastMDXplora).

The canonical package is [`fastmdxplora`](https://pypi.org/project/fastmdxplora/). This shim exists so that `pip install fastmdx` works for users who reach for the shorter name. Installing it transparently installs `fastmdxplora` underneath.

## Recommended usage

```python
import fastmdxplora as fastmdx
```

The bare `import fastmdx` form also works and re-exports the `fastmdxplora` namespace, emitting a one-time notice suggesting the recommended idiom above.

## CLI

The CLI command is also `fastmdx`. It is provided by the canonical `fastmdxplora` package, so it is available regardless of whether you `pip install fastmdxplora` or `pip install fastmdx`.

```bash
fastmdx explore -system protein.pdb
fastmdx xplore -pdb-id 1L2Y
```

## Source code

All code, documentation, examples, and issue tracker live at the canonical repository:

**https://github.com/aai-research-lab/FastMDXplora**

## Citation

> Aina, A.; Kwan, D. *FastMDAnalysis: Software for Automated Analysis of Molecular Dynamics Trajectories.* J. Comput. Chem. **2026**, 47, e70350. DOI: [10.1002/jcc.70350](https://doi.org/10.1002/jcc.70350)

## License

MIT — see the canonical repository for the full text.
