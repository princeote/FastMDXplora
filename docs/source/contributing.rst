Contributing
============

FastMDAnalysis is an open-source project released under the MIT license. The
research paper emphasises reproducibility and extensibility; this page explains
how to contribute new analyses, improve documentation, or report issues.

Development setup
-----------------

1. Fork the repository and clone your fork.
2. Install in editable mode with development extras::

		python -m pip install -e .
		python -m pip install -r docs/requirements.txt  # optional, for docs

3. Run the unit tests regularly::

		python -m unittest tests.tests

	The suite exercises every analysis on the bundled Trp-cage dataset and
	mirrors the validation described in the manuscript.

Coding guidelines
-----------------

* Follow the patterns documented in ``.github/copilot-instructions.md`` and the
  ``analysis/base.py`` contract (set ``self.data``, populate ``self.results``,
  write outputs via ``_save_data``/``_save_plot``).
* Use informative logging via the shared ``logging`` configuration instead of
  ``print``.
* Keep plots backend-agnostic (``matplotlib`` is already forced to ``Agg``).
* Provide docstrings and update the relevant ``docs/source`` page when adding
  new functionality.

Adding a new analysis module
----------------------------

1. Create ``FastMDAnalysis/analysis/<name>.py`` and subclass
	``BaseAnalysis``.
2. Implement ``run()`` to compute data, populate ``self.results``, and return
	the dictionary. Call ``self.plot()`` if the analysis always produces figures.
3. Implement ``plot()`` to generate PNG outputs and return their paths. Reuse
	helper methods for saving.
4. Register the class in ``FastMDAnalysis/analysis/__init__.py`` and expose a
	convenience method in ``FastMDAnalysis/__init__.py`` if appropriate.
5. Update ``FastMDAnalysis/cli.py`` to add a subcommand and options.
6. Document the behaviour under ``docs/source/analysis/<name>.rst`` and add an
	entry to examples/tests where applicable.

Documentation contributions
---------------------------

* Rebuild docs locally with::

		python -m sphinx -b html docs/source docs/build/html

* For iterative writing, use::

		python -m sphinx_autobuild docs/source docs/build/html --open-browser

* Keep prose concise and reference the manuscript where context helps readers.

Reporting issues
----------------

Open GitHub issues with the following details:

* Operating system and Python version
* Exact command or API call
* Full traceback or log file (``<analysis>_output/<command>.log``)
* Steps to reproduce using the bundled datasets when possible

Community values
-----------------

We welcome contributions from students and researchers of all backgrounds. By
sharing analyses, datasets, and documentation, you help expand the toolkit and
make MD analysis more approachable – the central motivation of the project.
