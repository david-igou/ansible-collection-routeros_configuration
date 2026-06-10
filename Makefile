COLLECTION_NAMESPACE := david_igou
COLLECTION_NAME      := routeros_configuration
COLLECTION           := $(COLLECTION_NAMESPACE).$(COLLECTION_NAME)
COLLECTION_VERSION   := $(shell grep '^version:' galaxy.yml | awk '{print $$2}')

# Scenarios that own their own CHR lifecycle (create/prepare/destroy in their
# test_sequence) run standalone; every other (shared-state) scenario relies on
# the `default` scenario to boot the shared CHR, so a single-scenario run must
# prepend it (see the `molecule` target's SCENARIO= branch).
SELF_OWNING := chr lifecycle default

# The shared-state pass — the SINGLE source of truth for which scenarios run
# against the one shared CHR and in what order (CI consumes it via
# `make molecule-shared`; do not duplicate this list elsewhere). ORDER MATTERS:
#   - `default` MUST be first: under shared_state it owns create/prepare, and
#     molecule runs explicitly-listed scenarios in the given order (whereas
#     `--all` sorts by directory, which would put configure_* before default
#     and converge against an un-prepared CHR).
#   - `ping` and `fetch` self-target the device, so they run BEFORE
#     configure_full installs its input firewall (drops ICMP and http/80,
#     allowing only 22/8728).
#   - Rebooting scenarios (`restore`, `reboot`) run LAST among the
#     device-mutating scenarios so their reboot windows can't race another
#     scenario's converge. `negative` is validation-only (no mutation), so it
#     is safe anywhere, including after `reboot`.
SHARED_SCENARIOS := default ping fetch configure_lists configure_singletons \
	configure_ordered configure_modify_only \
	configure_dependency_chain configure_full configure_check_mode \
	certificate upgrade export_vars \
	command poe user_password reset \
	backup restore reboot negative
SHARED_SCENARIO_ARGS := $(foreach s,$(SHARED_SCENARIOS),-s $(s))

# PROVISIONER picks which mp.<backend> block a scenario uses when its inventory
# declares more than one. The chr scenario declares only qemu, so leaving this
# unset is correct — molecule_provisioners auto-selects. Override only for
# multi-backend scenarios (e.g. `PROVISIONER=qemu make molecule SCENARIO=chr`).

# Scenarios live at extensions/molecule/<scenario>/molecule.yml — point molecule
# at that layout via MOLECULE_GLOB so the `molecule` target works from the
# collection root and auto-discovers the shared base config at
# extensions/molecule/config.yml (which only fires from the collection root).
export MOLECULE_GLOB := extensions/molecule/*/molecule.yml

# The dev shell may export ANSIBLE_INVENTORY for ad-hoc runs; it leaks into
# molecule's subprocess and overrides per-scenario inventory. Strip it.
unexport ANSIBLE_INVENTORY

.PHONY: help install molecule molecule-shared test collection-build collection-install clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install everything molecule needs (runtime deps, test provisioner, this collection)
	ansible-galaxy collection install -r requirements.yml
	# Test-only provisioner up front: shared_state hoists the default scenario's
	# create before molecule's per-scenario dependency step would install it.
	ansible-galaxy collection install -r extensions/molecule/requirements-test.yml
	# The collection under test itself, so FQCN role/filter references resolve
	# in the scenarios — refreshed from the working tree on every run.
	ansible-galaxy collection install . --force

# `molecule`/`molecule-shared` depend on `install` so a single make invocation
# resolves everything the scenarios need: runtime deps, the pinned provisioner,
# and the collection under test. No manual ansible-galaxy calls required —
# locally or in CI (tests.yml calls these targets; the scenario list lives ONLY
# in SHARED_SCENARIOS above).
molecule-shared: install ## Run the shared-state pass (one CHR, all SHARED_SCENARIOS)
	molecule test $(SHARED_SCENARIO_ARGS)

# With no SCENARIO: the full suite — the shared-state pass (all subsystem-role
# scenarios on a single CHR via the `default` scenario — see
# extensions/molecule/config.yml), then the dedicated-CHR scenarios (`chr`
# over network_cli, `lifecycle` for the destructive end-to-end), each booting
# its own VM after the shared CHR has torn down.
molecule: install ## Run molecule test (SCENARIO=<name> for one; omit for the full suite)
ifeq ($(SCENARIO),)
	molecule test $(SHARED_SCENARIO_ARGS)
	molecule test -s chr
	molecule test -s lifecycle
else ifeq ($(filter $(SCENARIO),$(SELF_OWNING)),$(SCENARIO))
	molecule test -s $(SCENARIO)
else
	molecule test -s default -s $(SCENARIO)
endif

test: molecule ## Run the molecule test suite

collection-build: ## Build the collection tarball
	ansible-galaxy collection build --force

collection-install: collection-build ## Build and install the collection locally
	ansible-galaxy collection install $(COLLECTION_NAMESPACE)-$(COLLECTION_NAME)-*.tar.gz --force

clean: ## Remove build artefacts
	rm -f $(COLLECTION_NAMESPACE)-$(COLLECTION_NAME)-*.tar.gz
