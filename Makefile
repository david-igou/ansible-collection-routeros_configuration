COLLECTION_NAMESPACE := david_igou
COLLECTION_NAME      := routeros_configuration
COLLECTION           := $(COLLECTION_NAMESPACE).$(COLLECTION_NAME)
COLLECTION_VERSION   := $(shell grep '^version:' galaxy.yml | awk '{print $$2}')

# Scenarios that own their own CHR lifecycle (create/prepare/destroy in their
# test_sequence) run standalone; every other (shared-state) scenario relies on
# the `default` scenario to boot the shared CHR, so a single-scenario run must
# prepend it (see the `molecule` target's SCENARIO= branch).
SELF_OWNING := chr lifecycle default

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

.PHONY: help install molecule test collection-build collection-install clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime collection dependencies (community.routeros, ansible.netcommon)
	ansible-galaxy collection install -r requirements.yml
	# Test-only provisioner up front: shared_state hoists the default scenario's
	# create before molecule's per-scenario dependency step would install it.
	ansible-galaxy collection install -r extensions/molecule/requirements-test.yml

# `molecule` depends on `install` so a single `make molecule` resolves all
# collections the scenario needs: runtime deps here, and the pinned provisioner
# via molecule's own `dependency` step (extensions/molecule/config.yml ->
# requirements-test.yml). No manual ansible-galaxy calls required.
# With no SCENARIO: run the shared-state pass (all subsystem-role scenarios on a
# single CHR via the `default` scenario — see extensions/molecule/config.yml),
# then the standalone `chr` scenario. The shared pass excludes `chr` (network_cli,
# opts out of shared_state).
molecule: install ## Run molecule test (SCENARIO=<name> for one; omit for the shared pass + chr)
# `default` MUST be listed first: under shared_state it owns create/prepare, and
# molecule runs explicitly-listed scenarios in the given order (whereas `--all`
# sorts by directory, which would put configure_* before default and converge
# against an un-prepared CHR).
ifeq ($(SCENARIO),)
	molecule test -s default -s ping -s fetch -s configure_lists -s configure_singletons \
		-s configure_ordered -s configure_modify_only \
		-s configure_dependency_chain -s configure_full -s configure_check_mode \
		-s certificate -s upgrade -s export_vars \
		-s command -s poe -s user_password -s reset \
		-s backup -s restore -s reboot -s negative
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
